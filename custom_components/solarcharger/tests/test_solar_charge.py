# ruff: noqa: SLF001
"""Unit tests for SolarCharge (state_machine/solar_charge.py).

SolarCharge.__init__ wires up a Tracker, ControlEntities, a Charger/Chargeable
pair and reads config_entry.data for the current-update period -- none of
which get_charger_effective_voltage() touches (it only resolves one option
entity through the inherited ScOptionState/ScConfigState/ScState chain).
Constructing a full SolarCharge just to test that one getter would mean
building fakes for the whole session object graph to satisfy attributes the
test never uses, so these tests bypass __init__ via SolarCharge.__new__() and
set only the attributes ScState/ScConfigState/ScOptionState actually read:
_hass, _entry, _subentry, caller, _internal_entity_ids.
"""

from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.solarcharger.const import (
    MAX_CONSECUTIVE_FAILURE_COUNT,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MIN_CURRENT,
    ChargeStatus,
    RunState,
)
from custom_components.solarcharger.models.model_charge_stats import ChargeStats
from custom_components.solarcharger.models.model_config import ConfigValue
from custom_components.solarcharger.models.model_context_data import ContextData
from custom_components.solarcharger.models.model_median_data import (
    MedianData,
    MedianDataPoint,
)
from custom_components.solarcharger.models.model_schedule_data import (
    ChargeSchedule,
    ScheduleData,
)
from custom_components.solarcharger.state_machine.solar_charge import SolarCharge
import pytest

from homeassistant.config_entries import ConfigSubentry

from .conftest import FakeConfigEntry, make_config_entry, make_hass, make_subentry

TESLA23M3_SUBENTRY_ID = "tesla23m3"


# ----------------------------------------------------------------------------
def make_bare_solar_charge(
    hass: object | None = None,
    entry: FakeConfigEntry | None = None,
    subentry: ConfigSubentry | None = None,
    *,
    charger: object | None = None,
    chargeable: object | None = None,
    entities: object | None = None,
    running_goal: ScheduleData | None = None,
    power_monitor_duration: float = 0.0,
    can_set_current: bool = False,
    stats: ChargeStats | None = None,
) -> SolarCharge:
    """Build a SolarCharge exposing only a handful of ScState-chain attributes.

    hass/entry/subentry default to fresh fakes when omitted, for tests whose
    methods under test don't touch real option resolution at all (they stub
    their own collaborator methods directly instead). charger/chargeable/
    entities/running_goal/power_monitor_duration/can_set_current/stats are
    only set by tests that need them.
    """
    subentry = subentry or make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = entry or make_config_entry()
    hass = hass or make_hass()

    solar_charge = SolarCharge.__new__(SolarCharge)
    solar_charge._hass = hass
    solar_charge._entry = entry
    solar_charge._subentry = subentry
    solar_charge.caller = subentry.unique_id
    solar_charge._internal_entity_ids = {}
    solar_charge.charger = charger
    solar_charge.chargeable = chargeable
    solar_charge.entities = entities
    solar_charge.running_goal = running_goal
    solar_charge.power_monitor_duration = power_monitor_duration
    solar_charge.can_set_current = can_set_current
    solar_charge.stats = stats
    return solar_charge


def make_fake_charger(max_current: float) -> SimpleNamespace:
    """Minimal stand-in for a Charger: only get_max_charge_current() is read here."""
    return SimpleNamespace(get_max_charge_current=lambda: max_current)


def make_context(
    *,
    connected: bool = True,
    below_charge_limit: bool = True,
    charging: bool = False,
    fast_charge: bool = False,
    calibrate_max_charge_speed: bool = False,
    state: RunState = RunState.CHARGE,
    loop_success_count: int = 0,
    end_on_condition: bool = False,
    exit_condition: bool = False,
    sun_trigger: bool = False,
    sun_above_start_end_elevations: bool = True,
    has_charge_endtime: bool = False,
    max_charge_now: bool = False,
) -> ContextData:
    """Build a ContextData with a real ScheduleData/ChargeStats, defaults tuned to pass every gate."""
    goal = ScheduleData(
        weekly_schedule=[],
        end_on_condition=end_on_condition,
        exit_condition=exit_condition,
        sun_trigger=sun_trigger,
        sun_above_start_end_elevations=sun_above_start_end_elevations,
        has_charge_endtime=has_charge_endtime,
        max_charge_now=max_charge_now,
    )
    context = ContextData(
        charger=None,  # type: ignore[arg-type]
        chargeable=None,  # type: ignore[arg-type]
        state=state,
        goal=goal,
        net_allocations=None,  # type: ignore[arg-type]
        stats=ChargeStats(loop_success_count=loop_success_count),
    )
    context.connected = connected
    context.below_charge_limit = below_charge_limit
    context.charging = charging
    context.fast_charge = fast_charge
    context.calibrate_max_charge_speed = calibrate_max_charge_speed
    return context


def make_ready_median_data(
    *,
    median_value: float,
    last_value: float,
    window_seconds: float = 300.0,
    data_set_ready: bool = True,
) -> MedianData:
    """Build a MedianData in the shape _is_median_net_allocated_power_...() reads."""
    return MedianData(
        window_seconds=window_seconds,
        window_duration=None,  # type: ignore[arg-type]
        sequence=[],
        data_set_ready=data_set_ready,
        median_value=median_value,
        last_data_point=MedianDataPoint(value=last_value, period=1.0, time=None),  # type: ignore[arg-type]
    )


