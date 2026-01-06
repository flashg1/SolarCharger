"""Charger and Chargeable base class implementation."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import (  # noqa: TID252
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_LOCATION_STATE_LIST,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_CHARGING_STATE_LIST,
    OPTION_CHARGER_CONNECT_STATE_LIST,
    OPTION_CHARGER_GET_CHARGE_CURRENT,
    OPTION_CHARGER_MAX_CURRENT,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
)
from ..ha_device import HaDevice  # noqa: TID252
from ..model_config import ConfigValueDict  # noqa: TID252
from ..sc_option_state import ScOptionState  # noqa: TID252
from .chargeable import Chargeable
from .charger import Charger

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ChargerChargeableBase(HaDevice, ScOptionState, Charger, Chargeable):
    """Implementation of the Charger and Chargeable base classes."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the charger and chargeable devices."""

        caller = subentry.unique_id
        if caller is None:
            caller = __name__

        HaDevice.__init__(self, hass, device)
        ScOptionState.__init__(self, hass, entry, subentry, caller)
        Charger.__init__(self, hass, entry, subentry, device)
        Chargeable.__init__(self, hass, entry, subentry, device)

        self.refresh_entities()

    # ----------------------------------------------------------------------------
    # Chargeable interface implementation
    # ----------------------------------------------------------------------------
    # @staticmethod
    # def is_chargeable_device(device: DeviceEntry) -> bool:
    #     """Check if the given device is an Tesla Custom charger."""
    #     return any(
    #         id_domain == CHARGER_DOMAIN_TESLA_CUSTOM
    #         for id_domain, _ in device.identifiers
    #     )

    # ----------------------------------------------------------------------------
    def get_chargeable_name(self) -> str:
        """Get chargeable name."""
        return self._device.id

    # ----------------------------------------------------------------------------
    async def async_setup_chargeable(self) -> None:
        """Set up chargeable device."""
        # self.wake_up_chargee()
        # await asyncio.sleep(WAIT_CHARGEE_WAKEUP)
        # self.get_chargee_update()
        # await asyncio.sleep(WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    async def async_wake_up(self, val_dict: ConfigValueDict | None = None) -> None:
        """Wake up chargeable device."""
        await self.async_option_press_entity_button(
            OPTION_CHARGEE_WAKE_UP_BUTTON, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    async def async_update_ha(self, val_dict: ConfigValueDict | None = None) -> None:
        """Force chargeable device to update data in HA."""
        await self.async_option_press_entity_button(
            OPTION_CHARGEE_UPDATE_HA_BUTTON, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    def is_at_location(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is chargeable device at charger location?"""
        is_at_location = False

        # 'device_tracker.tesla23m3_location_tracker' = 'not_home' or 'home'
        state = self.option_get_entity_string(
            OPTION_CHARGEE_LOCATION_SENSOR, val_dict=val_dict
        )
        state_list = self.option_get_list(
            OPTION_CHARGEE_LOCATION_STATE_LIST, val_dict=val_dict
        )
        if state is not None and state_list is not None:
            is_at_location = state in state_list

        return is_at_location

    # ----------------------------------------------------------------------------
    def get_state_of_charge(
        self, val_dict: ConfigValueDict | None = None
    ) -> int | None:
        """Get state of charge (SoC) of chargeable device."""
        return self.option_get_entity_integer(
            OPTION_CHARGEE_SOC_SENSOR, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    def get_charge_limit(self, val_dict: ConfigValueDict | None = None) -> float | None:
        """Get chargeable device charge limit."""
        return self.option_get_entity_number(
            OPTION_CHARGEE_CHARGE_LIMIT, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    async def async_set_charge_limit(
        self, charge_limit: float, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Set chargeable device charge limit."""
        min_limit = self.option_get_entity_number_or_abort(
            NUMBER_CHARGEE_MIN_CHARGE_LIMIT, val_dict=val_dict
        )
        max_limit = self.option_get_entity_number_or_abort(
            NUMBER_CHARGEE_MAX_CHARGE_LIMIT, val_dict=val_dict
        )
        if not min_limit <= charge_limit <= max_limit:
            msg = f"Invalid charge limit {charge_limit}. Must be between {min_limit} and {max_limit} %%."
            raise ValueError(msg)
        await self.async_option_set_entity_number(
            OPTION_CHARGEE_CHARGE_LIMIT, charge_limit, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    # @staticmethod
    # def is_charger_device(device: DeviceEntry) -> bool:
    #     """Check if device is a Tesla Custom charger."""
    #     return any(
    #         id_domain == CHARGER_DOMAIN_TESLA_CUSTOM
    #         for id_domain, _ in device.identifiers
    #     )

    # ----------------------------------------------------------------------------
    def get_charger_name(self) -> str:
        """Get charger name."""
        return self._device.id

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Set up the charger."""
        await self.async_setup_chargeable()

    # ----------------------------------------------------------------------------
    def get_max_charge_current(
        self, val_dict: ConfigValueDict | None = None
    ) -> float | None:
        """Get charger max allowable current in amps."""
        return self.option_get_entity_number(
            OPTION_CHARGER_MAX_CURRENT, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    def is_connected(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is charger connected to chargeable device?"""
        is_connected = False

        state = self.option_get_entity_string(
            OPTION_CHARGER_PLUGGED_IN_SENSOR, val_dict=val_dict
        )
        state_list = self.option_get_list(
            OPTION_CHARGER_CONNECT_STATE_LIST, val_dict=val_dict
        )
        if state is not None and state_list is not None:
            is_connected = state in state_list

        return is_connected

    # ----------------------------------------------------------------------------
    def is_charger_switch_on(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is charger switched on?"""
        switched_on = False

        state = self.option_get_entity_string(
            OPTION_CHARGER_ON_OFF_SWITCH, val_dict=val_dict
        )
        if state == STATE_ON:
            switched_on = True

        return switched_on

    # ----------------------------------------------------------------------------
    async def async_turn_charger_switch_on(
        self, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Switch on charger."""
        await self.async_option_turn_entity_switch_on(
            OPTION_CHARGER_ON_OFF_SWITCH, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    async def async_turn_charger_switch_off(
        self, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Switch off charger."""
        await self.async_option_turn_entity_switch_off(
            OPTION_CHARGER_ON_OFF_SWITCH, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    def is_charging(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is device charging?"""
        is_charging = False

        state = self.option_get_entity_string(
            OPTION_CHARGER_CHARGING_SENSOR, val_dict=val_dict
        )
        state_list = self.option_get_list(OPTION_CHARGER_CHARGING_STATE_LIST)
        if state is not None and state_list is not None:
            is_charging = state in state_list

        return is_charging

    # ----------------------------------------------------------------------------
    def get_charge_current(
        self, val_dict: ConfigValueDict | None = None
    ) -> float | None:
        """Get charger charge current in AMPS."""
        return self.option_get_entity_number(
            OPTION_CHARGER_GET_CHARGE_CURRENT, val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    async def async_set_charge_current(
        self, charge_current: float, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Set charger charge current in AMPS."""
        await self.async_option_set_entity_integer(
            OPTION_CHARGER_GET_CHARGE_CURRENT, int(charge_current), val_dict=val_dict
        )

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the Tesla Custom charger."""
