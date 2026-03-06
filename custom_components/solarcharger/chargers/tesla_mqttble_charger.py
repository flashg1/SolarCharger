"""Tesla MQTT BLE Charger implementation."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import MQTT_TESLA_BLE_MANUFACTURER, MQTT_TESLA_BLE_MODEL  # noqa: TID252
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
    def is_matched_device(device: DeviceEntry) -> bool:
        """Check if the given device is a Tesla ESPHome BLE charger."""

        _LOGGER.debug("%s: %s", device.name, device)

        if device is None or device.manufacturer is None or device.model is None:
            return False

        if (
            device.manufacturer == MQTT_TESLA_BLE_MANUFACTURER
            and device.model == MQTT_TESLA_BLE_MODEL
        ):
            return True

        return False

    # ----------------------------------------------------------------------------
    @staticmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if the given device is an Tesla MQTT BLE charger."""

        # _LOGGER.debug("%s: %s", device.name, device)
        # return any(
        #     id_domain == CHARGER_DOMAIN_MQTT for id_domain, _ in device.identifiers
        # )
        return TeslaMqttBleCharger.is_matched_device(device)

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is a Tesla MQTT BLE charger."""

        # _LOGGER.debug("%s: %s", device.name, device)
        # return any(
        #     id_domain == CHARGER_DOMAIN_MQTT for id_domain, _ in device.identifiers
        # )
        return TeslaMqttBleCharger.is_matched_device(device)