# ----------------------------------------------------------------------------
# get_charger_effective_voltage() -- voltage = 230 V
# ----------------------------------------------------------------------------
def test_get_charger_effective_voltage_reads_configured_number_entity() -> None:
    """Effective voltage comes from the configured number entity's state."""
    hass = make_hass({"number.tesla23m3_voltage": "230"})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_EFFECTIVE_VOLTAGE: "number.tesla23m3_voltage"
            }
        },
    )
    solar_charge = make_bare_solar_charge(hass, entry, subentry)

    assert solar_charge.get_charger_effective_voltage() == 230.0


@pytest.mark.parametrize(
    "voltage",
    [
        pytest.param("0", id="zero_voltage"),
        pytest.param("-230", id="negative_voltage"),
    ],
)
def test_get_charger_effective_voltage_rejects_non_positive_value(
    voltage: str,
) -> None:
    """A configured but non-positive voltage is treated as invalid, not silently used."""
    hass = make_hass({"number.tesla23m3_voltage": voltage})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_EFFECTIVE_VOLTAGE: "number.tesla23m3_voltage"
            }
        },
    )
    solar_charge = make_bare_solar_charge(hass, entry, subentry)

    with pytest.raises(ValueError, match="Invalid charger effective voltage"):
        solar_charge.get_charger_effective_voltage()


def test_get_charger_effective_voltage_raises_when_unconfigured() -> None:
    """No configured entity aborts rather than silently returning a default."""
    hass = make_hass()
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(subentry, options={subentry.unique_id: {}})
    solar_charge = make_bare_solar_charge(hass, entry, subentry)

    with pytest.raises(ValueError, match="Failed to get entity number value"):
        solar_charge.get_charger_effective_voltage()


# ----------------------------------------------------------------------------
# validate_current() -- clamps to [0, max_current], never raises
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("current", "max_current", "expected"),
    [
        pytest.param(-5, 15, 0, id="negative_clamps_to_zero"),
        pytest.param(20, 15, 15, id="above_max_clamps_to_max"),
        pytest.param(7.5, 15, 7.5, id="within_range_passes_through_unchanged"),
        pytest.param(0, 15, 0, id="zero_passes_through_unchanged"),
        pytest.param(15, 15, 15, id="exactly_max_passes_through_unchanged"),
    ],
)
def test_validate_current_clamps_to_explicit_max_current(
    current: float, max_current: float, expected: float
) -> None:
    """With max_current given explicitly, validate_current() needs no charger at all."""
    solar_charge = make_bare_solar_charge(
        make_hass(), make_config_entry(), make_subentry(TESLA23M3_SUBENTRY_ID)
    )

    assert solar_charge.validate_current(current, max_current) == expected


def test_validate_current_falls_back_to_charger_max_current_when_not_given() -> None:
    """Without an explicit max_current, validate_current() asks the attached charger."""
    solar_charge = make_bare_solar_charge(
        make_hass(),
        make_config_entry(),
        make_subentry(TESLA23M3_SUBENTRY_ID),
        charger=make_fake_charger(max_current=15),
    )

    assert solar_charge.validate_current(20) == 15


# ----------------------------------------------------------------------------
# get_charger_min_current() -- min current = 0 A, max current = 15 A
# ----------------------------------------------------------------------------
def test_get_charger_min_current_reads_configured_entity() -> None:
    """Min current comes from the configured number entity, clamped against max current."""
    hass = make_hass({"number.tesla23m3_min_current": "0"})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_MIN_CURRENT: "number.tesla23m3_min_current"
            }
        },
    )
    solar_charge = make_bare_solar_charge(
        hass, entry, subentry, charger=make_fake_charger(max_current=15)
    )

    assert solar_charge.get_charger_min_current() == 0.0


@pytest.mark.parametrize(
    ("configured_min_current", "expected"),
    [
        pytest.param("-3", 0, id="negative_config_clamps_to_zero"),
        pytest.param("20", 15, id="config_above_max_clamps_to_max"),
    ],
)
def test_get_charger_min_current_clamps_a_misconfigured_value(
    configured_min_current: str, expected: float
) -> None:
    """A min-current option outside [0, max_current] is clamped, not trusted as-is."""
    hass = make_hass({"number.tesla23m3_min_current": configured_min_current})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_MIN_CURRENT: "number.tesla23m3_min_current"
            }
        },
    )
    solar_charge = make_bare_solar_charge(
        hass, entry, subentry, charger=make_fake_charger(max_current=15)
    )

    assert solar_charge.get_charger_min_current() == expected


def test_get_charger_min_current_direct_reads_control_entity_state_instead() -> None:
    """direct=True reads the live ControlEntities.numbers state, bypassing config options.

    This is the path get_number_state() takes -- entities.numbers is a dict
    of the actual SolarChargerNumberConfigEntity objects, so a plain object
    exposing .state stands in for one here.
    """
    solar_charge = make_bare_solar_charge(
        make_hass(),
        make_config_entry(),
        make_subentry(TESLA23M3_SUBENTRY_ID),
        charger=make_fake_charger(max_current=15),
        entities=SimpleNamespace(
            numbers={NUMBER_CHARGER_MIN_CURRENT: SimpleNamespace(state=0)}
        ),
    )

    assert solar_charge.get_charger_min_current(direct=True) == 0.0


