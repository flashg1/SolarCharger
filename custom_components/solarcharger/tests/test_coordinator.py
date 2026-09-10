# ruff: noqa: SLF001
"""Unit tests for SolarChargerCoordinator (modules/coordinator.py).

SolarChargerCoordinator.__init__ constructs a real Tracker, same as
ChargeController, so these tests bypass __init__ via __new__() and wire up
small fakes for _tracker and _allocator instead -- see test_controller.py for
the same rationale. Each DeviceControl's .controller is a fake exposing only
the ChargeController surface the coordinator itself calls (the switch
delegation methods, .charge_control, .async_check_if_need_to_reschedule_charge,
...), not a real ChargeController.

_async_handle_net_power_update() is the actual trigger for the sequence
diagrammed earlier in this project (net power sensor -> allocate -> maybe
synchronise charge current) -- it and _check_weather_provider()'s tracking
state machine get the most direct coverage below, since they carry the real
conditional logic in this module.
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
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR_SYNC_UPDATE,
    WEEKLY_CHARGE_ENDTIMES,
)
from custom_components.solarcharger.models.model_charge_control import (
    ChargeControl,
    ControlEntities,
)
from custom_components.solarcharger.models.model_device_control import DeviceControl
import custom_components.solarcharger.modules.coordinator as coordinator_module
from custom_components.solarcharger.modules.coordinator import SolarChargerCoordinator
import pytest

from .conftest import make_config_entry, make_hass, make_subentry

GLOBAL_DEFAULTS_SUBENTRY_ID = "global-defaults"
HOT_WATER_SUBENTRY_ID = "hot-water"
ANCHOR_NOW = datetime(2026, 1, 5, 10, 0, 0, tzinfo=ZoneInfo("UTC"))


# ----------------------------------------------------------------------------
def make_fake_tracker(**overrides: object) -> SimpleNamespace:
    """Stand-in for Tracker: only what the coordinator itself calls."""
    defaults: dict[str, object] = {
        "async_setup": AsyncMock(),
        "async_unload": AsyncMock(),
        "track_net_power_update": Mock(return_value=True),
        "track_weather_update": Mock(return_value=True),
        "untrack_weather_update": Mock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_fake_controller(**overrides: object) -> SimpleNamespace:
    """Stand-in for ChargeController: only the surface the coordinator calls."""
    defaults: dict[str, object] = {
        "charge_control": ChargeControl(
            subentry_id=HOT_WATER_SUBENTRY_ID,
            config_name=HOT_WATER_SUBENTRY_ID,
            entities=ControlEntities(),
        ),
        "async_switch_charge": AsyncMock(),
        "async_switch_schedule_charge": AsyncMock(),
        "async_switch_plugin_trigger": AsyncMock(),
        "async_switch_presence_trigger": AsyncMock(),
        "async_switch_sun_elevation_trigger": AsyncMock(),
        "async_switch_calibrate_max_charge_speed": AsyncMock(),
        "async_check_if_need_to_reschedule_charge": AsyncMock(),
        "async_setup": AsyncMock(),
        "async_unload": AsyncMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_device_control(
    subentry_id: str, config_name: str, *, controller: SimpleNamespace | None = None
) -> DeviceControl:
    """Build a DeviceControl backed by a fake ChargeController."""
    return DeviceControl(
        subentry_id=subentry_id,
        config_name=config_name,
        controller=controller or make_fake_controller(),  # type: ignore[arg-type]
    )


def make_bare_coordinator(
    *,
    device_controls: dict[str, DeviceControl] | None = None,
    tracker: SimpleNamespace | None = None,
    allocator: object | None = None,
    weather_provider: str | None = None,
    now: datetime = ANCHOR_NOW,
) -> SolarChargerCoordinator:
    """Build a SolarChargerCoordinator with its heavy collaborators replaced by fakes."""
    subentry = make_subentry(GLOBAL_DEFAULTS_SUBENTRY_ID, subentry_id="global-defaults")
    entry = make_config_entry(subentry)
    hass = make_hass()

    def _close_coro_and_return_mock(coro: object) -> Mock:
        coro.close()  # type: ignore[attr-defined]
        return Mock()

    hass.async_create_task = Mock(side_effect=_close_coro_and_return_mock)

    coordinator = SolarChargerCoordinator.__new__(SolarChargerCoordinator)
    coordinator._hass = hass
    coordinator._entry = entry
    coordinator._subentry = subentry
    coordinator.caller = "Coordinator"
    coordinator.device_controls = device_controls or {}
    coordinator._unsub = []
    coordinator._tracker = tracker or make_fake_tracker()
    coordinator._allocator = allocator or SimpleNamespace(
        async_allocate_net_power=AsyncMock(return_value=True),
        init_allocator=Mock(),
    )
    coordinator._current_update_period = 0.0
    coordinator._min_current_update_period = 0.0
    coordinator._sync_charge_current_time = 0.0
    coordinator._net_power_update_count = 0
    coordinator._weather_provider = weather_provider
    coordinator._tracking_weather = weather_provider is not None
    coordinator._last_check_timestamp = None

    coordinator.get_local_datetime = lambda: now
    coordinator.get_weather_provider = lambda: weather_provider

    return coordinator


def make_event(entity_id: str, old_state: object, new_state: object) -> SimpleNamespace:
    """Minimal stand-in for a HA Event[EventStateChangedData]."""
    return SimpleNamespace(
        data={"entity_id": entity_id, "old_state": old_state, "new_state": new_state}
    )


def make_state(state: str) -> SimpleNamespace:
    """Minimal stand-in for a HA State: only .state is read here."""
    return SimpleNamespace(state=state)


# ----------------------------------------------------------------------------
# is_charging() -- trivial, but the only place this indirection exists
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("switch_charge", [True, False, None])
def test_is_charging_mirrors_the_charge_control_switch_state(
    switch_charge: bool | None,
) -> None:
    """is_charging() is just a read-through to ChargeControl.switch_charge."""
    coordinator = make_bare_coordinator()
    control = ChargeControl(
        subentry_id="s", config_name="s", entities=ControlEntities()
    )
    control.switch_charge = switch_charge

    assert coordinator.is_charging(control) is switch_charge


# ----------------------------------------------------------------------------
# Switch delegation -- only acts when the device has a controller
# ----------------------------------------------------------------------------
async def test_switch_charge_delegates_to_the_device_controller() -> None:
    """The coordinator's switch methods just forward to the matching controller method."""
    controller = make_fake_controller()
    coordinator = make_bare_coordinator()
    control = make_device_control(
        HOT_WATER_SUBENTRY_ID, "hot_water", controller=controller
    )

    await coordinator.async_switch_charge(control, True)

    controller.async_switch_charge.assert_awaited_once_with(True)


