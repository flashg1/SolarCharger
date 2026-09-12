# ruff: noqa: SLF001
"""Unit tests for ChargeController (modules/controller.py).

ChargeController.__init__ constructs a real Tracker and a real SolarCharge
(which itself needs a Tracker, ControlEntities, a Charger and a Chargeable),
so building one for real just to test one guard clause would mean assembling
almost the whole integration's object graph. As with the state-machine tests,
these bypass __init__ via ChargeController.__new__() and wire up small fakes
for _tracker and _solar_charge instead -- the tests are about ChargeController's
own decisions (when to act on an event, when a switch guard blocks a
double-start, when a task needs recreating), not about Tracker or SolarCharge's
own behavior, which belong to their own test modules.

hass.loop.create_task()/hass.async_create_task() are HA's real task-scheduling
entry points; ChargeController uses them as fire-and-forget (it does not await
the result), so the fakes below record the call and close the coroutine
instead of running it, to avoid a stray "coroutine was never awaited" warning
without actually executing unrelated code.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

from custom_components.solarcharger.const import (
    DEFAULT_CHARGE_LIMIT_MAP,
    NUMBER_CHARGE_LIMIT_MONDAY,
    NUMBER_CHARGE_LIMIT_TUESDAY,
    NUMBER_DEFAULT_CHARGE_LIMIT_TUESDAY,
    NUMBER_DEVICE_MAX_CHARGE_LIMIT,
    NUMBER_DEVICE_MIN_CHARGE_LIMIT,
    SENSOR_SYNC_UPDATE,
    WEEKLY_CHARGE_ENDTIMES,
)
from custom_components.solarcharger.models.model_charge_control import (
    ChargeControl,
    ControlEntities,
)
from custom_components.solarcharger.models.model_device_control import DeviceControl
from custom_components.solarcharger.models.model_schedule_data import ScheduleData
import custom_components.solarcharger.modules.controller as controller_module
from custom_components.solarcharger.modules.controller import ChargeController
import pytest

from .conftest import make_config_entry, make_hass, make_subentry

HOT_WATER_SUBENTRY_ID = "hot_water"
ANCHOR_NOW = datetime(2026, 1, 5, 10, 0, 0, tzinfo=ZoneInfo("UTC"))  # Monday


# ----------------------------------------------------------------------------
def _close_coro_and_return(value: object) -> object:
    """Build a side_effect that closes an unawaited coroutine arg and returns value."""

    def _side_effect(coro: object, *args: object, **kwargs: object) -> object:
        coro.close()  # type: ignore[attr-defined]
        return value

    return _side_effect


def make_fake_tracker(**overrides: object) -> SimpleNamespace:
    """Stand-in for Tracker: every subscribe/track call is a recording Mock."""
    defaults: dict[str, object] = {
        "log_state_change": Mock(),
        "track_charger_plugged_in_sensor": Mock(return_value=True),
        "untrack_charger_plugged_in_sensor": Mock(),
        "track_device_presence_sensor": Mock(return_value=True),
        "untrack_device_presence_sensor": Mock(),
        "track_sun_elevation": Mock(),
        "untrack_sun_elevation": Mock(),
        "schedule_next_charge_time": Mock(),
        "unschedule_next_charge_time": Mock(),
        "track_charge_limit_schedule": Mock(return_value=True),
        "track_charge_endtime_schedule": Mock(return_value=True),
        "untrack_charge_limit_schedule": Mock(),
        "untrack_charge_endtime_schedule": Mock(),
        "track_next_charge_time_trigger": Mock(),
        "remove_ha_started_callback": Mock(),
        "track_net_power_update": Mock(return_value=True),
        "track_weather_update": Mock(return_value=True),
        "untrack_weather_update": Mock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_fake_solar_charge(**overrides: object) -> SimpleNamespace:
    """Stand-in for SolarCharge, covering only what ChargeController itself calls."""
    defaults: dict[str, object] = {
        "caller": HOT_WATER_SUBENTRY_ID,
        "is_connected": Mock(return_value=False),
        "async_wake_up_and_update_ha": AsyncMock(),
        "async_get_current_schedule_data": AsyncMock(
            return_value=ScheduleData(weekly_schedule=[])
        ),
        "is_device_at_location_and_connected": Mock(return_value=False),
        "async_stop_calibrate_max_charge_speed": AsyncMock(),
        "async_start_charge_task": AsyncMock(),
        "async_tidy_up": AsyncMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_bare_controller(
    *,
    tracker: SimpleNamespace | None = None,
    solar_charge: SimpleNamespace | None = None,
    charge_control: ChargeControl | None = None,
    initialising: bool = False,
    is_schedule_charge: bool = False,
    charge_limit_entity_ids: dict[str, int] | None = None,
    charge_endtime_entity_ids: dict[str, int] | None = None,
    now: datetime = ANCHOR_NOW,
    device_controls: dict[str, object] | None = None,
    allocator: object | None = None,
    weather_provider: str | None = None,
) -> ChargeController:
    """Build a ChargeController with its heavy collaborators replaced by fakes."""
    subentry = make_subentry(HOT_WATER_SUBENTRY_ID)
    entry = make_config_entry(subentry)
    hass = make_hass()
    hass.loop = SimpleNamespace(
        create_task=Mock(side_effect=_close_coro_and_return(Mock()))
    )
    hass.async_create_task = Mock(side_effect=_close_coro_and_return(Mock()))

    controller = ChargeController.__new__(ChargeController)
    controller._hass = hass
    controller._entry = entry
    controller._subentry = subentry
    controller.caller = subentry.unique_id
    controller._initialising = initialising
    controller._control = charge_control or ChargeControl(
        subentry_id=subentry.subentry_id,
        config_name=HOT_WATER_SUBENTRY_ID,
        entities=ControlEntities(),
    )
    controller._charger = SimpleNamespace()
    controller._chargeable = SimpleNamespace()
    controller._tracker = tracker or make_fake_tracker()
    controller._solar_charge = solar_charge or make_fake_solar_charge()
    controller._charge_task = None
    controller._end_charge_task = None
    controller._is_updated_today_tomorrow_schedule = False

    controller._device_controls = device_controls or {}
    controller._allocator = allocator or SimpleNamespace(
        async_allocate_net_power=AsyncMock(return_value=True),
        init_allocator=Mock(),
    )
    controller._current_update_period = 0.0
    controller._min_current_update_period = 0.0
    controller._sync_charge_current_time = 0.0
    controller._net_power_update_count = 0
    controller._weather_provider = weather_provider
    controller._tracking_weather = weather_provider is not None
    controller.get_weather_provider = lambda: weather_provider

    controller.is_schedule_charge = lambda: is_schedule_charge
    controller.get_local_datetime = lambda: now
    controller.charge_switch_entity_id = "switch.hot_water_charge"
    controller.next_charge_time_trigger_entity_id = "datetime.hot_water_next_charge"
    controller.get_charge_limit_entity_ids = charge_limit_entity_ids or {}
    controller.get_charge_endtime_entity_ids = charge_endtime_entity_ids or {}

    return controller


def make_event(old_state: object, new_state: object) -> SimpleNamespace:
    """Minimal stand-in for a HA Event[EventStateChangedData]: only .data is read."""
    return SimpleNamespace(data={"old_state": old_state, "new_state": new_state})


def make_state(state: str, **attributes: object) -> SimpleNamespace:
    """Minimal stand-in for a HA State: .state and .attributes are all that's read."""
    return SimpleNamespace(state=state, attributes=attributes)


