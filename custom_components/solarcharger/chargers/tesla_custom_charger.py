"""Tesla Custom Charger implementation."""

import logging

from sqlalchemy import true

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import (  # noqa: TID252
    CHARGER_DOMAIN_TESLA_CUSTOM,
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
from ..sc_option_state import ScOptionState  # noqa: TID252
from .chargeable import Chargeable
from .charger import Charger

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class TeslaCustomCharger(HaDevice, ScOptionState, Charger, Chargeable):
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
        self.device_entry = device_entry

        # TeslaCustomEntityMap.__init__(self, config_entry, config_subentry)
        HaDevice.__init__(self, hass, device_entry)
        ScOptionState.__init__(self, hass, config_entry, config_subentry, __name__)
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
    def get_chargeable_name(self) -> str:
        """Get chargeable name."""
        return self.device_entry.id

    # ----------------------------------------------------------------------------
    async def async_setup_chargeable(self) -> None:
        """Set up chargeable device."""
        # self.wake_up_chargee()
        # await asyncio.sleep(WAIT_CHARGEE_WAKEUP)
        # self.get_chargee_update()
        # await asyncio.sleep(WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    async def async_wake_up(self) -> None:
        """Wake up chargeable device."""
        await self.async_option_button_press(OPTION_CHARGEE_WAKE_UP_BUTTON)

    # ----------------------------------------------------------------------------
    async def async_update_ha(self) -> None:
        """Force chargeable device to update data in HA."""
        await self.async_option_button_press(OPTION_CHARGEE_UPDATE_HA_BUTTON)

    # ----------------------------------------------------------------------------
    def is_at_location(self) -> bool:
        """Is chargeable device at charger location?"""
        is_at_location = False

        # 'device_tracker.tesla23m3_location_tracker' = 'not_home' or 'home'
        state = self.option_get_string(OPTION_CHARGEE_LOCATION_SENSOR)
        state_list = self.option_get_data_list(OPTION_CHARGEE_LOCATION_STATE_LIST)
        if state is not None and state_list is not None:
            is_at_location = state in state_list

        return is_at_location

    # ----------------------------------------------------------------------------
    def get_state_of_charge(self) -> int | None:
        """Get state of charge (SoC) of chargeable device."""
        return self.option_get_integer(OPTION_CHARGEE_SOC_SENSOR)

    # ----------------------------------------------------------------------------
    def get_charge_limit(self) -> int | None:
        """Get chargeable device charge limit."""
        return self.option_get_integer(OPTION_CHARGEE_CHARGE_LIMIT)

    # ----------------------------------------------------------------------------
    async def async_set_charge_limit(self, charge_limit: int) -> None:
        """Set chargeable device charge limit."""
        if not 50 <= charge_limit <= 100:
            msg = "Invalid charge limit. Must be between 50 and 100."
            raise ValueError(msg)
        await self.async_option_set_integer(OPTION_CHARGEE_CHARGE_LIMIT, charge_limit)

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is a Tesla Custom charger."""
        return any(
            id_domain == CHARGER_DOMAIN_TESLA_CUSTOM
            for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    def get_charger_name(self) -> str:
        """Get charger name."""
        return self.device_entry.id

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Set up the charger."""
        await self.async_setup_chargeable()

    # ----------------------------------------------------------------------------
    def get_max_charge_current(self) -> float | None:
        """Get charger max allowable current in amps."""
        return self.option_get_number(OPTION_CHARGER_MAX_CURRENT)

    # ----------------------------------------------------------------------------
    def get_connect_state(self) -> str | None:
        """Get charger connect state."""
        return self.option_get_string(OPTION_CHARGER_PLUGGED_IN_SENSOR)

    # ----------------------------------------------------------------------------
    def is_connected(self) -> bool:
        """Is charger connected to chargeable device?"""
        is_connected = False

        state = self.get_connect_state()
        state_list = self.option_get_data_list(OPTION_CHARGER_CONNECT_STATE_LIST)
        if state is not None and state_list is not None:
            is_connected = state in state_list

        return is_connected

    # ----------------------------------------------------------------------------
    def is_charger_on(self) -> bool:
        """Is charger switched on?"""
        switched_on = False

        state = self.option_get_string(OPTION_CHARGER_ON_OFF_SWITCH)
        if state == "on":
            switched_on = True

        return switched_on

    # ----------------------------------------------------------------------------
    async def async_charger_switch_on(self) -> None:
        """Switch on charger."""
        await self.async_option_switch_on(OPTION_CHARGER_ON_OFF_SWITCH)

    # ----------------------------------------------------------------------------
    async def async_charger_switch_off(self) -> None:
        """Switch off charger."""
        await self.async_option_switch_off(OPTION_CHARGER_ON_OFF_SWITCH)

    # ----------------------------------------------------------------------------
    def get_charging_state(self) -> str | None:
        """Get charging state."""
        return self.option_get_string(OPTION_CHARGER_CHARGING_SENSOR)

    # ----------------------------------------------------------------------------
    def is_charging(self) -> bool:
        """Is device charging?"""
        is_charging = False

        state = self.get_charging_state()
        state_list = self.option_get_data_list(OPTION_CHARGER_CHARGING_STATE_LIST)
        if state is not None and state_list is not None:
            is_charging = state in state_list

        return is_charging

    # ----------------------------------------------------------------------------
    def get_charge_current(self) -> float | None:
        """Get charger charge current in AMPS."""
        return self.option_get_number(OPTION_CHARGER_GET_CHARGE_CURRENT)

    # ----------------------------------------------------------------------------
    async def async_set_charge_current(self, charge_current: float) -> None:
        """Set charger charge current in AMPS."""
        await self.async_option_set_integer(
            OPTION_CHARGER_GET_CHARGE_CURRENT, int(charge_current)
        )

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the Tesla Custom charger."""