async def test_switch_charge_is_a_noop_without_a_controller() -> None:
    """The global-defaults DeviceControl has no controller: nothing to delegate to."""
    coordinator = make_bare_coordinator()
    control = DeviceControl(
        subentry_id=GLOBAL_DEFAULTS_SUBENTRY_ID,
        config_name=OPTION_GLOBAL_DEFAULTS_ID,
        controller=None,  # type: ignore[arg-type]
    )

    # Must not raise despite controller being None.
    await coordinator.async_switch_charge(control, True)


@pytest.mark.parametrize(
    ("coordinator_method", "controller_method"),
    [
        ("async_switch_schedule_charge", "async_switch_schedule_charge"),
        ("async_switch_plugin_trigger", "async_switch_plugin_trigger"),
        ("async_switch_presence_trigger", "async_switch_presence_trigger"),
        ("async_switch_sun_elevation_trigger", "async_switch_sun_elevation_trigger"),
        (
            "async_switch_calibrate_max_charge_speed",
            "async_switch_calibrate_max_charge_speed",
        ),
    ],
)
async def test_every_switch_method_delegates_to_its_matching_controller_method(
    coordinator_method: str, controller_method: str
) -> None:
    """Each of the remaining switch delegations wires up to the right controller method."""
    controller = make_fake_controller()
    coordinator = make_bare_coordinator()
    control = make_device_control(
        HOT_WATER_SUBENTRY_ID, "hot_water", controller=controller
    )

    await getattr(coordinator, coordinator_method)(control, True)

    getattr(controller, controller_method).assert_awaited_once_with(True)