# ----------------------------------------------------------------------------
# async_handle_plug_in_charger_event() -- plug-in triggers a charge attempt
# ----------------------------------------------------------------------------
async def test_plug_in_event_turns_on_charger_switch_when_connected() -> None:
    """A real state change while the charger reports connected starts a charge attempt."""
    solar_charge = make_fake_solar_charge(is_connected=Mock(return_value=True))
    controller = make_bare_controller(solar_charge=solar_charge)
    event = make_event(make_state("not_connected"), make_state("connected"))

    await controller.async_handle_plug_in_charger_event(event)

    controller._hass.loop.create_task.assert_called_once()


async def test_plug_in_event_does_nothing_when_not_connected() -> None:
    """A state change that doesn't reflect a connected charger triggers nothing."""
    solar_charge = make_fake_solar_charge(is_connected=Mock(return_value=False))
    controller = make_bare_controller(solar_charge=solar_charge)
    event = make_event(make_state("connected"), make_state("not_connected"))

    await controller.async_handle_plug_in_charger_event(event)

    controller._hass.loop.create_task.assert_not_called()


@pytest.mark.parametrize(
    ("old_state", "new_state"),
    [
        pytest.param(None, make_state("connected"), id="no_old_state_at_startup"),
        pytest.param(make_state("connected"), None, id="no_new_state"),
        pytest.param(
            make_state("connected"), make_state("connected"), id="unchanged_state"
        ),
        pytest.param(
            make_state("unknown"), make_state("connected"), id="old_state_unknown"
        ),
    ],
)
async def test_plug_in_event_ignores_noise(
    old_state: object, new_state: object
) -> None:
    """Startup noise, unchanged state and unknown/unavailable states are all ignored."""
    solar_charge = make_fake_solar_charge(is_connected=Mock(return_value=True))
    controller = make_bare_controller(solar_charge=solar_charge)
    event = make_event(old_state, new_state)

    await controller.async_handle_plug_in_charger_event(event)

    controller._hass.loop.create_task.assert_not_called()


