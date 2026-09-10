# ruff: noqa: SLF001
"""Unit tests for StateStart (state_machine/state_start.py).

StateStart is the session-init state: before any device wake-up happens (that
is StateInitialise's job), it decides whether this session was triggered by
the scheduled timer, resets per-session counters, sets up the sliding-window
power-monitor data structure, and subscribes to allocated-power updates. That
sliding window is also where the only real statistics in this file live --
median/SMA of net allocated power over a rolling time window, with hysteresis
between "ready" and "not ready" -- so it gets the most direct coverage below.

As with test_state_charge.py, a lightweight fake SolarCharge stands in for
the real one: StateStart's own methods are what's under test, and the
SolarCharge methods they call (get_local_datetime(), set_net_allocated_power(),
...) are simple, already-understood primitives that don't need re-driving
through real HA entity state to verify StateStart's own logic.
"""

from datetime import datetime, timedelta
import logging
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from custom_components.solarcharger.const import RunState
from custom_components.solarcharger.models.model_median_data import (
    MedianData,
    MedianDataPoint,
)
from custom_components.solarcharger.state_machine.state_initialise import (
    StateInitialise,
)
from custom_components.solarcharger.state_machine.state_start import StateStart
import pytest

ANCHOR_NOW = datetime(2026, 1, 5, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
WINDOW_SECONDS = 300.0  # 5-minute power-monitor window used throughout


# ----------------------------------------------------------------------------
def make_fake_solarcharge(**overrides: object) -> SimpleNamespace:
    """Stand-in for SolarCharge, covering everything StateStart's methods touch.

    set_median_data_ready()/set_median_data_not_ready() mutate data_set_ready
    on the given MedianData, mirroring the real SolarCharge methods (which
    also update an HA sensor) -- that side effect is what _set_median_data_state()
    itself relies on, so a bare no-op Mock would make its own guard clauses
    untestable.
    """

    def _set_ready(data: MedianData) -> None:
        data.data_set_ready = True

    def _set_not_ready(data: MedianData) -> None:
        data.data_set_ready = False

    defaults: dict[str, object] = {
        "caller": "hot_water",
        "next_charge_time_trigger_entity_id": "datetime.next_charge_time",
        "get_datetime": Mock(return_value=None),
        "get_local_datetime": Mock(return_value=ANCHOR_NOW),
        "get_power_monitor_duration": Mock(return_value=5.0),
        "can_set_charge_current": Mock(return_value=False),
        "set_consumed_power": Mock(),
        "set_median_data_not_ready": Mock(side_effect=_set_not_ready),
        "set_median_data_ready": Mock(side_effect=_set_ready),
        "set_pause_stats": Mock(),
        "give_up_real_power_allocation": Mock(),
        "set_net_allocated_power": Mock(),
        "set_net_allocated_power_sample_size": Mock(),
        "set_median_net_allocated_power": Mock(),
        "set_median_net_allocated_power_period": Mock(),
        "set_sma_net_allocated_power": Mock(),
        "set_run_state": Mock(),
        "set_machine_state": Mock(),
        "tracker": SimpleNamespace(track_delta_allocated_power_update=Mock()),
        "power_monitor_duration": 0.0,
        "net_allocations": None,
        "session_start_time": None,
        "session_triggered_by_timer": False,
        "starting_goal": None,
        "running_goal": None,
        "can_set_current": False,
        "started_calibrate_max_charge_speed": False,
        "started_max_charge": 0,
        "stats": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_state_start(fake_solar_charge: SimpleNamespace) -> StateStart:
    """Build a StateStart pointed at the given fake SolarCharge context."""
    state = StateStart()
    state.solarcharge = fake_solar_charge  # type: ignore[assignment]
    return state


def make_median_data(**overrides: object) -> MedianData:
    """Build a MedianData with a standard 5-minute window, overridden per test."""
    defaults: dict[str, object] = {
        "window_seconds": WINDOW_SECONDS,
        "window_duration": timedelta(seconds=WINDOW_SECONDS),
        "sequence": [],
    }
    defaults.update(overrides)
    return MedianData(**defaults)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# _is_session_triggered_by_timer() -- was this session started by the scheduler?
# ----------------------------------------------------------------------------
def test_not_triggered_by_timer_when_no_next_charge_time_configured() -> None:
    """No next-charge-time entity value at all means not timer-triggered."""
    fake = make_fake_solarcharge(get_datetime=Mock(return_value=None))
    state = make_state_start(fake)

    assert state._is_session_triggered_by_timer(ANCHOR_NOW) is False


@pytest.mark.parametrize(
    ("seconds_before_now", "expected"),
    [
        pytest.param(0, True, id="exact_match"),
        pytest.param(-15, True, id="15s_after_next_charge_time"),
        pytest.param(15, True, id="15s_before_next_charge_time"),
        pytest.param(30, False, id="exactly_30s_before_is_not_within"),
        pytest.param(-30, False, id="exactly_30s_after_is_not_within"),
        pytest.param(120, False, id="2_minutes_away"),
    ],
)
def test_triggered_by_timer_within_30_seconds_of_next_charge_time(
    seconds_before_now: int, expected: bool
) -> None:
    """Within (strictly less than) 30 seconds of the scheduled time counts as timer-triggered."""
    next_charge_time = ANCHOR_NOW - timedelta(seconds=seconds_before_now)
    fake = make_fake_solarcharge(get_datetime=Mock(return_value=next_charge_time))
    state = make_state_start(fake)

    assert state._is_session_triggered_by_timer(ANCHOR_NOW) is expected


# ----------------------------------------------------------------------------
# _calculate_median_value() / _calculate_median_period() / _calculate_sma_value()
# ----------------------------------------------------------------------------
def test_median_value_odd_sample_size_is_the_middle_value() -> None:
    """Three points: median is the middle one once sorted, not an average."""
    state = make_state_start(make_fake_solarcharge())
    data = make_median_data(
        sequence=[
            MedianDataPoint(value=30, period=1, time=ANCHOR_NOW),
            MedianDataPoint(value=10, period=1, time=ANCHOR_NOW),
            MedianDataPoint(value=20, period=1, time=ANCHOR_NOW),
        ]
    )

    state._calculate_median_value(data)

    assert data.median_value == 20


def test_median_value_even_sample_size_averages_the_two_middle_values() -> None:
    """Four points: median is the average of the two middle values once sorted."""
    state = make_state_start(make_fake_solarcharge())
    data = make_median_data(
        sequence=[
            MedianDataPoint(value=10, period=1, time=ANCHOR_NOW),
            MedianDataPoint(value=40, period=1, time=ANCHOR_NOW),
            MedianDataPoint(value=20, period=1, time=ANCHOR_NOW),
            MedianDataPoint(value=30, period=1, time=ANCHOR_NOW),
        ]
    )

    state._calculate_median_value(data)

    assert data.median_value == 25  # (20 + 30) / 2


def test_median_period_uses_the_same_odd_even_logic_on_period() -> None:
    """Median period mirrors median value's logic, but sorts/picks on .period."""
    state = make_state_start(make_fake_solarcharge())
    data = make_median_data(
        sequence=[
            MedianDataPoint(value=0, period=90, time=ANCHOR_NOW),
            MedianDataPoint(value=0, period=30, time=ANCHOR_NOW),
            MedianDataPoint(value=0, period=60, time=ANCHOR_NOW),
        ]
    )

    state._calculate_median_period(data)

    assert data.median_period == 60


def test_sma_value_is_the_plain_average_of_all_values() -> None:
    """SMA is just sum/count -- uses data.sample_size, not len(sequence)."""
    state = make_state_start(make_fake_solarcharge())
    data = make_median_data(
        sequence=[
            MedianDataPoint(value=10, period=1, time=ANCHOR_NOW),
            MedianDataPoint(value=20, period=1, time=ANCHOR_NOW),
            MedianDataPoint(value=30, period=1, time=ANCHOR_NOW),
        ],
        sample_size=3,
    )

    state._calculate_sma_value(data)

    assert data.sma_value == 20


# ----------------------------------------------------------------------------
# _is_median_data_ready() -- 80% of window duration, per DELTA_POWER_MONITOR_DURATION
# ----------------------------------------------------------------------------
def test_median_data_ready_at_80_percent_of_window() -> None:
    """Exactly the 80% threshold counts as ready (boundary is inclusive)."""
    state = make_state_start(make_fake_solarcharge())
    data = make_median_data(sample_duration=timedelta(seconds=WINDOW_SECONDS * 0.8))

    assert state._is_median_data_ready(data) is True


def test_median_data_not_ready_just_below_80_percent_of_window() -> None:
    """Just under the 80% threshold is not ready."""
    state = make_state_start(make_fake_solarcharge())
    data = make_median_data(sample_duration=timedelta(seconds=WINDOW_SECONDS * 0.8 - 1))

    assert state._is_median_data_ready(data) is False


# ----------------------------------------------------------------------------
# _set_median_data_state() -- ready/not-ready hysteresis and max_sample_size tracking
# ----------------------------------------------------------------------------
def test_set_median_data_state_noop_when_nothing_was_removed() -> None:
    """No data pruned this update means no ready/not-ready re-evaluation at all."""
    fake = make_fake_solarcharge()
    state = make_state_start(fake)
    data = make_median_data(
        data_set_ready=False,
        max_sample_size=-1,
        sample_size=3,
        sample_duration=timedelta(seconds=90),
    )

    state._set_median_data_state(data, removed_old_data=False)

    fake.set_median_data_ready.assert_not_called()
    fake.set_median_data_not_ready.assert_not_called()
    assert data.data_set_ready is False
    assert data.max_sample_size == -1


def test_set_median_data_state_becomes_ready_sets_initial_max_sample_size() -> None:
    """Crossing the ready threshold for the first time records the initial max sample size."""
    fake = make_fake_solarcharge()
    state = make_state_start(fake)
    data = make_median_data(
        data_set_ready=False,
        max_sample_size=-1,
        sample_size=5,
        sample_duration=timedelta(seconds=WINDOW_SECONDS * 0.8),
    )

    state._set_median_data_state(data, removed_old_data=True)

    fake.set_median_data_ready.assert_called_once_with(data)
    assert data.data_set_ready is True
    assert data.max_sample_size == 5


def test_set_median_data_state_becoming_ready_again_keeps_prior_max_sample_size() -> (
    None
):
    """A max sample size already recorded from an earlier ready period is not clobbered."""
    fake = make_fake_solarcharge()
    state = make_state_start(fake)
    data = make_median_data(
        data_set_ready=False,
        max_sample_size=8,
        sample_size=5,
        sample_duration=timedelta(seconds=WINDOW_SECONDS * 0.8),
    )

    state._set_median_data_state(data, removed_old_data=True)

    fake.set_median_data_ready.assert_called_once_with(data)
    assert data.max_sample_size == 8


def test_set_median_data_state_stays_not_ready_below_threshold() -> None:
    """Still below the ready threshold: no setter call, stays not ready."""
    fake = make_fake_solarcharge()
    state = make_state_start(fake)
    data = make_median_data(
        data_set_ready=False,
        max_sample_size=-1,
        sample_size=2,
        sample_duration=timedelta(seconds=50),
    )

    state._set_median_data_state(data, removed_old_data=True)

    fake.set_median_data_ready.assert_not_called()
    assert data.data_set_ready is False


def test_set_median_data_state_raises_max_sample_size_while_still_ready() -> None:
    """Already ready and growing: max sample size tracks the new high, no setter call."""
    fake = make_fake_solarcharge()
    state = make_state_start(fake)
    data = make_median_data(
        data_set_ready=True,
        max_sample_size=5,
        sample_size=7,
        sample_duration=timedelta(seconds=WINDOW_SECONDS * 0.8),
    )

    state._set_median_data_state(data, removed_old_data=True)

    assert data.max_sample_size == 7
    fake.set_median_data_ready.assert_not_called()
    fake.set_median_data_not_ready.assert_not_called()


def test_set_median_data_state_drops_to_not_ready_when_sample_shrinks() -> None:
    """Already ready but the sample shrank back below threshold: flips to not ready."""
    fake = make_fake_solarcharge()
    state = make_state_start(fake)
    data = make_median_data(
        data_set_ready=True,
        max_sample_size=10,
        sample_size=2,
        sample_duration=timedelta(seconds=50),
    )

    state._set_median_data_state(data, removed_old_data=True)

    fake.set_median_data_not_ready.assert_called_once_with(data)
    assert data.data_set_ready is False
    # The historical high-water mark is not erased by a temporary dip.
    assert data.max_sample_size == 10


# ----------------------------------------------------------------------------
# _process_net_allocated_power_update() -- append, prune, recompute, push to sensors
# ----------------------------------------------------------------------------
def test_process_update_prunes_points_outside_the_window_and_pushes_sensors() -> None:
    """A point older than the window is dropped before recomputing median/SMA."""
    fake = make_fake_solarcharge(get_local_datetime=Mock(return_value=ANCHOR_NOW))
    state = make_state_start(fake)
    data = make_median_data(
        sequence=[
            MedianDataPoint(
                value=100, period=60, time=ANCHOR_NOW - timedelta(seconds=400)
            ),  # older than the 300s window: pruned
            MedianDataPoint(
                value=200, period=60, time=ANCHOR_NOW - timedelta(seconds=200)
            ),  # still inside the window: kept
        ]
    )
    new_point = MedianDataPoint(value=300, period=60, time=ANCHOR_NOW)

    state._process_net_allocated_power_update(data, new_point)

    assert [point.value for point in data.sequence] == [200, 300]
    assert data.sample_size == 2
    assert data.median_value == 250
    assert data.sma_value == 250
    assert data.median_period == 60
    fake.set_net_allocated_power.assert_called_once_with(300)
    fake.set_net_allocated_power_sample_size.assert_called_once_with(2)
    fake.set_median_net_allocated_power.assert_called_once_with(250)
    fake.set_median_net_allocated_power_period.assert_called_once_with(60)
    fake.set_sma_net_allocated_power.assert_called_once_with(250)
    # 200s of sample duration is below the 240s (80% of 300s) ready threshold.
    fake.set_median_data_ready.assert_not_called()


def test_process_update_first_ever_point_is_its_own_median_and_average() -> None:
    """The very first data point in an empty window is trivially its own median/SMA."""
    fake = make_fake_solarcharge(get_local_datetime=Mock(return_value=ANCHOR_NOW))
    state = make_state_start(fake)
    data = make_median_data(sequence=[])
    point = MedianDataPoint(value=150, period=45, time=ANCHOR_NOW)

    state._process_net_allocated_power_update(data, point)

    assert data.sample_size == 1
    assert data.median_value == 150
    assert data.sma_value == 150
    assert data.median_period == 45
    fake.set_net_allocated_power.assert_called_once_with(150)


# ----------------------------------------------------------------------------
# _init_power_monitor_window() / _init_instance_variables()
# ----------------------------------------------------------------------------
def test_init_power_monitor_window_converts_minutes_to_seconds() -> None:
    """Power monitor duration is configured in minutes but stored/used in seconds."""
    fake = make_fake_solarcharge(get_power_monitor_duration=Mock(return_value=5.0))
    state = make_state_start(fake)

    state._init_power_monitor_window()

    assert fake.power_monitor_duration == 300.0
    assert isinstance(fake.net_allocations, MedianData)
    assert fake.net_allocations.window_seconds == 300.0
    assert fake.net_allocations.window_duration == timedelta(seconds=300.0)
    assert fake.net_allocations.sequence == []
    fake.set_median_data_not_ready.assert_called_once_with(fake.net_allocations)


def test_init_instance_variables_resets_fresh_session_state() -> None:
    """A fresh session starts with clean counters and a newly built power-monitor window."""
    fake = make_fake_solarcharge(
        get_local_datetime=Mock(return_value=ANCHOR_NOW),
        get_datetime=Mock(return_value=None),
        can_set_charge_current=Mock(return_value=True),
        get_power_monitor_duration=Mock(return_value=10.0),
    )
    state = make_state_start(fake)

    state._init_instance_variables()

    assert fake.session_start_time == ANCHOR_NOW
    assert fake.session_triggered_by_timer is False
    assert fake.starting_goal is None
    assert fake.running_goal is None
    assert fake.can_set_current is True
    assert fake.started_calibrate_max_charge_speed is False
    assert fake.started_max_charge == 0
    fake.set_consumed_power.assert_called_once_with(0.0)
    assert fake.power_monitor_duration == 600.0


# ----------------------------------------------------------------------------
# async_activate_state() -- top-level: run state, session init, hand off to StateInitialise
# ----------------------------------------------------------------------------
async def test_async_activate_state_starts_session_and_hands_off_to_initialise() -> (
    None
):
    """Sets RunState.START, subscribes for power allocation, then transitions onward."""
    fake = make_fake_solarcharge(
        get_local_datetime=Mock(return_value=ANCHOR_NOW),
        get_datetime=Mock(return_value=None),
        can_set_charge_current=Mock(return_value=False),
        get_power_monitor_duration=Mock(return_value=1.0),
    )
    state = make_state_start(fake)
    # log_configuration() is debug-log-gated and depends on unrelated ScOptionState
    # entity lookups; stub it out so this test doesn't depend on the ambient log level.
    state.log_configuration = Mock()

    await state.async_activate_state()

    fake.set_run_state.assert_called_once_with(RunState.START)
    fake.give_up_real_power_allocation.assert_called_once()
    fake.tracker.track_delta_allocated_power_update.assert_called_once_with(
        state._async_handle_delta_allocated_power_update
    )
    fake.set_machine_state.assert_called_once()
    assert isinstance(fake.set_machine_state.call_args.args[0], StateInitialise)


def test_log_configuration_is_a_noop_when_debug_logging_disabled() -> None:
    """Sanity check for the assumption the top-level test above relies on."""
    assert not logging.getLogger(
        "custom_components.solarcharger.state_machine.state_start"
    ).isEnabledFor(logging.DEBUG)
