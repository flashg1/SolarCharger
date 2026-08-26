# ruff: noqa: TID252
"""BYD vehicle charger implementation."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import (
    DOMAIN_BYD_VEHICLE,
    ENTITY_BYD_START_CHARGE_BUTTON,
    ENTITY_BYD_STOP_CHARGE_BUTTON,
)
from ..models.model_config import ConfigValueDict
from .charger_chargeable_base import ChargerChargeableBase

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class BYDVehicleCharger(ChargerChargeableBase):
    """Implementation of the Charger class for BYD vehicle chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the BYD vehicle charger."""

        ChargerChargeableBase.__init__(self, hass, entry, subentry, device)

    # ----------------------------------------------------------------------------
    # Chargeable interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if the given device is an BYD vehicle charger."""

        _LOGGER.debug("%s: %s", device.name, device)
        return any(
            id_domain == DOMAIN_BYD_VEHICLE for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is a BYD vehicle charger."""

        _LOGGER.debug("%s: %s", device.name, device)
        return any(
            id_domain == DOMAIN_BYD_VEHICLE for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    def is_charger_switch_on(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is charger switched on?"""

        return self.is_charging(val_dict)

    # ----------------------------------------------------------------------------
    async def async_turn_charger_switch(
        self, turn_on: bool, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Switch on or off charger."""

        if turn_on:
            await self.async_option_press_entity_button(
                ENTITY_BYD_START_CHARGE_BUTTON, val_dict=val_dict
            )
        else:
            await self.async_option_press_entity_button(
                ENTITY_BYD_STOP_CHARGE_BUTTON, val_dict=val_dict
            )
