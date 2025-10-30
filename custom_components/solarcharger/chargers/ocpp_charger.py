"""OCPP Charger implementation."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..const import CHARGER_DOMAIN_OCPP  # noqa: TID252
from ..ha_device import HaDevice  # noqa: TID252
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
class OcppCharger(HaDevice, Charger):
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
        Charger.__init__(self, hass, config_entry, config_subentry, device_entry)
        self.refresh_entities()

    # ----------------------------------------------------------------------------
    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if the given device is an OCPP charger."""
        return any(
            id_domain == CHARGER_DOMAIN_OCPP for id_domain, _ in device.identifiers
        )

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Set up the charger."""

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
    def get_max_charge_current(self) -> float | None:
        """Get the configured maximum current limit of the charger in amps."""
        # TODO: Get max current from OCPP
        _LOGGER.info(
            "No maximum current limit information available for OCPP charger %s, "
            "using default 15A",
            self.device_entry.id,
        )
        return 15.0

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
    def is_connected(self) -> bool:
        """Car is connected to the charger and ready to receive charge."""
        status = self._get_status()

        # Consider the car connected if the charger is in any of these states
        connected_statuses = [
            OcppStatusMap.Preparing,
            OcppStatusMap.Charging,
            OcppStatusMap.SuspendedEVSE,
            OcppStatusMap.SuspendedEV,
            OcppStatusMap.Finishing,
        ]

        return status in connected_statuses

    # ----------------------------------------------------------------------------
    def is_charging(self) -> bool:
        """Return whether the car is connected and charging or accepting charge."""
        status = self._get_status()

        charging_statuses = [
            OcppStatusMap.Preparing,
            OcppStatusMap.Charging,
            OcppStatusMap.SuspendedEV,
        ]

        return status in charging_statuses

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the OCPP charger."""