# ----------------------------------------------------------------------------
# get_charger_max_current() -- validates the charger's own answer
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "reported_max_current",
    [
        pytest.param(None, id="charger_reports_none"),
        pytest.param(0, id="charger_reports_zero"),
        pytest.param(-5, id="charger_reports_negative"),
    ],
)
def test_get_charger_max_current_rejects_a_non_positive_answer(
    reported_max_current: float | None,
) -> None:
    """A charger reporting no usable max current aborts rather than propagating nonsense."""
    solar_charge = make_bare_solar_charge(
        charger=make_fake_charger(max_current=reported_max_current)
    )

    with pytest.raises(ValueError, match="Failed to get charger max current"):
        solar_charge.get_charger_max_current()


def test_get_charger_max_current_returns_a_valid_answer_unchanged() -> None:
    """A positive max current from the charger is returned as-is."""
    solar_charge = make_bare_solar_charge(charger=make_fake_charger(max_current=15))

    assert solar_charge.get_charger_max_current() == 15


# ----------------------------------------------------------------------------
# get_charger_power_factor() -- valid range is (0, 1]
# ----------------------------------------------------------------------------
def _make_solar_charge_with_power_factor(power_factor: float) -> SolarCharge:
    hass = make_hass({"number.power_factor": str(power_factor)})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={subentry.unique_id: {"charger_power_factor": "number.power_factor"}},
    )
    return make_bare_solar_charge(hass, entry, subentry)


@pytest.mark.parametrize("power_factor", [0.0001, 0.5, 1.0])
def test_get_charger_power_factor_accepts_the_valid_range(power_factor: float) -> None:
    """Anything above 0 and up to (and including) 1 is a valid power factor."""
    solar_charge = _make_solar_charge_with_power_factor(power_factor)

    assert solar_charge.get_charger_power_factor() == power_factor


@pytest.mark.parametrize(
    "power_factor",
    [
        pytest.param(-5.0, id="negative"),
        pytest.param(0.0, id="exactly_zero_is_not_physically_meaningful"),
        pytest.param(1.0001, id="just_above_one"),
        pytest.param(50.0, id="way_above_one"),
    ],
)
def test_get_charger_power_factor_rejects_out_of_range_values(
    power_factor: float,
) -> None:
    """0 (no active power at all) and anything above 1 are both rejected.

    Regression test for a chained-comparison bug: the guard used to read
    `if 0 > power_factor > 1:`, which Python parses as
    `(0 > power_factor) and (power_factor > 1)` -- impossible for any real
    number, so it could never actually raise for any input, including these.
    """
    solar_charge = _make_solar_charge_with_power_factor(power_factor)

    with pytest.raises(ValueError, match="Invalid charger power factor"):
        solar_charge.get_charger_power_factor()


# ----------------------------------------------------------------------------
# get_allowed_current_variation() / get_allowed_power_variation()
# ----------------------------------------------------------------------------
def test_get_allowed_current_variation_is_a_percentage_of_max_current() -> None:
    """5% (CURRENT_VARIATION_PERCENTAGE) of max current, not a fixed amp value."""
    solar_charge = make_bare_solar_charge(charger=make_fake_charger(max_current=15))

    assert solar_charge.get_allowed_current_variation() == pytest.approx(0.75)


def test_get_allowed_power_variation_is_a_percentage_of_max_real_power() -> None:
    """5% of max_current * voltage * power_factor."""
    solar_charge = make_bare_solar_charge(charger=make_fake_charger(max_current=15))
    solar_charge.get_charger_effective_voltage = lambda: 230.0
    solar_charge.get_charger_power_factor = lambda: 1.0

    # max_real_power = 15 * 230 * 1 = 3450; 5% of that = 172.5
    assert solar_charge.get_allowed_power_variation() == pytest.approx(172.5)


# ----------------------------------------------------------------------------
# get_adjusted_activation_power() -- the pause/resume threshold picks the right sign
# ----------------------------------------------------------------------------
def _make_solar_charge_for_activation_power() -> SolarCharge:
    solar_charge = make_bare_solar_charge()
    solar_charge.get_charger_min_workable_current = lambda: 15.0
    solar_charge.get_charger_effective_voltage = lambda: 230.0
    solar_charge.get_charger_power_factor = lambda: 1.0
    solar_charge.get_charger_min_workable_power_pause_charge_threshold = lambda: -10.0
    solar_charge.get_charger_min_workable_power_resume_charge_threshold = lambda: -5.0
    return solar_charge


def test_adjusted_activation_power_while_charging_uses_the_pause_threshold() -> None:
    """Entering pause (from CHARGE) uses the pause threshold, raising the bar to stop."""
    solar_charge = _make_solar_charge_for_activation_power()

    adjusted, activation = solar_charge.get_adjusted_activation_power(RunState.CHARGE)

    # activation_power = 15 * 230 * 1 * -1 = -3450
    assert activation == pytest.approx(-3450.0)
    # adjusted = -3450 * (100 - 10) / 100
    assert adjusted == pytest.approx(-3105.0)