# ----------------------------------------------------------------------------
# async_handle_device_presence_event() -- only an OFF->ON transition matters
# ----------------------------------------------------------------------------
async def test_presence_event_off_to_on_starts_connection_check() -> None:
    """The vehicle arriving (off -> on) kicks off the connection-check task."""
    solar_charge = make_fake_solar_charge()
    solar_charge.start_check_charger_connection_task = Mock()
    controller = make_bare_controller(solar_charge=solar_charge)
    controller._solar_charge = solar_charge
    event = make_event(make_state("off"), make_state("on"))

    await controller.async_handle_device_presence_event(event)

    solar_charge.start_check_charger_connection_task.assert_called_once()


async def test_presence_event_on_to_off_does_nothing() -> None:
    """The vehicle leaving (on -> off) is not a trigger to start anything."""
    solar_charge = make_fake_solar_charge()
    solar_charge.start_check_charger_connection_task = Mock()
    controller = make_bare_controller(solar_charge=solar_charge)
    controller._solar_charge = solar_charge
    event = make_event(make_state("on"), make_state("off"))

    await controller.async_handle_device_presence_event(event)

    solar_charge.start_check_charger_connection_task.assert_not_called()


async def test_presence_event_ignores_unavailable_states() -> None:
    """An unavailable/unknown state on either side is not a real transition."""
    solar_charge = make_fake_solar_charge()
    solar_charge.start_check_charger_connection_task = Mock()
    controller = make_bare_controller(solar_charge=solar_charge)
    controller._solar_charge = solar_charge
    event = make_event(make_state("unavailable"), make_state("on"))

    await controller.async_handle_device_presence_event(event)

    solar_charge.start_check_charger_connection_task.assert_not_called()


# ----------------------------------------------------------------------------
# async_handle_sun_elevation_update() -- start charging as the sun rises through the trigger
# ----------------------------------------------------------------------------
async def test_sun_elevation_update_turns_on_charger_when_rising_through_trigger() -> (
    None
):
    """Sun rising and crossing the start-elevation trigger turns the charger on."""
    controller = make_bare_controller()
    controller.option_get_entity_number_or_abort = lambda _config_item: 10.0
    old_state = make_state("above_horizon", rising=True, elevation=8.0)
    new_state = make_state("above_horizon", rising=True, elevation=12.0)

    await controller.async_handle_sun_elevation_update(make_event(old_state, new_state))

    controller._hass.services.async_call.assert_awaited_once()


async def test_sun_elevation_update_does_nothing_when_not_yet_crossing_trigger() -> (
    None
):
    """Still below the trigger elevation: no action yet."""
    controller = make_bare_controller()
    controller.option_get_entity_number_or_abort = lambda _config_item: 10.0
    old_state = make_state("above_horizon", rising=True, elevation=5.0)
    new_state = make_state("above_horizon", rising=True, elevation=8.0)

    await controller.async_handle_sun_elevation_update(make_event(old_state, new_state))

    controller._hass.services.async_call.assert_not_awaited()


async def test_sun_elevation_update_ignores_a_setting_sun_crossing_the_same_value() -> (
    None
):
    """The same elevation crossing while the sun is setting does not trigger a start."""
    controller = make_bare_controller()
    controller.option_get_entity_number_or_abort = lambda _config_item: 10.0
    old_state = make_state("above_horizon", rising=False, elevation=12.0)
    new_state = make_state("above_horizon", rising=False, elevation=8.0)

    await controller.async_handle_sun_elevation_update(make_event(old_state, new_state))

    controller._hass.services.async_call.assert_not_awaited()


# ----------------------------------------------------------------------------
# async_handle_next_charge_time_update() -- reschedule, or log and move on
# ----------------------------------------------------------------------------
async def test_next_charge_time_update_schedules_the_parsed_datetime() -> None:
    """A valid new datetime string is parsed and handed to the tracker."""
    tracker = make_fake_tracker()
    controller = make_bare_controller(tracker=tracker)
    old_state = make_state("2026-01-01T00:00:00+00:00")
    new_state = make_state("2026-01-06T20:00:00+00:00")

    await controller.async_handle_next_charge_time_update(
        make_event(old_state, new_state)
    )

    tracker.schedule_next_charge_time.assert_called_once()
    scheduled_time = tracker.schedule_next_charge_time.call_args.args[0]
    assert scheduled_time.year == 2026
    assert scheduled_time.month == 1
    assert scheduled_time.day == 6


async def test_next_charge_time_update_logs_and_continues_on_unparseable_value() -> (
    None
):
    """A malformed datetime string is logged, not raised, and nothing gets scheduled."""
    tracker = make_fake_tracker()
    controller = make_bare_controller(tracker=tracker)
    old_state = make_state("2026-01-01T00:00:00+00:00")
    new_state = make_state("not-a-datetime")

    await controller.async_handle_next_charge_time_update(
        make_event(old_state, new_state)
    )

    tracker.schedule_next_charge_time.assert_not_called()


