"""Tesla Custom Charger implementation."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import CHARGER_DOMAIN_TESLA_CUSTOM  # noqa: TID252
from .charger_chargeable_base import ChargerChargeableBase

_LOGGER = logging.getLogger(__name__)


class TeslaCustomCharger(ChargerChargeableBase):
    """Implementation of the Charger class for Tesla Custom chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the Tesla Custom charger."""
        self._hass = hass
        self._entry = entry
        self._subentry = subentry
        self._device = device

        ChargerChargeableBase.__init__(self, hass, entry, subentry, device)

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
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is a Tesla Custom charger."""
        return any(
            id_domain == CHARGER_DOMAIN_TESLA_CUSTOM
            for id_domain, _ in device.identifiers
        )