def test_adjusted_activation_power_while_paused_uses_the_resume_threshold() -> None:
    """Exiting pause uses the resume threshold instead, a different bar to restart."""
    solar_charge = _make_solar_charge_for_activation_power()

    adjusted, activation = solar_charge.get_adjusted_activation_power(RunState.PAUSE)

    assert activation == pytest.approx(-3450.0)
    # adjusted = -3450 * (100 - 5) / 100
    assert adjusted == pytest.approx(-3277.5)


def test_adjusted_activation_power_for_any_non_pause_state_uses_the_pause_threshold() -> (
    None
):
    """SELF_DEPOWER (a CHARGE sub-state) is not treated as PAUSE for this threshold choice."""
    solar_charge = _make_solar_charge_for_activation_power()

    adjusted, _ = solar_charge.get_adjusted_activation_power(RunState.SELF_DEPOWER)

    assert adjusted == pytest.approx(-3105.0)


# ----------------------------------------------------------------------------
# _is_median_net_allocated_power_more_than_min_workable_power()
# ----------------------------------------------------------------------------
def _make_solar_charge_for_power_check(adjusted_activation_power: float) -> SolarCharge:
    solar_charge = make_bare_solar_charge()
    solar_charge.get_adjusted_activation_power = lambda run_state: (
        adjusted_activation_power,
        adjusted_activation_power,
    )
    return solar_charge


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            make_ready_median_data(
                median_value=-500, last_value=-500, window_seconds=0
            ),
            id="monitoring_window_disabled",
        ),
        pytest.param(
            make_ready_median_data(
                median_value=-500, last_value=-500, data_set_ready=False
            ),
            id="data_set_not_ready_yet",
        ),
    ],
)
def test_median_power_check_returns_none_when_not_enough_data(data: MedianData) -> None:
    """No usable data (window off, or not enough samples yet) means 'unknown', not False."""
    solar_charge = _make_solar_charge_for_power_check(adjusted_activation_power=-3105.0)

    assert (
        solar_charge._is_median_net_allocated_power_more_than_min_workable_power(
            data, RunState.CHARGE
        )
        is None
    )


@pytest.mark.parametrize(
    ("median_value", "expected"),
    [
        pytest.param(-4000, True, id="more_surplus_than_needed_to_resume"),
        pytest.param(-1000, False, id="not_enough_surplus_to_resume"),
    ],
)
def test_median_power_check_while_paused_only_looks_at_the_median(
    median_value: float, expected: bool
) -> None:
    """Resuming from pause only trusts the smoothed median, not the noisy realtime value."""
    solar_charge = _make_solar_charge_for_power_check(adjusted_activation_power=-3105.0)
    data = make_ready_median_data(median_value=median_value, last_value=-1000)

    result = solar_charge._is_median_net_allocated_power_more_than_min_workable_power(
        data, RunState.PAUSE
    )

    assert result is expected


def test_median_power_check_while_charging_median_alone_is_enough() -> None:
    """While charging, a sufficient median alone is enough to say 'keep going'."""
    solar_charge = _make_solar_charge_for_power_check(adjusted_activation_power=-3105.0)
    data = make_ready_median_data(median_value=-4000, last_value=-1000)

    result = solar_charge._is_median_net_allocated_power_more_than_min_workable_power(
        data, RunState.CHARGE
    )

    assert result is True


def test_median_power_check_while_charging_a_realtime_surplus_also_counts() -> None:
    """A realtime spike counts too, making it harder to pause than to resume.

    Median alone is insufficient here, but the realtime last data point is --
    that asymmetry (checked only while charging, not while paused) is
    deliberate per the source comment: it makes it harder to enter pause
    than to exit it.
    """
    solar_charge = _make_solar_charge_for_power_check(adjusted_activation_power=-3105.0)
    data = make_ready_median_data(median_value=-1000, last_value=-4000)

    result = solar_charge._is_median_net_allocated_power_more_than_min_workable_power(
        data, RunState.CHARGE
    )

    assert result is True


def test_median_power_check_while_charging_neither_value_is_enough() -> None:
    """Both the median and the realtime value fall short: not enough power."""
    solar_charge = _make_solar_charge_for_power_check(adjusted_activation_power=-3105.0)
    data = make_ready_median_data(median_value=-1000, last_value=-1000)

    result = solar_charge._is_median_net_allocated_power_more_than_min_workable_power(
        data, RunState.CHARGE
    )

    assert result is False


# ----------------------------------------------------------------------------
# is_max_speed_charge() / _is_allow_pause_state()
# ----------------------------------------------------------------------------
def _make_solar_charge_for_max_speed(
    *,
    max_current: float = 15.0,
    min_current: float = 5.0,
    running_goal: ScheduleData | None = None,
    fast_charge_mode: bool = False,
    calibrate: bool = False,
) -> SolarCharge:
    solar_charge = make_bare_solar_charge(running_goal=running_goal)
    solar_charge.get_charger_max_current = lambda: max_current
    solar_charge.get_charger_min_current = lambda _max_current: min_current
    solar_charge.is_fast_charge_mode = lambda: fast_charge_mode
    solar_charge.is_calibrate_max_charge_speed = lambda: calibrate
    return solar_charge