# ----------------------------------------------------------------------------
# async_handle_charge_limit_update() / async_handle_charge_endtime_update()
# -- flag a schedule update only when it's relevant and the charger is idle
# ----------------------------------------------------------------------------
async def test_charge_limit_update_for_today_flags_reschedule_when_idle() -> None:
    """Today's charge-limit entity changing, while idle and scheduled, sets the flag."""
    controller = make_bare_controller(
        is_schedule_charge=True,
        charge_limit_entity_ids={"number.monday_limit": 0},  # ANCHOR_NOW is Monday
    )
    event = make_event(make_state("70"), make_state("80"))
    event.data["new_state"].entity_id = "number.monday_limit"

    await controller.async_handle_charge_limit_update(event)

    assert controller.is_updated_today_tomorrow_schedule is True


async def test_charge_limit_update_ignored_while_currently_charging() -> None:
    """Even a relevant schedule change is ignored while a charge session is active."""
    control = ChargeControl(
        subentry_id="s", config_name=HOT_WATER_SUBENTRY_ID, entities=ControlEntities()
    )
    control.instance_count = 1
    controller = make_bare_controller(
        is_schedule_charge=True,
        charge_control=control,
        charge_limit_entity_ids={"number.monday_limit": 0},
    )
    event = make_event(make_state("70"), make_state("80"))
    event.data["new_state"].entity_id = "number.monday_limit"

    await controller.async_handle_charge_limit_update(event)

    assert controller.is_updated_today_tomorrow_schedule is False


async def test_charge_limit_update_for_an_unrelated_day_is_ignored() -> None:
    """A day that is neither today nor tomorrow does not flag a reschedule."""
    controller = make_bare_controller(
        is_schedule_charge=True,
        charge_limit_entity_ids={"number.wednesday_limit": 2},  # today=0, tomorrow=1
    )
    event = make_event(make_state("70"), make_state("80"))
    event.data["new_state"].entity_id = "number.wednesday_limit"

    await controller.async_handle_charge_limit_update(event)

    assert controller.is_updated_today_tomorrow_schedule is False


async def test_charge_endtime_update_for_tomorrow_flags_reschedule_when_idle() -> None:
    """The endtime handler follows the same today/tomorrow rule as the limit handler."""
    controller = make_bare_controller(
        is_schedule_charge=True,
        charge_endtime_entity_ids={"time.tuesday_endtime": 1},  # tomorrow
    )
    event = make_event(make_state("18:00:00"), make_state("19:00:00"))
    event.data["new_state"].entity_id = "time.tuesday_endtime"

    await controller.async_handle_charge_endtime_update(event)

    assert controller.is_updated_today_tomorrow_schedule is True


# ----------------------------------------------------------------------------
# async_check_if_need_to_reschedule_charge()
# ----------------------------------------------------------------------------
async def test_reschedule_check_does_nothing_when_flag_is_not_set() -> None:
    """No pending schedule update means nothing at all happens."""
    solar_charge = make_fake_solar_charge()
    controller = make_bare_controller(solar_charge=solar_charge)

    await controller.async_check_if_need_to_reschedule_charge()

    solar_charge.async_wake_up_and_update_ha.assert_not_awaited()


async def test_reschedule_check_skips_reevaluation_while_charging_but_clears_flag() -> (
    None
):
    """Busy charging: the inner check is skipped, but the pending flag is still cleared."""
    control = ChargeControl(
        subentry_id="s", config_name=HOT_WATER_SUBENTRY_ID, entities=ControlEntities()
    )
    control.instance_count = 1
    solar_charge = make_fake_solar_charge()
    controller = make_bare_controller(charge_control=control, solar_charge=solar_charge)
    controller.set_updated_today_tomorrow_schedule(True)

    await controller.async_check_if_need_to_reschedule_charge()

    solar_charge.async_wake_up_and_update_ha.assert_not_awaited()
    assert controller.is_updated_today_tomorrow_schedule is False


async def test_reschedule_check_turns_on_charger_when_goal_qualifies_and_connected() -> (
    None
):
    """Idle, scheduled, a qualifying goal and a connected device: reschedule now."""
    solar_charge = make_fake_solar_charge(
        async_get_current_schedule_data=AsyncMock(
            return_value=ScheduleData(
                weekly_schedule=[], use_charge_schedule=True, has_charge_endtime=True
            )
        ),
        is_device_at_location_and_connected=Mock(return_value=True),
    )
    controller = make_bare_controller(
        is_schedule_charge=True, solar_charge=solar_charge
    )
    controller.set_updated_today_tomorrow_schedule(True)

    await controller.async_check_if_need_to_reschedule_charge()

    controller._hass.loop.create_task.assert_called_once()
    assert controller.is_updated_today_tomorrow_schedule is False


async def test_reschedule_check_does_not_reschedule_when_goal_does_not_qualify() -> (
    None
):
    """A goal that isn't using the schedule at all does not trigger a reschedule."""
    solar_charge = make_fake_solar_charge(
        async_get_current_schedule_data=AsyncMock(
            return_value=ScheduleData(weekly_schedule=[], use_charge_schedule=False)
        )
    )
    controller = make_bare_controller(
        is_schedule_charge=True, solar_charge=solar_charge
    )
    controller.set_updated_today_tomorrow_schedule(True)

    await controller.async_check_if_need_to_reschedule_charge()

    controller._hass.loop.create_task.assert_not_called()
    assert controller.is_updated_today_tomorrow_schedule is False