# ----------------------------------------------------------------------------
# async_reset_charge_limit_default() -- reset all 7 days to configured defaults
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
    controller = make_fake_controller(
        charge_control=ChargeControl(
            subentry_id=HOT_WATER_SUBENTRY_ID,
            config_name="hot_water",
            entities=ControlEntities(numbers=numbers, times=times),
        )
    )
    subentry = make_subentry(HOT_WATER_SUBENTRY_ID, subentry_id=HOT_WATER_SUBENTRY_ID)
    coordinator = make_bare_coordinator()
    coordinator._entry = make_config_entry(subentry)
    coordinator.option_get_entity_number_or_abort = lambda _config_item: 50.0
    control = make_device_control(
        HOT_WATER_SUBENTRY_ID, "hot_water", controller=controller
    )

    await coordinator.async_reset_charge_limit_default(control)

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
    controller = make_fake_controller(
        charge_control=ChargeControl(
            subentry_id=HOT_WATER_SUBENTRY_ID,
            config_name="hot_water",
            entities=ControlEntities(numbers=numbers, times=times),
        )
    )
    subentry = make_subentry(HOT_WATER_SUBENTRY_ID, subentry_id=HOT_WATER_SUBENTRY_ID)
    coordinator = make_bare_coordinator()
    coordinator._entry = make_config_entry(subentry)

    def _fake_option_get(config_item: str) -> float:
        if config_item == NUMBER_DEVICE_MIN_CHARGE_LIMIT:
            return 0.0
        if config_item == NUMBER_DEVICE_MAX_CHARGE_LIMIT:
            return 100.0
        if config_item == NUMBER_DEFAULT_CHARGE_LIMIT_TUESDAY:
            return 150.0  # out of range
        return 50.0

    coordinator.option_get_entity_number_or_abort = _fake_option_get
    control = make_device_control(
        HOT_WATER_SUBENTRY_ID, "hot_water", controller=controller
    )

    await coordinator.async_reset_charge_limit_default(control)

    numbers[NUMBER_CHARGE_LIMIT_TUESDAY].async_set_native_value.assert_not_awaited()
    numbers[NUMBER_CHARGE_LIMIT_MONDAY].async_set_native_value.assert_awaited_once_with(
        50.0
    )


async def test_reset_charge_limit_default_noop_without_number_and_time_entities() -> (
    None
):
    """The global-defaults control (no number/time entities of its own) is left alone."""
    controller = make_fake_controller(
        charge_control=ChargeControl(
            subentry_id=GLOBAL_DEFAULTS_SUBENTRY_ID,
            config_name=OPTION_GLOBAL_DEFAULTS_ID,
            entities=ControlEntities(),  # numbers/times both None
        )
    )
    coordinator = make_bare_coordinator()
    coordinator.option_get_entity_number_or_abort = Mock(
        side_effect=AssertionError("should never be called")
    )
    control = make_device_control(
        GLOBAL_DEFAULTS_SUBENTRY_ID, OPTION_GLOBAL_DEFAULTS_ID, controller=controller
    )

    # Must not raise, and must not touch option_get_entity_number_or_abort at all.
    await coordinator.async_reset_charge_limit_default(control)


# ----------------------------------------------------------------------------
# _async_allocate_net_power() -- thin wrapper that never lets the allocator raise
# ----------------------------------------------------------------------------
async def test_allocate_net_power_returns_the_allocator_result() -> None:
    """The allocator's own True/False result is passed straight through."""
    allocator = SimpleNamespace(async_allocate_net_power=AsyncMock(return_value=True))
    coordinator = make_bare_coordinator(allocator=allocator)

    assert await coordinator._async_allocate_net_power() is True


async def test_allocate_net_power_swallows_allocator_errors_as_false() -> None:
    """A raised exception in the allocator is logged, not propagated, and counts as False."""
    allocator = SimpleNamespace(
        async_allocate_net_power=AsyncMock(side_effect=RuntimeError("boom"))
    )
    coordinator = make_bare_coordinator(allocator=allocator)

    assert await coordinator._async_allocate_net_power() is False


