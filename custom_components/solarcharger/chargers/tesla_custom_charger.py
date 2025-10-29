"""Tesla Custom Charger implementation."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import (  # noqa: TID252
    CHARGER_DOMAIN_TESLA_CUSTOM,
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_CHARGING_AMPS,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_CHARGING_STATE_LIST,
    OPTION_CHARGER_CONNECT_STATE_LIST,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
)
from ..ha_device import HaDevice  # noqa: TID252
from ..ha_state import HaState  # noqa: TID252
from .chargeable import Chargeable
from .charger import Charger

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# class TeslaCustomEntityMap:
#     """Map Tesla Custom entities to their respective attributes."""

#     _car_name = ""
#     # Status entities from HAChargerStatuses
#     ChargerConnectState = f"binary_sensor.{_car_name}charger"
#     ChargerSwitch = f"switch.{_car_name}charger"
#     ChargerChargingState = f"binary_sensor.{_car_name}charging"
#     ChargerCurrent = f"number.{_car_name}charging_amps"

#     ChargeeWakeUp = f"button.{_car_name}wake_up"
#     ChargeeUpdate = f"button.{_car_name}force_data_update"
#     ChargeeStateOfCharge = f"sensor.{_car_name}battery"
#     ChargeeChargeLimit = f"number.{_car_name}charge_limit"
#     ChargeeLocation = f"device_tracker.{_car_name}location_tracker"

#     def __init__(
#         self,
#         config_entry: ConfigEntry,
#         config_subentry: ConfigSubentry,
#     ) -> None:
#         """Initialize the TeslaCustomEntityMap."""
#         self.config_entry = config_entry
#         self.config_subentry = config_subentry

#         if not self.config_subentry.unique_id:
#             raise ValueError("Config subentry unique_id is required")


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class TeslaCustomChargerConnectStateMap:
    """Map Tesla Custom charger connected states."""

    On = "on"

    # Consider the chargee is connected if the charger is in any of these states.
    ConnectedStateList = [On]


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class TeslaCustomChargerChargingStateMap:
    """Map Tesla Custom charger charging states."""

    On = "on"

    # Consider the chargee is charging or ready to charge if the charger is in any of these states.
    ChargingStateList = [On]


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class TeslaCustomCharger(HaDevice, Charger, Chargeable):
    """Implementation of the Charger class for Tesla Custom chargers."""

    # Also need to implement following,
    # OPTION_CHARGER_ON_OFF_SWITCH,
    # OPTION_CHARGEE_LOCATION_SENSOR,

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        config_subentry: ConfigSubentry,
        device_entry: DeviceEntry,
    ) -> None:
        """Initialize the Tesla Custom charger."""
        self.hass = hass
        self.config_entry = config_entry
        self.config_subentry = config_subentry
        self._ha_state = HaState(hass, config_entry, config_subentry, __name__)

        # TeslaCustomEntityMap.__init__(self, config_entry, config_subentry)
        HaDevice.__init__(self, hass, device_entry)
        Charger.__init__(self, hass, config_entry, config_subentry, device_entry)
        Chargeable.__init__(self, hass, config_entry, config_subentry, device_entry)
        self.refresh_entities()

    # ----------------------------------------------------------------------------
    # Chargeable interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if the given device is an Tesla Custom charger."""
        return any(
            id_domain == CHARGER_DOMAIN_TESLA_CUSTOM
            for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    async def async_setup_chargeable(self) -> None:
        """Set up chargeable device."""
        # self.wake_up_chargee()
        # await asyncio.sleep(WAIT_CHARGEE_WAKEUP)
        # self.get_chargee_update()
        # await asyncio.sleep(WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    async def async_wake_up_chargee(self) -> None:
        """Wake up chargeable device."""
        await self._ha_state.async_press_entity_button(OPTION_CHARGEE_WAKE_UP_BUTTON)

    # ----------------------------------------------------------------------------
    async def async_get_chargee_update(self) -> None:
        """Force chargeable device to update data in HA."""
        await self._ha_state.async_press_entity_button(OPTION_CHARGEE_UPDATE_HA_BUTTON)

    # ----------------------------------------------------------------------------
    def get_state_of_charge(self) -> int | None:
        """Get the current state of charge (SoC) of the chargeable device."""
        return self._ha_state.get_entity_integer(OPTION_CHARGEE_SOC_SENSOR)

    # ----------------------------------------------------------------------------
    def get_charge_limit(self) -> int | None:
        """Get chargeable device charge limit."""
        return self._ha_state.get_entity_integer(OPTION_CHARGEE_CHARGE_LIMIT)

    # ----------------------------------------------------------------------------
    async def async_set_charge_limit(self, charge_limit: int) -> None:
        """Set chargeable device charge limit."""
        if not 50 <= charge_limit <= 100:
            msg = "Invalid charge limit. Must be between 50 and 100."
            raise ValueError(msg)
        await self._ha_state.async_set_entity_integer(
            OPTION_CHARGEE_CHARGE_LIMIT, charge_limit
        )

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if the given device is an Tesla Custom charger."""
        return any(
            id_domain == CHARGER_DOMAIN_TESLA_CUSTOM
            for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Set up the charger."""
        await self.async_setup_chargeable()

    # ----------------------------------------------------------------------------
    async def set_charge_current(self, charge_current: float) -> None:
        """Set charger charge current."""
        await self._ha_state.async_set_entity_integer(
            OPTION_CHARGER_CHARGING_AMPS, int(charge_current)
        )

    # ----------------------------------------------------------------------------
    def get_charge_current(self) -> float | None:
        """Get the current limit of the charger in amps."""
        return self._ha_state.get_entity_number(OPTION_CHARGER_CHARGING_AMPS)

    # ----------------------------------------------------------------------------
    def get_max_charge_current(self) -> float | None:
        """Get the configured maximum current limit of the charger in amps."""
        _LOGGER.info(
            "No maximum current limit information available for Tesla Custom charger %s, "
            "using default 15A",
            self.device_entry.id,
        )
        return 15.0  # Assume a default max current limit of 15A

    # ----------------------------------------------------------------------------
    def _get_connect_state(self) -> str | None:
        """Get connect state of Tesla Custom charger."""
        return self._ha_state.get_entity_string(OPTION_CHARGER_PLUGGED_IN_SENSOR)

    # ----------------------------------------------------------------------------
    def car_connected(self) -> bool:
        """Car is connected to the charger and ready to receive charge."""
        is_connected = False

        state = self._get_connect_state()
        state_list = self._ha_state.get_config(OPTION_CHARGER_CONNECT_STATE_LIST)
        if state is not None and state_list is not None:
            is_connected = state in state_list

        return is_connected

    # ----------------------------------------------------------------------------
    def _get_charging_state(self) -> str | None:
        """Get charging state of Tesla Custom charger."""
        return self._ha_state.get_entity_string(OPTION_CHARGER_CHARGING_SENSOR)

    # ----------------------------------------------------------------------------
    def can_charge(self) -> bool:
        """Return whether the car is connected and charging or accepting charge."""
        is_charging = False

        state = self._get_charging_state()
        state_list = self._ha_state.get_config(OPTION_CHARGER_CHARGING_STATE_LIST)
        if state is not None and state_list is not None:
            is_charging = state in state_list

        return is_charging

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the Tesla Custom charger."""