def test_max_speed_charge_true_when_device_is_binary_only() -> None:
    """min_current == max_current (eg. the Hot Water element) always counts as max speed."""
    solar_charge = _make_solar_charge_for_max_speed(max_current=15.0, min_current=15.0)

    assert solar_charge.is_max_speed_charge() is True


def test_max_speed_charge_false_with_no_overriding_condition() -> None:
    """A device with a real current range and no active override is not at max speed."""
    solar_charge = _make_solar_charge_for_max_speed(max_current=15.0, min_current=5.0)

    assert solar_charge.is_max_speed_charge() is False


def test_max_speed_charge_true_when_racing_a_charge_deadline() -> None:
    """A charge-endtime deadline that requires max charge now overrides everything."""
    goal = ScheduleData(
        weekly_schedule=[], has_charge_endtime=True, max_charge_now=True
    )
    solar_charge = _make_solar_charge_for_max_speed(running_goal=goal)

    assert solar_charge.is_max_speed_charge() is True


def test_max_speed_charge_false_when_charge_endtime_set_but_not_yet_urgent() -> None:
    """A charge-endtime goal that hasn't yet hit max_charge_now does not force max speed."""
    goal = ScheduleData(
        weekly_schedule=[], has_charge_endtime=True, max_charge_now=False
    )
    solar_charge = _make_solar_charge_for_max_speed(running_goal=goal)

    assert solar_charge.is_max_speed_charge() is False


def test_max_speed_charge_true_in_fast_charge_mode() -> None:
    """The user's fast-charge-mode switch forces max speed."""
    solar_charge = _make_solar_charge_for_max_speed(fast_charge_mode=True)

    assert solar_charge.is_max_speed_charge() is True


def test_max_speed_charge_true_while_calibrating() -> None:
    """Calibrating max charge speed needs max current by definition."""
    solar_charge = _make_solar_charge_for_max_speed(calibrate=True)

    assert solar_charge.is_max_speed_charge() is True


def test_allow_pause_state_false_when_power_monitoring_is_off() -> None:
    """No monitor window configured means pausing is never considered."""
    solar_charge = make_bare_solar_charge(power_monitor_duration=0.0)

    assert solar_charge._is_allow_pause_state() is False


def test_allow_pause_state_true_when_monitoring_on_and_not_at_max_speed() -> None:
    """Monitoring on, and not forced to max speed: pausing is allowed."""
    solar_charge = make_bare_solar_charge(power_monitor_duration=300.0)
    solar_charge.is_max_speed_charge = lambda: False

    assert solar_charge._is_allow_pause_state() is True


def test_allow_pause_state_false_when_at_max_speed_even_with_monitoring_on() -> None:
    """Max-speed charging overrides monitoring: never pause while racing a deadline."""
    solar_charge = make_bare_solar_charge(power_monitor_duration=300.0)
    solar_charge.is_max_speed_charge = lambda: True

    assert solar_charge._is_allow_pause_state() is False


# ----------------------------------------------------------------------------
# get_charge_current() -- falls back to max current for devices that can't report it
# ----------------------------------------------------------------------------
def make_fake_current_reporting_charger(
    *, entity_id: str | None, value: float | None
) -> SimpleNamespace:
    """A charger whose get_charge_current() fills in val_dict like the real base class does."""

    def get_charge_current(val_dict: object) -> float | None:
        val_dict.config_values["charger_get_charge_current"] = ConfigValue(
            "charger_get_charge_current", entity_id, value
        )
        return value

    return SimpleNamespace(get_charge_current=get_charge_current)


def test_get_charge_current_reports_the_chargers_own_reading() -> None:
    """A device that can report its own current uses that value, not max current."""
    solar_charge = make_bare_solar_charge(charger=make_fake_charger(max_current=15.0))
    charger = make_fake_current_reporting_charger(
        entity_id="number.reported_current", value=7.5
    )

    assert solar_charge.get_charge_current(charger) == 7.5


def test_get_charge_current_falls_back_to_max_current_for_a_resistive_load() -> None:
    """No configured current-reading entity: assume it's drawing its full rated current."""
    solar_charge = make_bare_solar_charge(charger=make_fake_charger(max_current=15.0))
    charger = make_fake_current_reporting_charger(entity_id=None, value=None)

    assert solar_charge.get_charge_current(charger) == 15.0


def test_get_charge_current_raises_when_configured_but_unavailable() -> None:
    """A configured reading entity that returns nothing is an error, not a silent 0."""
    solar_charge = make_bare_solar_charge(charger=make_fake_charger(max_current=15.0))
    charger = make_fake_current_reporting_charger(
        entity_id="number.reported_current", value=None
    )

    with pytest.raises(ValueError, match="Failed to get device charge current"):
        solar_charge.get_charge_current(charger)