async def test_reschedule_check_swallows_errors_but_still_clears_the_flag() -> None:
    """A failure partway through is logged, not raised, and the flag is still cleared."""
    solar_charge = make_fake_solar_charge(
        async_wake_up_and_update_ha=AsyncMock(side_effect=RuntimeError("boom"))
    )
    controller = make_bare_controller(
        is_schedule_charge=True, solar_charge=solar_charge
    )
    controller.set_updated_today_tomorrow_schedule(True)

    await controller.async_check_if_need_to_reschedule_charge()

    assert controller.is_updated_today_tomorrow_schedule is False


# ----------------------------------------------------------------------------
# _async_switch_task() -- switch actions are deferred while still initialising
# ----------------------------------------------------------------------------
async def test_switch_task_deferred_while_initialising() -> None:
    """No task is scheduled at all while the controller is still initialising."""
    controller = make_bare_controller(initialising=True)
    action = AsyncMock()

    await controller._async_switch_task(action, True)

    controller._hass.loop.create_task.assert_not_called()
    action.assert_not_called()


async def test_switch_task_scheduled_once_initialised() -> None:
    """Once initialised, the action is scheduled as a background task."""
    controller = make_bare_controller(initialising=False)
    action = AsyncMock()

    await controller._async_switch_task(action, True)

    controller._hass.loop.create_task.assert_called_once()


# ----------------------------------------------------------------------------
# _async_switch_charge() -- guards against double-start and double-stop
# ----------------------------------------------------------------------------
async def test_switch_charge_on_starts_charger_when_not_already_running() -> None:
    """Turning the charge switch on from stopped starts the charger."""
    controller = make_bare_controller()
    controller.async_start_charger = AsyncMock()
    controller.charge_control.switch_charge = False

    await controller._async_switch_charge(True)

    assert controller.charge_control.switch_charge is True
    controller.async_start_charger.assert_awaited_once_with(controller.charge_control)


async def test_switch_charge_on_is_a_noop_when_already_running() -> None:
    """Turning the charge switch on again while already running does not double-start."""
    controller = make_bare_controller()
    controller.async_start_charger = AsyncMock()
    controller.charge_control.switch_charge = True

    await controller._async_switch_charge(True)

    controller.async_start_charger.assert_not_awaited()


async def test_switch_charge_off_stops_charger_when_running() -> None:
    """Turning the charge switch off while running stops the charger."""
    controller = make_bare_controller()
    controller.async_stop_charger = AsyncMock()
    controller.charge_control.switch_charge = True

    await controller._async_switch_charge(False)

    assert controller.charge_control.switch_charge is False
    controller.async_stop_charger.assert_awaited_once_with(controller.charge_control)


async def test_switch_charge_off_is_a_noop_when_already_stopped() -> None:
    """Turning the charge switch off again while already stopped calls nothing."""
    controller = make_bare_controller()
    controller.async_stop_charger = AsyncMock()
    controller.charge_control.switch_charge = False

    await controller._async_switch_charge(False)

    controller.async_stop_charger.assert_not_awaited()


# ----------------------------------------------------------------------------
# async_start_charger() -- guard against starting a second task
# ----------------------------------------------------------------------------
async def test_start_charger_is_a_noop_when_a_charge_task_is_already_running() -> None:
    """An already-running charge task is left alone, not replaced."""
    controller = make_bare_controller()
    controller.async_start_charge = AsyncMock()
    controller.charge_control.charge_task = SimpleNamespace(
        done=Mock(return_value=False), get_name=Mock(return_value="hot_water charge")
    )

    await controller.async_start_charger(controller.charge_control)

    controller.async_start_charge.assert_not_awaited()


# ----------------------------------------------------------------------------
# stop_charge() -- create, reuse or skip the end-charge task as appropriate
# ----------------------------------------------------------------------------
def test_stop_charge_returns_none_without_a_charge_task() -> None:
    """Nothing is running, so there is nothing to stop."""
    controller = make_bare_controller()

    result = controller.stop_charge()

    assert result is None
    controller._hass.async_create_task.assert_not_called()


def test_stop_charge_returns_none_when_charge_task_already_done() -> None:
    """A charge task that already finished on its own needs no explicit stop."""
    controller = make_bare_controller()
    controller._charge_task = SimpleNamespace(
        done=Mock(return_value=True), get_name=Mock(return_value="hot_water charge")
    )

    result = controller.stop_charge()

    assert result is None
    controller._hass.async_create_task.assert_not_called()


