# ruff: noqa: SLF001
"""Unit tests for ChargeScheduler (state_machine/scheduler.py).

ChargeScheduler.__init__ only wires up ScOptionState plus two trivial local
fields, so unlike SolarCharge it can be constructed directly with the same
hass/entry/subentry fakes used elsewhere in this suite.

async_get_schedule_data() is the "schedule-goal calculation": it composes
roughly a dozen already-simple ScOptionState/ScState primitives (is_sun_
trigger(), get_weekly_schedule(), is_end_on_condition(), ...) into one
ScheduleData "goal", then hands off to _look_ahead_to_reduce_charge_limit_
difference(), _async_set_charge_limit_goal_if_calibration() and
_calc_charge_starttime() for the actual date/limit math. The integration
tests below (make_bare_scheduler) replace each of those primitives with a
canned value on the instance, so they exercise async_get_schedule_data()'s
own branching -- which day's schedule wins, whether an end time counts --
rather than re-verifying primitives that are simple getters in their own
right. _calculate_need_charge_duration(), _get_look_ahead_charge_limit() and
_calc_charge_starttime() are tested directly below that, since they are the
real calculations and are cheap to drive with a plain ScheduleData.
"""

from datetime import datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from custom_components.solarcharger.const import (
    NUMBER_CHARGER_MAX_SPEED,
    WEEKLY_DAY_NAMES,
)
from custom_components.solarcharger.models.model_schedule_data import (
    ChargeSchedule,
    ScheduleData,
)
from custom_components.solarcharger.state_machine.scheduler import (
    LOOK_AHEAD_CHARGE_LIMIT_DAYS,
    MAX_CHARGE_LIMIT_DIFF,
    MIN_CHARGE_LIMIT_DIFF,
    ChargeScheduler,
)
import pytest

from .conftest import make_config_entry, make_hass, make_subentry

TESLA23M3_SUBENTRY_ID = "tesla23m3"

# Monday, so day_index 0 needs no wraparound; other tests pick day_index
# values that do wrap through the 7-day week on purpose.
ANCHOR_NOW = datetime(2026, 1, 5, 10, 0, tzinfo=ZoneInfo("UTC"))


# ----------------------------------------------------------------------------
def make_scheduler(
    max_charge_speed: str | None,
) -> ChargeScheduler:
    """Build a ChargeScheduler with the given max-charge-speed option configured."""
    options: dict[str, str] = {}
    states: dict[str, str] = {}
    if max_charge_speed is not None:
        options[NUMBER_CHARGER_MAX_SPEED] = "number.tesla23m3_max_speed"
        states["number.tesla23m3_max_speed"] = max_charge_speed

    hass = make_hass(states)
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(subentry, options={subentry.unique_id: options})
    return ChargeScheduler(hass, entry, subentry)  # type: ignore[arg-type]


def make_weekly_schedule(
    limits: list[float], endtimes: list[time] | None = None
) -> list[ChargeSchedule]:
    """Build a 7-day weekly schedule (Monday first) from per-day charge limits."""
    endtimes = endtimes or [time.min] * 7
    return [
        ChargeSchedule(
            charge_day=WEEKLY_DAY_NAMES[i],
            charge_limit=limits[i],
            charge_end_time=endtimes[i],
        )
        for i in range(7)
    ]


def make_chargeable(
    charge_limit: float, state_of_charge: float | None = None
) -> object:
    """Minimal stand-in for a Chargeable: only these two getters are read here."""
    return SimpleNamespace(
        get_charge_limit=lambda: charge_limit,
        get_state_of_charge=lambda: state_of_charge,
    )


def make_bare_scheduler(
    *,
    is_schedule_charge: bool = False,
    weekly_schedule: list[ChargeSchedule] | None = None,
    is_reduce_charge_limit_difference: bool = False,
    is_calibrate_max_charge_speed: bool = False,
    is_sun_trigger: bool = False,
    sun_above_start_end_elevations: bool = False,
    sun_elevation: float = 0.0,
    is_end_on_condition: bool = False,
    consumed_energy_today: float = 0.0,
    self_depower_today: int = 0,
    now: datetime = ANCHOR_NOW,
) -> ChargeScheduler:
    """Build a ChargeScheduler with its ScOptionState-inherited getters stubbed to fixed values."""
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(subentry)
    hass = make_hass()
    scheduler = ChargeScheduler(hass, entry, subentry)  # type: ignore[arg-type]

    scheduler.get_local_datetime = lambda: now
    scheduler.is_sun_trigger = lambda: is_sun_trigger
    scheduler.is_sun_above_start_end_elevation_triggers = lambda: (
        sun_above_start_end_elevations,
        sun_elevation,
    )
    scheduler.get_consumed_energy_today = lambda: consumed_energy_today
    scheduler.get_self_depower_today = lambda: self_depower_today
    scheduler.is_end_on_condition = lambda: is_end_on_condition
    scheduler.is_schedule_charge = lambda: is_schedule_charge
    scheduler.get_weekly_schedule = lambda: weekly_schedule or []
    scheduler.is_reduce_charge_limit_difference_between_days = lambda: (
        is_reduce_charge_limit_difference
    )
    scheduler.is_calibrate_max_charge_speed = lambda: is_calibrate_max_charge_speed
    # _calc_charge_starttime()'s own date math is covered separately below; here
    # it only needs to run without aborting for want of a configured max speed.
    scheduler._get_one_percent_charge_duration = lambda: 360.0

    return scheduler