# ----------------------------------------------------------------------------
# async_set_charge_limit_if_required()
# ----------------------------------------------------------------------------
def make_goal_for_charge_limit(
    *, old_charge_limit: float, new_charge_limit: float, next_charge_limit: float | None
) -> ScheduleData:
    """Build a ScheduleData carrying just the charge-limit fields the method under test reads."""
    return ScheduleData(
        weekly_schedule=[
            ChargeSchedule(
                charge_day="Monday", charge_limit=0, charge_end_time=time.min
            )
        ],
        day_index=0,
        old_charge_limit=old_charge_limit,
        new_charge_limit=new_charge_limit,
        next_charge_limit=next_charge_limit,
    )


async def test_set_charge_limit_if_required_noop_when_unchanged() -> None:
    """No difference between old and new charge limit: nothing is set."""
    solar_charge = make_bare_solar_charge()
    solar_charge.async_set_charge_limit = AsyncMock()
    goal = make_goal_for_charge_limit(
        old_charge_limit=80, new_charge_limit=80, next_charge_limit=None
    )

    changed = await solar_charge.async_set_charge_limit_if_required(None, goal)

    assert changed is False
    solar_charge.async_set_charge_limit.assert_not_awaited()


async def test_set_charge_limit_if_required_applies_the_new_limit() -> None:
    """A changed charge limit is applied via async_set_charge_limit()."""
    solar_charge = make_bare_solar_charge()
    solar_charge.async_set_charge_limit = AsyncMock()
    goal = make_goal_for_charge_limit(
        old_charge_limit=70, new_charge_limit=80, next_charge_limit=None
    )

    changed = await solar_charge.async_set_charge_limit_if_required("chargeable", goal)

    assert changed is True
    solar_charge.async_set_charge_limit.assert_awaited_once_with("chargeable", 80)


async def test_set_charge_limit_if_required_next_charge_limit_takes_priority() -> None:
    """A look-ahead next_charge_limit overrides new_charge_limit as the target."""
    solar_charge = make_bare_solar_charge()
    solar_charge.async_set_charge_limit = AsyncMock()
    goal = make_goal_for_charge_limit(
        old_charge_limit=70, new_charge_limit=80, next_charge_limit=90
    )

    changed = await solar_charge.async_set_charge_limit_if_required("chargeable", goal)

    assert changed is True
    solar_charge.async_set_charge_limit.assert_awaited_once_with("chargeable", 90)


async def test_set_charge_limit_if_required_next_charge_limit_can_also_mean_no_change() -> (
    None
):
    """If next_charge_limit already equals old_charge_limit, that also counts as unchanged."""
    solar_charge = make_bare_solar_charge()
    solar_charge.async_set_charge_limit = AsyncMock()
    goal = make_goal_for_charge_limit(
        old_charge_limit=70, new_charge_limit=80, next_charge_limit=70
    )

    changed = await solar_charge.async_set_charge_limit_if_required("chargeable", goal)

    assert changed is False
    solar_charge.async_set_charge_limit.assert_not_awaited()


# ----------------------------------------------------------------------------
# is_below_charge_limit() -- fails open, never blocks a session on an error
# ----------------------------------------------------------------------------
def make_fake_soc_chargeable(
    *,
    charge_limit: float | None = 80.0,
    soc_entity_id: str | None = "sensor.soc",
    soc: float | None = 50.0,
    raise_on_charge_limit: Exception | None = None,
    raise_on_soc: Exception | None = None,
) -> SimpleNamespace:
    """A chargeable whose get_state_of_charge() fills in val_dict like the real base class does."""

    def get_charge_limit() -> float | None:
        if raise_on_charge_limit:
            raise raise_on_charge_limit
        return charge_limit

    def get_state_of_charge(val_dict: object) -> float | None:
        if raise_on_soc:
            raise raise_on_soc
        val_dict.config_values["device_soc_sensor"] = ConfigValue(
            "device_soc_sensor", soc_entity_id, soc
        )
        return soc

    return SimpleNamespace(
        get_charge_limit=get_charge_limit, get_state_of_charge=get_state_of_charge
    )


def test_below_charge_limit_true_without_a_configured_soc_sensor() -> None:
    """No SOC sensor at all: assume it's fine to keep charging."""
    solar_charge = make_bare_solar_charge()
    chargeable = make_fake_soc_chargeable(soc_entity_id=None, soc=None)

    assert solar_charge.is_below_charge_limit(chargeable) is True


def test_below_charge_limit_true_when_soc_has_room_left() -> None:
    """SOC below the configured limit: still below."""
    solar_charge = make_bare_solar_charge()
    chargeable = make_fake_soc_chargeable(charge_limit=80.0, soc=50.0)

    assert solar_charge.is_below_charge_limit(chargeable) is True


def test_below_charge_limit_false_when_soc_has_reached_the_limit() -> None:
    """SOC at or above the configured limit: no longer below."""
    solar_charge = make_bare_solar_charge()
    chargeable = make_fake_soc_chargeable(charge_limit=80.0, soc=80.0)

    assert solar_charge.is_below_charge_limit(chargeable) is False


def test_below_charge_limit_fails_open_when_charge_limit_lookup_errors() -> None:
    """An error reading the charge limit is swallowed, defaulting to 'keep charging'."""
    solar_charge = make_bare_solar_charge()
    chargeable = make_fake_soc_chargeable(raise_on_charge_limit=RuntimeError("boom"))

    assert solar_charge.is_below_charge_limit(chargeable) is True