def test_stop_charge_creates_an_end_task_when_none_is_running() -> None:
    """A running charge task with no end task yet gets a new end-charge task."""
    new_end_task = Mock(name="new_end_task")
    controller = make_bare_controller()
    controller._hass.async_create_task = Mock(
        side_effect=_close_coro_and_return(new_end_task)
    )
    controller._charge_task = SimpleNamespace(done=Mock(return_value=False))

    result = controller.stop_charge()

    assert result is new_end_task
    assert controller._end_charge_task is new_end_task
    controller._hass.async_create_task.assert_called_once()


def test_stop_charge_reuses_an_already_running_end_task() -> None:
    """A still-running end-charge task is returned as-is, not duplicated."""
    existing_end_task = SimpleNamespace(
        done=Mock(return_value=False), get_name=Mock(return_value="hot_water end")
    )
    controller = make_bare_controller()
    controller._charge_task = SimpleNamespace(done=Mock(return_value=False))
    controller._end_charge_task = existing_end_task

    result = controller.stop_charge()

    assert result is existing_end_task
    controller._hass.async_create_task.assert_not_called()


def test_stop_charge_starts_a_fresh_end_task_once_the_old_one_finished() -> None:
    """A previous end-charge task that already completed does not block a new one."""
    finished_end_task = SimpleNamespace(done=Mock(return_value=True))
    new_end_task = Mock(name="new_end_task")
    controller = make_bare_controller()
    controller._hass.async_create_task = Mock(
        side_effect=_close_coro_and_return(new_end_task)
    )
    controller._charge_task = SimpleNamespace(done=Mock(return_value=False))
    controller._end_charge_task = finished_end_task

    result = controller.stop_charge()

    assert result is new_end_task
    controller._hass.async_create_task.assert_called_once()


def make_net_power_event(
    entity_id: str, old_state: object, new_state: object
) -> SimpleNamespace:
    """Stand-in for the net power sensor's Event[EventStateChangedData]."""
    return SimpleNamespace(
        data={"entity_id": entity_id, "old_state": old_state, "new_state": new_state}
    )


def _patch_utcnow(monkeypatch: pytest.MonkeyPatch, timestamp: float) -> None:
    monkeypatch.setattr(
        controller_module,
        "utcnow",
        Mock(return_value=SimpleNamespace(timestamp=Mock(return_value=timestamp))),
    )


# ----------------------------------------------------------------------------
# async_reset_charge_limit_default() -- reset all 7 days to configured defaults
#
# Only reachable on a device with its own number/time entities (a real
# charger, or Global Defaults if it exposes them) -- moved here from
# SolarChargerCoordinator, which used to own this logic and delegate down to
# a control's ChargeController; the coordinator now just forwards the call.
# ----------------------------------------------------------------------------
async def test_reset_charge_limit_default_sets_every_day_within_range() -> None:
    """Every default that falls within [min, max] gets pushed to its number entity."""
    numbers = {
        key: SimpleNamespace(async_set_native_value=AsyncMock())
        for key in DEFAULT_CHARGE_LIMIT_MAP.values()
    }
    times = {
        key: SimpleNamespace(async_set_value=AsyncMock())
        for key in WEEKLY_CHARGE_ENDTIMES
    }
    control = ChargeControl(
        subentry_id=HOT_WATER_SUBENTRY_ID,
        config_name=HOT_WATER_SUBENTRY_ID,
        entities=ControlEntities(numbers=numbers, times=times),
    )
    controller = make_bare_controller(charge_control=control)
    controller.option_get_entity_number_or_abort = lambda _config_item, _val_dict=None: (
        50.0
    )

    await controller.async_reset_charge_limit_default()

    for entity in numbers.values():
        entity.async_set_native_value.assert_awaited_once_with(50.0)
    for entity in times.values():
        entity.async_set_value.assert_awaited_once()


async def test_reset_charge_limit_default_skips_a_default_outside_the_valid_range() -> (
    None
):
    """A default outside [min, max] is left alone; the rest are still applied."""
    numbers = {
        key: SimpleNamespace(async_set_native_value=AsyncMock())
        for key in DEFAULT_CHARGE_LIMIT_MAP.values()
    }
    times = {
        key: SimpleNamespace(async_set_value=AsyncMock())
        for key in WEEKLY_CHARGE_ENDTIMES
    }
    control = ChargeControl(
        subentry_id=HOT_WATER_SUBENTRY_ID,
        config_name=HOT_WATER_SUBENTRY_ID,
        entities=ControlEntities(numbers=numbers, times=times),
    )
    controller = make_bare_controller(charge_control=control)

    def _fake_option_get(config_item: str, _val_dict: object = None) -> float:
        if config_item == NUMBER_DEVICE_MIN_CHARGE_LIMIT:
            return 0.0
        if config_item == NUMBER_DEVICE_MAX_CHARGE_LIMIT:
            return 100.0
        if config_item == NUMBER_DEFAULT_CHARGE_LIMIT_TUESDAY:
            return 150.0  # out of range
        return 50.0

    controller.option_get_entity_number_or_abort = _fake_option_get

    await controller.async_reset_charge_limit_default()

    numbers[NUMBER_CHARGE_LIMIT_TUESDAY].async_set_native_value.assert_not_awaited()
    numbers[NUMBER_CHARGE_LIMIT_MONDAY].async_set_native_value.assert_awaited_once_with(
        50.0
    )