# ----------------------------------------------------------------------------
# _get_one_percent_charge_duration() -- max charge speed = 6.1 %/hr
# ----------------------------------------------------------------------------
def test_one_percent_charge_duration_is_an_hour_divided_by_max_speed() -> None:
    """One percent of charge takes (3600 seconds / configured %-per-hour) to complete."""
    scheduler = make_scheduler("6.1")

    assert scheduler._get_one_percent_charge_duration() == pytest.approx(3600 / 6.1)


def test_one_percent_charge_duration_raises_when_unconfigured() -> None:
    """No configured max-speed entity aborts rather than dividing by a default."""
    scheduler = make_scheduler(None)

    with pytest.raises(ValueError, match="Failed to get entity number value"):
        scheduler._get_one_percent_charge_duration()


def test_one_percent_charge_duration_raises_zero_division_at_zero_speed() -> None:
    """A calibrated max speed of exactly 0 %/hr is not guarded against divide-by-zero.

    Pinned as a characterization test: if 0 becomes a legitimate calibration
    outcome, this method needs a guard, not just a passing test.
    """
    scheduler = make_scheduler("0")

    with pytest.raises(ZeroDivisionError):
        scheduler._get_one_percent_charge_duration()


# ----------------------------------------------------------------------------
# async_get_schedule_data() -- composing the primitives into a ScheduleData goal
# ----------------------------------------------------------------------------
async def test_schedule_data_mirrors_chargeable_limit_when_schedule_disabled() -> None:
    """With scheduling off, the goal just carries the chargeable's own charge limit."""
    scheduler = make_bare_scheduler(is_schedule_charge=False)
    chargeable = make_chargeable(charge_limit=80.0)

    goal = await scheduler.async_get_schedule_data(
        chargeable,
        timer_session=False,
        include_tomorrow=False,
        started_calibration=False,
        started_max_charge=0,
    )

    assert goal.use_charge_schedule is False
    assert goal.old_charge_limit == 80.0
    assert goal.new_charge_limit == 80.0
    assert goal.has_charge_endtime is False


async def test_schedule_data_uses_todays_limit_when_endtime_still_ahead() -> None:
    """A future end time today, with SOC below limit, sets has_charge_endtime for today."""
    weekly = make_weekly_schedule(
        limits=[70, 0, 0, 0, 0, 0, 0],
        endtimes=[time(18, 0), *([time.min] * 6)],
    )
    scheduler = make_bare_scheduler(is_schedule_charge=True, weekly_schedule=weekly)
    chargeable = make_chargeable(charge_limit=70.0, state_of_charge=40.0)

    goal = await scheduler.async_get_schedule_data(
        chargeable,
        timer_session=False,
        include_tomorrow=False,
        started_calibration=False,
        started_max_charge=0,
    )

    assert goal.has_charge_endtime is True
    assert goal.day_index == 0
    assert goal.new_charge_limit == 70
    assert goal.charge_endtime == datetime(2026, 1, 5, 18, 0, tzinfo=ZoneInfo("UTC"))


async def test_schedule_data_ignores_a_todays_endtime_that_has_already_passed() -> None:
    """An end time earlier than now today does not count as a usable charge end time."""
    weekly = make_weekly_schedule(
        limits=[70, 0, 0, 0, 0, 0, 0],
        endtimes=[time(8, 0), *([time.min] * 6)],  # before ANCHOR_NOW's 10:00
    )
    scheduler = make_bare_scheduler(is_schedule_charge=True, weekly_schedule=weekly)
    chargeable = make_chargeable(charge_limit=70.0, state_of_charge=40.0)

    goal = await scheduler.async_get_schedule_data(
        chargeable,
        timer_session=False,
        include_tomorrow=False,
        started_calibration=False,
        started_max_charge=0,
    )

    assert goal.has_charge_endtime is False