def test_below_charge_limit_fails_open_on_soc_timeout() -> None:
    """A timeout reading SOC is a distinct, separately-caught case, also failing open."""
    solar_charge = make_bare_solar_charge()
    chargeable = make_fake_soc_chargeable(raise_on_soc=TimeoutError("slow device"))

    assert solar_charge.is_below_charge_limit(chargeable) is True


# ----------------------------------------------------------------------------
# abort_if_exceed_max_consecutive_failure()
# ----------------------------------------------------------------------------
def test_abort_if_exceed_max_consecutive_failure_allows_up_to_the_threshold() -> None:
    """Exactly at the threshold does not abort -- the check is strictly greater-than."""
    solar_charge = make_bare_solar_charge(
        stats=ChargeStats(loop_consecutive_fail_count=MAX_CONSECUTIVE_FAILURE_COUNT)
    )
    solar_charge._machine_state = SimpleNamespace(state=RunState.CHARGE)

    solar_charge.abort_if_exceed_max_consecutive_failure()  # must not raise


def test_abort_if_exceed_max_consecutive_failure_raises_past_the_threshold() -> None:
    """One failure past the threshold aborts the whole session state."""
    solar_charge = make_bare_solar_charge(
        stats=ChargeStats(loop_consecutive_fail_count=MAX_CONSECUTIVE_FAILURE_COUNT + 1)
    )
    solar_charge._machine_state = SimpleNamespace(state=RunState.CHARGE)

    with pytest.raises(RuntimeError, match="Exceeded max number of allowable"):
        solar_charge.abort_if_exceed_max_consecutive_failure()


# ----------------------------------------------------------------------------
# _set_is_continue_charge_state() -- the actual charge/pause/end decision
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "context_overrides",
    [
        pytest.param({"connected": False}, id="not_connected"),
        pytest.param({"below_charge_limit": False}, id="at_or_above_charge_limit"),
        pytest.param(
            {"end_on_condition": True, "exit_condition": True}, id="exit_condition_met"
        ),
        pytest.param(
            {"loop_success_count": 1, "charging": False},
            id="stopped_charging_after_first_successful_loop",
        ),
        pytest.param(
            {"sun_trigger": True, "sun_above_start_end_elevations": False},
            id="sun_below_trigger_with_no_override",
        ),
    ],
)
def test_continue_charge_state_ends_the_session_when_a_gate_fails(
    context_overrides: dict[str, object],
) -> None:
    """Any one of these conditions failing ends the charge session outright."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: False
    context = make_context(**context_overrides)

    solar_charge._set_is_continue_charge_state(context)

    assert context.next_step is ChargeStatus.CHARGE_END
    assert context.continue_state is False


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"fast_charge": True}, id="fast_charge_overrides_sun_gate"),
        pytest.param(
            {"calibrate_max_charge_speed": True}, id="calibration_overrides_sun_gate"
        ),
        pytest.param(
            {"has_charge_endtime": True, "max_charge_now": True},
            id="charge_deadline_overrides_sun_gate",
        ),
    ],
)
def test_continue_charge_state_sun_gate_has_overrides(
    override: dict[str, object],
) -> None:
    """Fast charge, calibration or an urgent deadline all bypass the sun-elevation gate."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: False
    context = make_context(
        sun_trigger=True, sun_above_start_end_elevations=False, **override
    )

    solar_charge._set_is_continue_charge_state(context)

    assert context.next_step is ChargeStatus.CHARGE_CONTINUE
    assert context.continue_state is True


def test_continue_charge_state_first_loop_continues_even_if_not_yet_charging() -> None:
    """The very first loop iteration is exempt from the 'must already be charging' gate."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: False
    context = make_context(loop_success_count=0, charging=False)

    solar_charge._set_is_continue_charge_state(context)

    assert context.next_step is ChargeStatus.CHARGE_CONTINUE


def test_continue_charge_state_skips_the_power_check_when_pausing_is_not_allowed() -> (
    None
):
    """With pausing disallowed, the power-sufficiency check is never even consulted."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: False

    def _fail_if_called(*_args: object) -> bool:
        raise AssertionError("should not be called when pausing is not allowed")

    solar_charge._is_median_net_allocated_power_more_than_min_workable_power = (
        _fail_if_called
    )
    context = make_context()

    solar_charge._set_is_continue_charge_state(context)

    assert context.next_step is ChargeStatus.CHARGE_CONTINUE


