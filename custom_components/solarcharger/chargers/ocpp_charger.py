"""OCPP Charger implementation."""

import logging
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import (  # noqa: TID252
    CHARGER_DOMAIN_OCPP,
    OPTION_OCPP_CHARGER_ID,
    OPTION_OCPP_TRANSACTION_ID,
)
from ..model_config import ConfigValueDict  # noqa: TID252
from .charger_chargeable_base import ChargerChargeableBase

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class OcppCharger(ChargerChargeableBase):
    """Implementation of the Charger class for OCPP chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the OCPP charger."""

        ChargerChargeableBase.__init__(self, hass, entry, subentry, device)

    # ----------------------------------------------------------------------------
    # Chargeable interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if the given device is an OCPP charger."""
        return any(
            id_domain == CHARGER_DOMAIN_OCPP for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    # Charger interface implementation
    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if the given device is an OCPP charger."""
        return any(
            id_domain == CHARGER_DOMAIN_OCPP for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    # 2025-11-03 11:53:39.370 INFO (MainThread) [ocpp] sn123456789: send [2,"3cf0a97a-6bd3-4ecd-b914-c9a57ec0b3be","GetConfiguration",{"key":["ChargeProfileMaxStackLevel"]}]
    # 2025-11-03 11:53:39.376 INFO (MainThread) [ocpp] sn123456789: receive message [3,"3cf0a97a-6bd3-4ecd-b914-c9a57ec0b3be",
    # {"configurationKey":[{"key":"ChargeProfileMaxStackLevel","readonly":true,"value":"20"}]}]

    async def _async_get_ocpp_max_stack_level(self) -> ServiceResponse:
        """Get OCPP charge profile max stack level. This stack level will be used to override all others."""
        # ocpp_max_stack_level_map: dict[str, Any] = {}

        ocpp_charger_id = self.option_get_entity_string(OPTION_OCPP_CHARGER_ID)
        # service_name = "ocpp.get_configuration"
        service_name = "get_configuration"
        service_data: dict[str, Any] = {
            "devid": ocpp_charger_id,
            "ocpp_key": "ChargeProfileMaxStackLevel",
        }

        ocpp_max_stack_level_map: ServiceResponse = await self.async_ha_call(
            CHARGER_DOMAIN_OCPP,
            service_name,
            service_data,
            # target=ocpp_max_stack_level_map,
            return_response=True,
        )

        return ocpp_max_stack_level_map

    # ----------------------------------------------------------------------------
    async def async_set_charge_current(
        self, charge_current: float, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Set charger charge current."""

        new_charge_current = int(round(charge_current))
        ocpp_charger_transaction_id = self.option_get_entity_integer(
            OPTION_OCPP_TRANSACTION_ID
        )

        # Get the OCPP charge profile max stack level to override all other profiles.
        ocpp_max_stack_level_map: ServiceResponse = (
            await self._async_get_ocpp_max_stack_level()
        )
        if ocpp_max_stack_level_map is not None:
            json_val: str = cast(str, ocpp_max_stack_level_map.get("value"))
            max_stack_level: int = int(json_val)

            service_name = "set_charge_rate"
            service_data: dict[str, Any] = {
                "custom_profile": {
                    "transactionId": ocpp_charger_transaction_id,
                    "chargingProfileId": 1,
                    "stackLevel": max_stack_level,
                    "chargingProfilePurpose": "TxProfile",
                    "chargingProfileKind": "Relative",
                    "chargingSchedule": {
                        "chargingRateUnit": "A",
                        "chargingSchedulePeriod": [
                            {"startPeriod": 0, "limit": new_charge_current}
                        ],
                    },
                },
                "conn_id": 1,
            }

            await self.async_ha_call(CHARGER_DOMAIN_OCPP, service_name, service_data)

    # ----------------------------------------------------------------------------
    # async def async_set_charge_current(
    #     self, charge_current: float, val_dict: ConfigValueDict | None = None
    # ) -> None:
    #     """Set charger charge current."""
    #     min_current = charge_current

    #     try:
    #         await self.hass.services.async_call(
    #             domain=CHARGER_DOMAIN_OCPP,
    #             service="set_charge_rate",
    #             service_data={
    #                 "device_id": self.device_entry.id,
    #                 "limit_amps": min_current,
    #             },
    #             blocking=True,
    #         )
    #     except (ValueError, RuntimeError, TimeoutError) as e:
    #         _LOGGER.warning(
    #             "Failed to set current limit for OCPP charger %s: %s",
    #             self.device_entry.id,
    #             e,
    #         )