# ----------------------------------------------------------------------------
# _async_synchronise_charge_current_update()
# ----------------------------------------------------------------------------
async def test_synchronise_charge_current_update_sets_sensor_and_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful sync writes the sync-update sensor and records the sync timestamp."""
    sync_entity = SimpleNamespace(set_state=Mock())
    controller = make_fake_controller(
        charge_control=ChargeControl(
            subentry_id=GLOBAL_DEFAULTS_SUBENTRY_ID,
            config_name=OPTION_GLOBAL_DEFAULTS_ID,
            entities=ControlEntities(sensors={SENSOR_SYNC_UPDATE: sync_entity}),
        )
    )
    control = make_device_control(
        GLOBAL_DEFAULTS_SUBENTRY_ID, OPTION_GLOBAL_DEFAULTS_ID, controller=controller
    )
    coordinator = make_bare_coordinator(
        device_controls={GLOBAL_DEFAULTS_SUBENTRY_ID: control}
    )
    fake_utcnow_result = SimpleNamespace(timestamp=Mock(return_value=12345.0))
    monkeypatch.setattr(
        coordinator_module, "utcnow", Mock(return_value=fake_utcnow_result)
    )

    await coordinator._async_synchronise_charge_current_update()

    sync_entity.set_state.assert_called_once()
    assert coordinator._sync_charge_current_time == 12345.0


async def test_synchronise_charge_current_update_swallows_a_missing_device_control() -> (
    None
):
    """The global-defaults control not being registered yet is logged, not raised."""
    coordinator = make_bare_coordinator(device_controls={})

    # Must not raise despite the lookup failing.
    await coordinator._async_synchronise_charge_current_update()

    assert coordinator._sync_charge_current_time == 0.0


# ----------------------------------------------------------------------------
# _async_handle_net_power_update() -- allocate, then maybe synchronise
# ----------------------------------------------------------------------------
def _patch_utcnow(monkeypatch: pytest.MonkeyPatch, timestamp: float) -> None:
    monkeypatch.setattr(
        coordinator_module,
        "utcnow",
        Mock(return_value=SimpleNamespace(timestamp=Mock(return_value=timestamp))),
    )


async def test_net_power_update_ignores_an_event_with_no_new_state() -> None:
    """A cleared/removed entity (new_state=None) is not a real power update."""
    coordinator = make_bare_coordinator()
    coordinator._async_allocate_net_power = AsyncMock()
    event = make_event("sensor.net_power", make_state("100"), None)

    await coordinator._async_handle_net_power_update(event)

    coordinator._async_allocate_net_power.assert_not_awaited()


async def test_net_power_update_allocates_but_waits_for_the_sync_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful allocation before the min sync period just counts, doesn't sync yet."""
    _patch_utcnow(monkeypatch, timestamp=100.0)
    coordinator = make_bare_coordinator()
    coordinator._sync_charge_current_time = 95.0  # 5s ago
    coordinator._min_current_update_period = 30.0
    coordinator._async_allocate_net_power = AsyncMock(return_value=True)
    coordinator._async_synchronise_charge_current_update = AsyncMock()
    event = make_event("sensor.net_power", make_state("100"), make_state("150"))

    await coordinator._async_handle_net_power_update(event)

    assert coordinator._net_power_update_count == 1
    coordinator._async_synchronise_charge_current_update.assert_not_awaited()


async def test_net_power_update_synchronises_once_the_sync_period_has_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once enough time has passed and at least one allocation happened, it synchronises."""
    _patch_utcnow(monkeypatch, timestamp=200.0)
    coordinator = make_bare_coordinator()
    coordinator._sync_charge_current_time = 100.0  # 100s ago
    coordinator._min_current_update_period = 30.0
    coordinator._async_allocate_net_power = AsyncMock(return_value=True)
    coordinator._async_synchronise_charge_current_update = AsyncMock()
    event = make_event("sensor.net_power", make_state("100"), make_state("150"))

    await coordinator._async_handle_net_power_update(event)

    coordinator._async_synchronise_charge_current_update.assert_awaited_once()
    assert coordinator._net_power_update_count == 0


async def test_net_power_update_does_not_synchronise_when_allocation_found_nothing_to_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even past the sync period, a run with no running charger does not trigger a sync."""
    _patch_utcnow(monkeypatch, timestamp=200.0)
    coordinator = make_bare_coordinator()
    coordinator._sync_charge_current_time = 100.0
    coordinator._min_current_update_period = 30.0
    coordinator._async_allocate_net_power = AsyncMock(return_value=False)
    coordinator._async_synchronise_charge_current_update = AsyncMock()
    event = make_event("sensor.net_power", make_state("100"), make_state("150"))

    await coordinator._async_handle_net_power_update(event)

    coordinator._async_synchronise_charge_current_update.assert_not_awaited()
    assert coordinator._net_power_update_count == 0