@pytest.mark.parametrize(
    ("enough_power", "expected_next_step"),
    [
        pytest.param(False, ChargeStatus.CHARGE_PAUSE, id="not_enough_power_pauses"),
        pytest.param(
            None, ChargeStatus.CHARGE_CONTINUE, id="unknown_data_keeps_charging"
        ),
        pytest.param(
            True, ChargeStatus.CHARGE_CONTINUE, id="enough_power_keeps_charging"
        ),
    ],
)
def test_continue_charge_state_pause_decision_when_monitoring_enabled(
    enough_power: bool | None, expected_next_step: ChargeStatus
) -> None:
    """Only a definite 'not enough power' (False, not None) triggers a pause."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: True
    solar_charge._is_median_net_allocated_power_more_than_min_workable_power = (
        lambda *_args: enough_power
    )
    context = make_context()

    solar_charge._set_is_continue_charge_state(context)

    assert context.next_step is expected_next_step


# ----------------------------------------------------------------------------
# _set_is_continue_pause_state() -- the inverse decision while already paused
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "context_overrides",
    [
        pytest.param({"connected": False}, id="not_connected"),
        pytest.param({"below_charge_limit": False}, id="at_or_above_charge_limit"),
        pytest.param(
            {"end_on_condition": True, "exit_condition": True}, id="exit_condition_met"
        ),
        pytest.param(
            {"sun_trigger": True, "sun_above_start_end_elevations": False},
            id="sun_below_trigger",
        ),
        pytest.param({"fast_charge": True}, id="fast_charge_forces_a_resume"),
        pytest.param(
            {"calibrate_max_charge_speed": True}, id="calibration_forces_a_resume"
        ),
        pytest.param(
            {"has_charge_endtime": True, "max_charge_now": True},
            id="charge_deadline_forces_a_resume",
        ),
    ],
)
def test_continue_pause_state_resumes_immediately_when_a_stay_paused_condition_fails(
    context_overrides: dict[str, object],
) -> None:
    """Any condition required to justify staying paused failing resumes charging at once.

    Unlike the charge-state gates (which end the session), failing here just
    means 'exit pause' (CHARGE_CONTINUE) -- pausing was never mandatory in
    the first place, only permitted when conditions actively call for it.
    """
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: True
    context = make_context(state=RunState.PAUSE, **context_overrides)

    solar_charge._set_is_continue_pause_state(context)

    assert context.next_step is ChargeStatus.CHARGE_CONTINUE
    assert context.continue_state is False


def test_continue_pause_state_exits_pause_when_pausing_is_no_longer_allowed() -> None:
    """If monitoring got turned off (or max-speed kicked in) mid-pause, resume immediately."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: False
    context = make_context(state=RunState.PAUSE)

    solar_charge._set_is_continue_pause_state(context)

    assert context.next_step is ChargeStatus.CHARGE_CONTINUE
    assert context.continue_state is False


@pytest.mark.parametrize(
    ("enough_power", "expected_continue_state"),
    [
        pytest.param(False, True, id="still_not_enough_power_stays_paused"),
        pytest.param(None, True, id="unknown_data_stays_paused_conservatively"),
    ],
)
def test_continue_pause_state_stays_paused_without_a_confirmed_surplus(
    enough_power: bool | None, expected_continue_state: bool
) -> None:
    """Staying paused is the conservative default: only a confirmed surplus ends it.

    Note the asymmetry with the charge-state equivalent: there, unknown data
    (None) keeps charging; here, unknown data keeps it paused. Both are
    "don't change behavior on uncertain data" -- it just reads differently
    because CHARGE_CONTINUE means something different in each state.
    """
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: True
    solar_charge._is_median_net_allocated_power_more_than_min_workable_power = (
        lambda *_args: enough_power
    )
    context = make_context(state=RunState.PAUSE)

    solar_charge._set_is_continue_pause_state(context)

    assert context.next_step is ChargeStatus.CHARGE_PAUSE
    assert context.continue_state is expected_continue_state


def test_continue_pause_state_resumes_once_a_surplus_is_confirmed() -> None:
    """A confirmed surplus (True) is the only thing that actually ends the pause."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: True
    solar_charge._is_median_net_allocated_power_more_than_min_workable_power = (
        lambda *_args: True
    )
    context = make_context(state=RunState.PAUSE)

    solar_charge._set_is_continue_pause_state(context)

    assert context.next_step is ChargeStatus.CHARGE_CONTINUE
    assert context.continue_state is False


# ----------------------------------------------------------------------------
# _set_is_continue_state() -- dispatches to the two handlers above by run state
# ----------------------------------------------------------------------------
def test_set_is_continue_state_dispatches_charge_state_to_the_charge_handler() -> None:
    """RunState.CHARGE is routed to _set_is_continue_charge_state()."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: False
    context = make_context(state=RunState.CHARGE, connected=False)

    solar_charge._set_is_continue_state(context)

    assert context.next_step is ChargeStatus.CHARGE_END  # the charge-state gate fired


def test_set_is_continue_state_dispatches_pause_state_to_the_pause_handler() -> None:
    """RunState.PAUSE is routed to _set_is_continue_pause_state()."""
    solar_charge = make_bare_solar_charge()
    solar_charge._is_allow_pause_state = lambda: False
    context = make_context(state=RunState.PAUSE)

    solar_charge._set_is_continue_state(context)

    assert (
        context.next_step is ChargeStatus.CHARGE_CONTINUE
    )  # the pause-state gate fired


def test_set_is_continue_state_leaves_context_untouched_for_other_states() -> None:
    """Any other run state (eg. START, INITIALISE) is not this method's concern."""
    solar_charge = make_bare_solar_charge()
    context = make_context(state=RunState.START)
    context.next_step = ChargeStatus.CHARGE_END  # sentinel: must stay untouched

    solar_charge._set_is_continue_state(context)

    assert context.next_step is ChargeStatus.CHARGE_END