async def test_schedule_data_falls_through_to_tomorrow_when_today_has_no_endtime() -> (
    None
):
    """No end time today, but include_tomorrow=True: tomorrow's schedule takes over."""
    weekly = make_weekly_schedule(
        limits=[70, 90, 0, 0, 0, 0, 0],
        endtimes=[time.min, time(20, 0), *([time.min] * 5)],
    )
    scheduler = make_bare_scheduler(is_schedule_charge=True, weekly_schedule=weekly)
    chargeable = make_chargeable(charge_limit=70.0, state_of_charge=40.0)

    goal = await scheduler.async_get_schedule_data(
        chargeable,
        timer_session=False,
        include_tomorrow=True,
        started_calibration=False,
        started_max_charge=0,
    )

    assert goal.has_charge_endtime is True
    assert goal.day_index == 1
    assert goal.new_charge_limit == 90
    assert goal.charge_endtime == datetime(2026, 1, 6, 20, 0, tzinfo=ZoneInfo("UTC"))


async def test_schedule_data_does_not_consult_tomorrow_when_not_asked_to() -> None:
    """Same schedule as above, but include_tomorrow=False leaves has_charge_endtime unset."""
    weekly = make_weekly_schedule(
        limits=[70, 90, 0, 0, 0, 0, 0],
        endtimes=[time.min, time(20, 0), *([time.min] * 5)],
    )
    scheduler = make_bare_scheduler(is_schedule_charge=True, weekly_schedule=weekly)
    chargeable = make_chargeable(charge_limit=70.0, state_of_charge=40.0)

    goal = await scheduler.async_get_schedule_data(
        chargeable,
        timer_session=False,
        include_tomorrow=False,
        started_calibration=False,
        started_max_charge=0,
    )

    assert goal.has_charge_endtime is False


# ----------------------------------------------------------------------------
# _calculate_need_charge_duration() -- pure duration math
# ----------------------------------------------------------------------------
def test_need_charge_duration_below_100_percent_has_no_extra_buffer() -> None:
    """Below 100%, duration is just (limit - soc) percent-points plus one loop's buffer."""
    scheduler = make_scheduler(None)

    duration = scheduler._calculate_need_charge_duration(
        battery_soc=40.0, charge_limit=70.0, one_percent_charge_duration=360.0
    )

    assert duration == timedelta(seconds=(70 - 40) * 360 + 360)


def test_need_charge_duration_to_100_percent_adds_a_six_percent_buffer() -> None:
    """Charging all the way to 100% adds a 6x one-percent-duration buffer for SOC drift."""
    scheduler = make_scheduler(None)

    duration = scheduler._calculate_need_charge_duration(
        battery_soc=90.0, charge_limit=100.0, one_percent_charge_duration=360.0
    )

    assert duration == timedelta(seconds=(100 - 90) * 360 + 360 + 6 * 360)


# ----------------------------------------------------------------------------
# _get_look_ahead_charge_limit() -- how far ahead to plan today's charge limit
# ----------------------------------------------------------------------------
def test_look_ahead_uses_min_diff_when_tomorrow_has_the_highest_limit() -> None:
    """When the peak in the look-ahead window falls on tomorrow, subtract MIN_CHARGE_LIMIT_DIFF."""
    scheduler = make_scheduler(None)
    assert LOOK_AHEAD_CHARGE_LIMIT_DAYS == 4
    goal = ScheduleData(
        weekly_schedule=make_weekly_schedule(limits=[50, 90, 60, 40, 90, 90, 90]),
        day_index=0,
        has_charge_endtime=False,
        new_charge_limit=50,
    )

    look_ahead_limit = scheduler._get_look_ahead_charge_limit(goal)

    assert look_ahead_limit == 90 - MIN_CHARGE_LIMIT_DIFF


def test_look_ahead_uses_index_times_max_diff_for_a_later_peak_day() -> None:
    """A peak later in the window (here day+2, wrapping past Sunday) uses index * MAX_CHARGE_LIMIT_DIFF."""
    scheduler = make_scheduler(None)
    # day_index=5 (Saturday): window wraps Sat(10), Sun(15), Mon(20), Tue(20).
    # First strictly-greater max is Mon at window-index 2 (Tue ties, doesn't win).
    goal = ScheduleData(
        weekly_schedule=make_weekly_schedule(limits=[20, 20, 0, 0, 0, 10, 15]),
        day_index=5,
        has_charge_endtime=False,
        new_charge_limit=10,
    )

    look_ahead_limit = scheduler._get_look_ahead_charge_limit(goal)

    assert look_ahead_limit == 20 - (2 * MAX_CHARGE_LIMIT_DIFF)