async def test_net_power_update_swallows_a_synchronise_failure() -> None:
    """A failure while synchronising is logged via self.caller, not raised back to the event bus.

    Regression test for a bug where the except-block's own log call read
    self.solarcharge.caller -- an attribute SolarChargerCoordinator doesn't
    have (that belongs to ChargeController) -- so a genuine failure here
    used to raise a fresh AttributeError instead of being logged and
    swallowed as intended.
    """
    coordinator = make_bare_coordinator()
    coordinator._sync_charge_current_time = 0.0
    coordinator._min_current_update_period = 0.0
    coordinator._async_allocate_net_power = AsyncMock(return_value=True)
    coordinator._async_synchronise_charge_current_update = AsyncMock(
        side_effect=RuntimeError("boom")
    )
    event = make_event("sensor.net_power", make_state("100"), make_state("150"))

    # Must not raise despite the synchronise call failing.
    await coordinator._async_handle_net_power_update(event)


# ----------------------------------------------------------------------------
# _check_weather_provider() -- subscribe/unsubscribe state machine
# ----------------------------------------------------------------------------
async def test_weather_provider_none_and_not_tracking_is_a_noop() -> None:
    """No weather provider configured, and nothing was tracked: nothing to do."""
    tracker = make_fake_tracker()
    coordinator = make_bare_coordinator(tracker=tracker, weather_provider=None)

    coordinator._check_weather_provider()

    tracker.untrack_weather_update.assert_not_called()
    tracker.track_weather_update.assert_not_called()


async def test_weather_provider_removed_unsubscribes() -> None:
    """A previously configured provider being cleared unsubscribes tracking."""
    tracker = make_fake_tracker()
    coordinator = make_bare_coordinator(tracker=tracker, weather_provider=None)
    coordinator._weather_provider = "weather.home"
    coordinator._tracking_weather = True

    coordinator._check_weather_provider()

    tracker.untrack_weather_update.assert_called_once()
    assert coordinator._tracking_weather is False
    assert coordinator._weather_provider is None


async def test_weather_provider_newly_configured_subscribes() -> None:
    """A provider configured for the first time starts tracking."""
    tracker = make_fake_tracker()
    coordinator = make_bare_coordinator(
        tracker=tracker, weather_provider="weather.home"
    )
    coordinator._weather_provider = None
    coordinator._tracking_weather = False

    coordinator._check_weather_provider()

    tracker.track_weather_update.assert_called_once()
    assert coordinator._tracking_weather is True
    assert coordinator._weather_provider == "weather.home"


async def test_weather_provider_unchanged_does_not_resubscribe() -> None:
    """The same provider still configured does not tear down and rebuild tracking."""
    tracker = make_fake_tracker()
    coordinator = make_bare_coordinator(
        tracker=tracker, weather_provider="weather.home"
    )
    coordinator._weather_provider = "weather.home"
    coordinator._tracking_weather = True

    coordinator._check_weather_provider()

    tracker.untrack_weather_update.assert_not_called()
    tracker.track_weather_update.assert_not_called()


async def test_weather_provider_changed_resubscribes_to_the_new_one() -> None:
    """Switching providers unsubscribes the old one and subscribes the new one."""
    tracker = make_fake_tracker()
    coordinator = make_bare_coordinator(
        tracker=tracker, weather_provider="weather.other_home"
    )
    coordinator._weather_provider = "weather.home"
    coordinator._tracking_weather = True

    coordinator._check_weather_provider()

    tracker.untrack_weather_update.assert_called_once()
    tracker.track_weather_update.assert_called_once()
    assert coordinator._weather_provider == "weather.other_home"


async def test_weather_tracking_falls_back_to_untracked_when_tracker_rejects_it() -> (
    None
):
    """If the tracker fails to subscribe, the provider is not recorded as tracked."""
    tracker = make_fake_tracker(track_weather_update=Mock(return_value=False))
    coordinator = make_bare_coordinator(
        tracker=tracker, weather_provider="weather.home"
    )
    coordinator._weather_provider = None
    coordinator._tracking_weather = False

    coordinator._check_weather_provider()

    assert coordinator._tracking_weather is False
    assert coordinator._weather_provider is None
