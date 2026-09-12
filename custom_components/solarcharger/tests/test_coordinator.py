# ruff: noqa: SLF001
"""Unit tests for SolarChargerCoordinator (modules/coordinator.py).

SolarChargerCoordinator.__init__ constructs a real Tracker, same as
ChargeController, so these tests bypass __init__ via __new__() and wire up
small fakes for _tracker instead -- see test_controller.py for the same
rationale. Each DeviceControl's .controller is a fake exposing only the
ChargeController surface the coordinator itself calls (the switch delegation
methods, .charge_control, .async_check_if_need_to_reschedule_charge, ...),
not a real ChargeController.

Net power allocation, charge-current synchronisation and weather-provider
tracking used to live on the coordinator (and were tested here), but moved to
ChargeController -- each is now only ever driven by the Global Defaults
device's own controller instance, not the coordinator. That coverage now
lives in test_controller.py; the coordinator's own async_reset_charge_limit_default()
is likewise just a delegate to control.controller now, so it's tested as a
delegation only, same as the switch methods below.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from custom_components.solarcharger.const import OPTION_GLOBAL_DEFAULTS_ID
from custom_components.solarcharger.models.model_charge_control import (
    ChargeControl,
    ControlEntities,
)
from custom_components.solarcharger.models.model_device_control import DeviceControl
from custom_components.solarcharger.modules.coordinator import SolarChargerCoordinator
import pytest

from .conftest import make_config_entry, make_hass, make_subentry

GLOBAL_DEFAULTS_SUBENTRY_ID = "global-defaults"
HOT_WATER_SUBENTRY_ID = "hot-water"


# ----------------------------------------------------------------------------
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
        "async_reset_charge_limit_default": AsyncMock(),
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
# async_reset_charge_limit_default() -- delegates to the device's controller
#
# The actual reset logic (validating each day's default against
# [min, max], pushing numbers/times) now lives on ChargeController itself
# and is tested in test_controller.py; the coordinator's own version is just
# a delegate, same as the switch methods above.
# ----------------------------------------------------------------------------
async def test_reset_charge_limit_default_delegates_to_the_device_controller() -> None:
    """The coordinator just forwards to the matching controller method."""
    controller = make_fake_controller()
    coordinator = make_bare_coordinator()
    control = make_device_control(
        HOT_WATER_SUBENTRY_ID, "hot_water", controller=controller
    )

    await coordinator.async_reset_charge_limit_default(control)

    controller.async_reset_charge_limit_default.assert_awaited_once()


async def test_reset_charge_limit_default_is_a_noop_without_a_controller() -> None:
    """A DeviceControl with no controller has nothing to delegate to."""
    coordinator = make_bare_coordinator()
    control = DeviceControl(
        subentry_id=GLOBAL_DEFAULTS_SUBENTRY_ID,
        config_name=OPTION_GLOBAL_DEFAULTS_ID,
        controller=None,  # type: ignore[arg-type]
    )

    # Must not raise despite controller being None.
    await coordinator.async_reset_charge_limit_default(control)
