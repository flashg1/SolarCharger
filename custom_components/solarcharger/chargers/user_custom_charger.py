"""User Custom Charger implementation."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import DOMAIN  # noqa: TID252
from .charger_chargeable_base import ChargerChargeableBase

_LOGGER = logging.getLogger(__name__)


class UserCustomCharger(ChargerChargeableBase):
    """Implementation of the Charger class for User Custom chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the User Custom charger."""

        ChargerChargeableBase.__init__(self, hass, entry, subentry, device)

    # ----------------------------------------------------------------------------
    # Chargeable interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if the given device is an User Custom charger."""
        return any(id_domain == DOMAIN for id_domain, _ in device.identifiers)

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is a User Custom charger."""
        return any(id_domain == DOMAIN for id_domain, _ in device.identifiers)