async def test_reset_charge_limit_default_noop_without_number_and_time_entities() -> (
    None
):
    """A device with no number/time entities of its own (eg. Global Defaults) is left alone."""
    control = ChargeControl(
        subentry_id=HOT_WATER_SUBENTRY_ID,
        config_name=HOT_WATER_SUBENTRY_ID,
        entities=ControlEntities(),  # numbers/times both None
    )
    controller = make_bare_controller(charge_control=control)
    controller.option_get_entity_number_or_abort = Mock(
        side_effect=AssertionError("should never be called")
    )

    # Must not raise, and must not touch option_get_entity_number_or_abort at all.
    await controller.async_reset_charge_limit_default()


# ----------------------------------------------------------------------------
# _async_allocate_net_power() -- thin wrapper that never lets the allocator raise
#
# Only ever exercised on the Global Defaults device's controller, the one
# that owns the shared PowerAllocator and _device_controls map.
# ----------------------------------------------------------------------------
async def test_allocate_net_power_returns_the_allocator_result() -> None:
    """The allocator's own True/False result is passed straight through."""
    allocator = SimpleNamespace(async_allocate_net_power=AsyncMock(return_value=True))
    controller = make_bare_controller(allocator=allocator)

    assert await controller._async_allocate_net_power() is True


async def test_allocate_net_power_swallows_allocator_errors_as_false() -> None:
    """A raised exception in the allocator is logged, not propagated, and counts as False."""
    allocator = SimpleNamespace(
        async_allocate_net_power=AsyncMock(side_effect=RuntimeError("boom"))
    )
    controller = make_bare_controller(allocator=allocator)

    assert await controller._async_allocate_net_power() is False


# ----------------------------------------------------------------------------
# _async_synchronise_charge_current_update()
# ----------------------------------------------------------------------------
async def test_synchronise_charge_current_update_sets_sensor_and_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful sync writes the sync-update sensor and records the sync timestamp."""
    sync_entity = SimpleNamespace(set_state=Mock())
    control = ChargeControl(
        subentry_id=HOT_WATER_SUBENTRY_ID,
        config_name=HOT_WATER_SUBENTRY_ID,
        entities=ControlEntities(sensors={SENSOR_SYNC_UPDATE: sync_entity}),
    )
    controller = make_bare_controller(charge_control=control)
    # Global Defaults' own device_controls entry maps its subentry_id back to
    # itself -- see _async_synchronise_charge_current_update()'s lookup.
    device_control = DeviceControl(
        subentry_id=controller._subentry.subentry_id,
        config_name=HOT_WATER_SUBENTRY_ID,
        controller=controller,
    )
    controller._device_controls = {controller._subentry.subentry_id: device_control}
    _patch_utcnow(monkeypatch, timestamp=12345.0)

    await controller._async_synchronise_charge_current_update()

    sync_entity.set_state.assert_called_once()
    assert controller._sync_charge_current_time == 12345.0


async def test_synchronise_charge_current_update_swallows_a_missing_device_control() -> (
    None
):
    """The global-defaults control not being registered yet is logged, not raised."""
    controller = make_bare_controller(device_controls={})

    # Must not raise despite the lookup failing.
    await controller._async_synchronise_charge_current_update()

    assert controller._sync_charge_current_time == 0.0


# ----------------------------------------------------------------------------
# _async_handle_net_power_update() -- allocate, then maybe synchronise
# ----------------------------------------------------------------------------
async def test_net_power_update_ignores_an_event_with_no_new_state() -> None:
    """A cleared/removed entity (new_state=None) is not a real power update."""
    controller = make_bare_controller()
    controller._async_allocate_net_power = AsyncMock()
    event = make_net_power_event("sensor.net_power", make_state("100"), None)

    await controller._async_handle_net_power_update(event)

    controller._async_allocate_net_power.assert_not_awaited()


async def test_net_power_update_allocates_but_waits_for_the_sync_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful allocation before the min sync period just counts, doesn't sync yet."""
    _patch_utcnow(monkeypatch, timestamp=100.0)
    controller = make_bare_controller()
    controller._sync_charge_current_time = 95.0  # 5s ago
    controller._min_current_update_period = 30.0
    controller._async_allocate_net_power = AsyncMock(return_value=True)
    controller._async_synchronise_charge_current_update = AsyncMock()
    event = make_net_power_event(
        "sensor.net_power", make_state("100"), make_state("150")
    )

    await controller._async_handle_net_power_update(event)

    assert controller._net_power_update_count == 1
    controller._async_synchronise_charge_current_update.assert_not_awaited()