def test_look_ahead_is_skipped_when_charge_endtime_set_and_not_near_done() -> None:
    """With a charge end time and SOC not yet 1% below limit, look-ahead does not apply."""
    scheduler = make_scheduler(None)
    goal = ScheduleData(
        weekly_schedule=make_weekly_schedule(limits=[0, 0, 0, 0, 0, 0, 0]),
        day_index=0,
        has_charge_endtime=True,
        new_charge_limit=80,
        battery_soc=50,  # not battery_soc + 1 == new_charge_limit
    )

    look_ahead_limit = scheduler._get_look_ahead_charge_limit(goal)

    assert look_ahead_limit == 80


# ----------------------------------------------------------------------------
# _calc_charge_starttime() -- projecting when the next session needs to start
# ----------------------------------------------------------------------------
def test_calc_charge_starttime_noop_without_a_charge_endtime() -> None:
    """No charge end time means nothing to project."""
    scheduler = make_scheduler("10")
    goal = ScheduleData(weekly_schedule=[], has_charge_endtime=False)

    scheduler._calc_charge_starttime(goal)

    assert goal.propose_charge_starttime == datetime.min
    assert goal.max_charge_now is False
    assert goal.start_next_session_now is False


@pytest.mark.parametrize(
    ("battery_soc", "new_charge_limit"),
    [
        pytest.param(None, 80.0, id="missing_soc"),
        pytest.param(80.0, 80.0, id="soc_already_at_limit"),
    ],
)
def test_calc_charge_starttime_noop_when_soc_unusable(
    battery_soc: float | None, new_charge_limit: float
) -> None:
    """Missing SOC, or SOC already at/above the limit, both skip the projection."""
    scheduler = make_scheduler("10")
    goal = ScheduleData(
        weekly_schedule=[],
        has_charge_endtime=True,
        battery_soc=battery_soc,
        new_charge_limit=new_charge_limit,
    )

    scheduler._calc_charge_starttime(goal)

    assert goal.propose_charge_starttime == datetime.min


def test_calc_charge_starttime_with_plenty_of_time_sets_neither_flag() -> None:
    """Enough time before the end time: no need to force max charge now."""
    scheduler = make_scheduler("10")  # one_percent_charge_duration = 360s
    goal = ScheduleData(
        weekly_schedule=[],
        has_charge_endtime=True,
        battery_soc=40.0,
        new_charge_limit=70.0,
        charge_endtime=datetime(2026, 1, 5, 18, 0, tzinfo=ZoneInfo("UTC")),
        data_timestamp=ANCHOR_NOW,
        started_max_charge=0,
        timer_session=False,
        sun_above_start_end_elevations=True,
    )

    scheduler._calc_charge_starttime(goal)

    # need_charge_duration = (70-40)*360 + 360 = 11160s = 3h6m
    assert goal.propose_charge_starttime == datetime(
        2026, 1, 5, 14, 54, tzinfo=ZoneInfo("UTC")
    )
    assert goal.max_charge_now is False
    assert goal.start_next_session_now is False


def test_calc_charge_starttime_with_too_little_time_sets_both_flags() -> None:
    """Not enough time left before the end time forces max charge now for this and next session."""
    scheduler = make_scheduler("10")
    goal = ScheduleData(
        weekly_schedule=[],
        has_charge_endtime=True,
        battery_soc=10.0,
        new_charge_limit=90.0,
        charge_endtime=datetime(2026, 1, 5, 11, 0, tzinfo=ZoneInfo("UTC")),
        data_timestamp=ANCHOR_NOW,
        started_max_charge=0,
        timer_session=False,
        sun_above_start_end_elevations=True,
    )

    scheduler._calc_charge_starttime(goal)

    # need_charge_duration = (90-10)*360 + 360 = 29160s = 8h6m; 11:00 - 8h6m = 02:54, before "now" (10:00).
    assert goal.propose_charge_starttime == datetime(
        2026, 1, 5, 2, 54, tzinfo=ZoneInfo("UTC")
    )
    assert goal.max_charge_now is True
    assert goal.start_next_session_now is True


def test_calc_charge_starttime_forces_max_charge_for_a_timer_session_at_night() -> None:
    """A timer-triggered session while the sun is below start/end elevations forces max charge, independent of timing."""
    scheduler = make_scheduler("10")
    goal = ScheduleData(
        weekly_schedule=[],
        has_charge_endtime=True,
        battery_soc=40.0,
        new_charge_limit=70.0,
        charge_endtime=datetime(2026, 1, 5, 18, 0, tzinfo=ZoneInfo("UTC")),
        data_timestamp=ANCHOR_NOW,
        started_max_charge=0,
        timer_session=True,
        sun_above_start_end_elevations=False,
    )

    scheduler._calc_charge_starttime(goal)

    assert goal.max_charge_now is True
    # Plenty of time otherwise, so the next-session flag is unaffected.
    assert goal.start_next_session_now is False
