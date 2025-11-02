"""OCPP Charger implementation."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import (  # noqa: TID252
    CHARGER_DOMAIN_OCPP,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_CHARGING_STATE_LIST,
    OPTION_CHARGER_CONNECT_STATE_LIST,
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
class OcppEntityMap:
    """Map OCPP entities to their respective attributes."""

    # Status entities from HAChargerStatuses
    Status = "Status"
    StatusConnector = "Status.Connector"

    # Current limit via number metric
    # https://github.com/lbbrhzn/ocpp/blob/main/custom_components/ocpp/number.py
    MaximumCurrent = "maximum_current"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class OcppStatusMap:
    """Map OCPP charger statuses."""

    Available = "Available"
    Preparing = "Preparing"
    Charging = "Charging"
    SuspendedEVSE = "SuspendedEVSE"
    SuspendedEV = "SuspendedEV"
    Finishing = "Finishing"
    Reserved = "Reserved"
    Unavailable = "Unavailable"
    Faulted = "Faulted"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class OcppCharger(HaDevice, ScOptionState, Charger, Chargeable):
    """Implementation of the Charger class for OCPP chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        config_subentry: ConfigSubentry,
        device_entry: DeviceEntry,
    ) -> None:
        """Initialize the OCPP charger."""
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
        """Check if the given device is an OCPP charger."""
        return any(
            id_domain == CHARGER_DOMAIN_OCPP for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    def get_chargeable_name(self) -> str:
        """Get chargeable name."""
        return self.device_entry.id

    # ----------------------------------------------------------------------------
    async def async_setup_chargeable(self) -> None:
        """Set up the charger."""
        return

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
        return self.option_get_entity_number(OPTION_CHARGER_MAX_CURRENT)

    # ----------------------------------------------------------------------------
    def is_connected(self) -> bool:
        """Is charger connected to chargeable device?"""
        is_connected = False

        state = self.option_get_entity_string(OPTION_CHARGER_PLUGGED_IN_SENSOR)
        state_list = self.option_get_list(OPTION_CHARGER_CONNECT_STATE_LIST)
        if state is not None and state_list is not None:
            is_connected = state in state_list

        return is_connected

    # ----------------------------------------------------------------------------
    def is_charger_switch_on(self) -> bool:
        """Is charger switched on?"""
        switched_on = False

        state = self.option_get_entity_string(OPTION_CHARGER_ON_OFF_SWITCH)
        if state == "on":
            switched_on = True

        return switched_on

    # ----------------------------------------------------------------------------
    async def async_charger_switch_on(self) -> None:
        """Switch on charger."""
        await self.async_option_turn_entity_switch_on(OPTION_CHARGER_ON_OFF_SWITCH)

    # ----------------------------------------------------------------------------
    async def async_charger_switch_off(self) -> None:
        """Switch off charger."""
        await self.async_option_turn_entity_switch_off(OPTION_CHARGER_ON_OFF_SWITCH)

    # ----------------------------------------------------------------------------
    def is_charging(self) -> bool:
        """Is device charging?"""
        is_charging = False

        state = self.option_get_entity_string(OPTION_CHARGER_CHARGING_SENSOR)
        state_list = self.option_get_list(OPTION_CHARGER_CHARGING_STATE_LIST)
        if state is not None and state_list is not None:
            is_charging = state in state_list

        return is_charging

    # ----------------------------------------------------------------------------
    # def get_charge_current(self) -> float | None:
    #     """Get charger charge current in AMPS."""
    #     return self.option_get_number(OPTION_CHARGER_GET_CHARGE_CURRENT)

    # ----------------------------------------------------------------------------
    def get_charge_current(self) -> float | None:
        """Get the current limit of the charger in amps."""
        # Try to get the current offered first, then fall back to current import
        state = self._get_entity_state_by_key(OcppEntityMap.MaximumCurrent)

        if state is None:
            _LOGGER.warning(
                "Current limit not available for OCPP charger %s. "
                "Make sure the required entity (%s) is enabled and available",
                self.device_entry.id,
                OcppEntityMap.MaximumCurrent,
            )
            return None

        try:
            return float(state)
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Failed to parse current limit value '%s' for OCPP charger %s: %s",
                state,
                self.device_entry.id,
                e,
            )
            return None

    # ----------------------------------------------------------------------------
    async def async_set_charge_current(self, charge_current: float) -> None:
        """Set charger charge current."""
        min_current = charge_current

        try:
            await self.hass.services.async_call(
                domain=CHARGER_DOMAIN_OCPP,
                service="set_charge_rate",
                service_data={
                    "device_id": self.device_entry.id,
                    "limit_amps": min_current,
                },
                blocking=True,
            )
        except (ValueError, RuntimeError, TimeoutError) as e:
            _LOGGER.warning(
                "Failed to set current limit for OCPP charger %s: %s",
                self.device_entry.id,
                e,
            )

    # ----------------------------------------------------------------------------
    def _get_status(self) -> Any | None:
        """Get the current status of the OCPP charger."""
        # Try connector status first, then general status
        status: Any | None = None

        try:
            status = self._get_entity_state_by_key(
                OcppEntityMap.StatusConnector,
            )
        except ValueError as e:
            _LOGGER.debug(
                "Failed to get status for OCPP charger by entity '%s': '%s'",
                OcppEntityMap.StatusConnector,
                e,
            )

        if status is None:
            status = self._get_entity_state_by_key(
                OcppEntityMap.Status,
            )

        return status

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the OCPP charger."""