async def test_net_power_update_synchronises_once_the_sync_period_has_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once enough time has passed and at least one allocation happened, it synchronises."""
    _patch_utcnow(monkeypatch, timestamp=200.0)
    controller = make_bare_controller()
    controller._sync_charge_current_time = 100.0  # 100s ago
    controller._min_current_update_period = 30.0
    controller._async_allocate_net_power = AsyncMock(return_value=True)
    controller._async_synchronise_charge_current_update = AsyncMock()
    event = make_net_power_event(
        "sensor.net_power", make_state("100"), make_state("150")
    )

    await controller._async_handle_net_power_update(event)

    controller._async_synchronise_charge_current_update.assert_awaited_once()
    assert controller._net_power_update_count == 0


async def test_net_power_update_does_not_synchronise_when_allocation_found_nothing_to_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even past the sync period, a run with no running charger does not trigger a sync."""
    _patch_utcnow(monkeypatch, timestamp=200.0)
    controller = make_bare_controller()
    controller._sync_charge_current_time = 100.0
    controller._min_current_update_period = 30.0
    controller._async_allocate_net_power = AsyncMock(return_value=False)
    controller._async_synchronise_charge_current_update = AsyncMock()
    event = make_net_power_event(
        "sensor.net_power", make_state("100"), make_state("150")
    )

    await controller._async_handle_net_power_update(event)

    controller._async_synchronise_charge_current_update.assert_not_awaited()
    assert controller._net_power_update_count == 0


async def test_net_power_update_swallows_a_synchronise_failure() -> None:
    """A failure while synchronising is logged via self.caller, not raised to the event bus."""
    controller = make_bare_controller()
    controller._sync_charge_current_time = 0.0
    controller._min_current_update_period = 0.0
    controller._async_allocate_net_power = AsyncMock(return_value=True)
    controller._async_synchronise_charge_current_update = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    event = make_net_power_event(
        "sensor.net_power", make_state("100"), make_state("150")
    )

    # Must not raise despite the synchronise call failing.
    await controller._async_handle_net_power_update(event)


# ----------------------------------------------------------------------------
# check_weather_provider() -- subscribe/unsubscribe state machine
#
# Only ever called for the Global Defaults device's controller (see
# SolarChargerCoordinator._async_periodic_maintenance()'s dispatch).
# ----------------------------------------------------------------------------
def test_weather_provider_none_and_not_tracking_is_a_noop() -> None:
    """No weather provider configured, and nothing was tracked: nothing to do."""
    tracker = make_fake_tracker()
    controller = make_bare_controller(tracker=tracker, weather_provider=None)

    controller.check_weather_provider()

    tracker.untrack_weather_update.assert_not_called()
    tracker.track_weather_update.assert_not_called()


def test_weather_provider_removed_unsubscribes() -> None:
    """A previously configured provider being cleared unsubscribes tracking."""
    tracker = make_fake_tracker()
    controller = make_bare_controller(tracker=tracker, weather_provider=None)
    controller._weather_provider = "weather.home"
    controller._tracking_weather = True

    controller.check_weather_provider()

    tracker.untrack_weather_update.assert_called_once()
    assert controller._tracking_weather is False
    assert controller._weather_provider is None


def test_weather_provider_newly_configured_subscribes() -> None:
    """A provider configured for the first time starts tracking."""
    tracker = make_fake_tracker()
    controller = make_bare_controller(tracker=tracker, weather_provider="weather.home")
    controller._weather_provider = None
    controller._tracking_weather = False

    controller.check_weather_provider()

    tracker.track_weather_update.assert_called_once()
    assert controller._tracking_weather is True
    assert controller._weather_provider == "weather.home"


def test_weather_provider_unchanged_does_not_resubscribe() -> None:
    """The same provider still configured does not tear down and rebuild tracking."""
    tracker = make_fake_tracker()
    controller = make_bare_controller(tracker=tracker, weather_provider="weather.home")
    controller._weather_provider = "weather.home"
    controller._tracking_weather = True

    controller.check_weather_provider()

    tracker.untrack_weather_update.assert_not_called()
    tracker.track_weather_update.assert_not_called()


def test_weather_provider_changed_resubscribes_to_the_new_one() -> None:
    """Switching providers unsubscribes the old one and subscribes the new one."""
    tracker = make_fake_tracker()
    controller = make_bare_controller(
        tracker=tracker, weather_provider="weather.other_home"
    )
    controller._weather_provider = "weather.home"
    controller._tracking_weather = True

    controller.check_weather_provider()

    tracker.untrack_weather_update.assert_called_once()
    tracker.track_weather_update.assert_called_once()
    assert controller._weather_provider == "weather.other_home"


def test_weather_tracking_falls_back_to_untracked_when_tracker_rejects_it() -> None:
    """If the tracker fails to subscribe, the provider is not recorded as tracked."""
    tracker = make_fake_tracker(track_weather_update=Mock(return_value=False))
    controller = make_bare_controller(tracker=tracker, weather_provider="weather.home")
    controller._weather_provider = None
    controller._tracking_weather = False

    controller.check_weather_provider()

    assert controller._tracking_weather is False
    assert controller._weather_provider is None
