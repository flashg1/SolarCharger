"""Tessie charger implementation."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import DOMAIN_TESSIE  # noqa: TID252
from .charger_chargeable_base import ChargerChargeableBase

_LOGGER = logging.getLogger(__name__)


class TessieCharger(ChargerChargeableBase):
    """Implementation of the Charger class for Tessie chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the Tessie charger."""

        ChargerChargeableBase.__init__(self, hass, entry, subentry, device)

    # ----------------------------------------------------------------------------
    # Chargeable interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if the given device is an Tessie charger."""

        _LOGGER.debug("%s: %s", device.name, device)
        return any(id_domain == DOMAIN_TESSIE for id_domain, _ in device.identifiers)

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is a Tessie charger."""

        _LOGGER.debug("%s: %s", device.name, device)
        return any(id_domain == DOMAIN_TESSIE for id_domain, _ in device.identifiers)
