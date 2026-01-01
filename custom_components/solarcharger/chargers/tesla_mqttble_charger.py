"""Tesla MQTT BLE Charger implementation."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import CHARGER_DOMAIN_TESLA_MQTTBLE  # noqa: TID252
from .charger_chargeable_base import ChargerChargeableBase

_LOGGER = logging.getLogger(__name__)


class TeslaMqttBleCharger(ChargerChargeableBase):
    """Implementation of the Charger class for Tesla MQTT BLE chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the Tesla MQTT BLE charger."""

        ChargerChargeableBase.__init__(self, hass, entry, subentry, device)

    # ----------------------------------------------------------------------------
    # Chargeable interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if the given device is an Tesla MQTT BLE charger."""
        return any(
            id_domain == CHARGER_DOMAIN_TESLA_MQTTBLE
            for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is a Tesla MQTT BLE charger."""
        return any(
            id_domain == CHARGER_DOMAIN_TESLA_MQTTBLE
            for id_domain, _ in device.identifiers
        )
