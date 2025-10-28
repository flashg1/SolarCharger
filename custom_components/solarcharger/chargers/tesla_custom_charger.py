"""Tesla Custom Charger implementation."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..config_option_utils import get_saved_option_value  # noqa: TID252
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
    def get_config(self, config_item) -> Any:
        """Get config from options."""

        return get_saved_option_value(
            self.config_entry, self.config_subentry, config_item, use_default=True
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
        await self.async_button_press(self.get_config(OPTION_CHARGEE_WAKE_UP_BUTTON))

    # ----------------------------------------------------------------------------
    async def async_get_chargee_update(self) -> None:
        """Force chargeable device to update data in HA."""
        await self.async_button_press(self.get_config(OPTION_CHARGEE_UPDATE_HA_BUTTON))

    # ----------------------------------------------------------------------------
    def get_state_of_charge(self) -> int | None:
        """Get the current state of charge (SoC) of the chargeable device."""
        return self.get_integer(self.get_config(OPTION_CHARGEE_SOC_SENSOR))

    # ----------------------------------------------------------------------------
    def get_charge_limit(self) -> int | None:
        """Get chargeable device charge limit."""
        return self.get_integer(self.get_config(OPTION_CHARGEE_CHARGE_LIMIT))

    # ----------------------------------------------------------------------------
    async def async_set_charge_limit(self, charge_limit: int) -> None:
        """Set chargeable device charge limit."""
        if not 50 <= charge_limit <= 100:
            msg = "Invalid charge limit. Must be between 50 and 100."
            raise ValueError(msg)
        await self.async_set_integer(
            self.get_config(OPTION_CHARGEE_CHARGE_LIMIT), charge_limit
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
        await self.async_set_integer(
            self.get_config(OPTION_CHARGER_CHARGING_AMPS), int(charge_current)
        )

    # ----------------------------------------------------------------------------
    def get_charge_current(self) -> float | None:
        """Get the current limit of the charger in amps."""
        return self.get_number(self.get_config(OPTION_CHARGER_CHARGING_AMPS))

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
        return self._get_state(self.get_config(OPTION_CHARGER_PLUGGED_IN_SENSOR))

    # ----------------------------------------------------------------------------
    def car_connected(self) -> bool:
        """Car is connected to the charger and ready to receive charge."""
        status = self._get_connect_state()
        return status in self.get_config(OPTION_CHARGER_CONNECT_STATE_LIST)

    # ----------------------------------------------------------------------------
    def _get_charging_state(self) -> str | None:
        """Get charging state of Tesla Custom charger."""
        return self._get_state(self.get_config(OPTION_CHARGER_CHARGING_SENSOR))

    # ----------------------------------------------------------------------------
    def can_charge(self) -> bool:
        """Return whether the car is connected and charging or accepting charge."""
        status = self._get_charging_state()
        return status in self.get_config(OPTION_CHARGER_CHARGING_STATE_LIST)

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the Tesla Custom charger."""

    # ----------------------------------------------------------------------------
    # Utils
    # ----------------------------------------------------------------------------
    def get_integer(self, entity: str) -> int | None:
        """Get integer entity."""
        num: float | None = self.get_number(entity)
        if num is None:
            return None
        return int(num)

    # ----------------------------------------------------------------------------
    def get_number(self, entity: str) -> float | None:
        """Get number entity."""
        state = self._get_state(entity)

        if state is None:
            _LOGGER.warning(
                "State of charge not available for Tesla Custom charger %s. "
                "Make sure the required entity (%s) is enabled and available",
                self.device_entry.id,
                entity,
            )
            return None

        try:
            # return int(float(state))
            return float(state)
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Failed to parse state '%s' of '%s' for Tesla Custom charger %s: %s",
                state,
                entity,
                self.device_entry.id,
                e,
            )
            return None

    # ----------------------------------------------------------------------------
    # def _get_state(self, entity: str) -> Any | None:
    #     """Get connect state of Tesla Custom charger."""
    #     status: Any | None = None

    #     try:
    #         status = self._get_entity_state_by_unique_id(entity)
    #     except ValueError as e:
    #         _LOGGER.debug(
    #             "Failed to get state for Tesla Custom charger entity '%s': '%s'",
    #             entity,
    #             e,
    #         )

    #     return status

    # ----------------------------------------------------------------------------
    def _get_state(self, entity_id: str) -> float | None:
        entity = self.hass.states.get(entity_id)
        if entity is None:
            _LOGGER.debug("State not found for entity %s", entity_id)
            return None
        state_value = entity.state
        try:
            return float(state_value)
        except ValueError as ex:
            _LOGGER.exception(
                "Failed to parse state %s for entity %s: %s",
                state_value,
                entity_id,
                ex,  # noqa: TRY401
            )
            return None

    # ----------------------------------------------------------------------------
    async def async_set_integer(self, entity: str, num: int) -> None:
        """Set integer entity."""
        await self.set_number(entity, float(num))

    # ----------------------------------------------------------------------------
    async def set_number(self, entity: str, num: float) -> None:
        """Set number entity."""

        try:
            # Call the Home Assistant number.set_value service
            await self.hass.services.async_call(
                domain="number",
                service="set_value",
                service_data={
                    "entity_id": entity,
                    "value": num,
                },
                blocking=True,
            )
        except (ValueError, RuntimeError, TimeoutError) as e:
            _LOGGER.warning(
                "Failed to set %s to %d for Tesla Custom charger %s: %s",
                entity,
                num,
                self.device_entry.id,
                e,
            )

    # ----------------------------------------------------------------------------
    async def async_button_press(self, entity: str) -> None:
        """Press a button entity."""
        try:
            # Call the Home Assistant button.press service
            await self.hass.services.async_call(
                domain="button",
                service="press",
                service_data={
                    "entity_id": entity,
                },
                blocking=True,
            )
        except (ValueError, RuntimeError, TimeoutError) as e:
            _LOGGER.warning(
                "Button press %s failed for Tesla Custom charger %s: %s",
                entity,
                self.device_entry.id,
                e,
            )
