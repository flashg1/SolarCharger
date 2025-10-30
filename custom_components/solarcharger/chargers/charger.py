"""Base Charger Class."""

from abc import ABC, abstractmethod
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class Charger(ABC):
    """Base class for all chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        config_subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the Charger instance."""
        self.hass = hass
        self.config_entry = config_entry
        self.config_subentry = config_subentry
        self.device = device

    # ----------------------------------------------------------------------------
    @property
    def id(self) -> str:
        """Return the unique ID of the charger."""
        # return self.config_entry.entry_id
        return self.config_subentry.subentry_id

    # ----------------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if given device is of class' type charger."""

    @abstractmethod
    async def async_setup(self) -> None:
        """Set up charger."""

    @abstractmethod
    async def set_charge_current(self, charge_current: float) -> None:
        """Set the charger limit in amps."""

    @abstractmethod
    def get_charge_current(self) -> float | None:
        """Get charge current in AMPS."""

    @abstractmethod
    def get_max_charge_current(self) -> float | None:
        """Get the configured maximum current limit of the charger in amps."""

    @abstractmethod
    def car_connected(self) -> bool:
        """Return whether the car is connected to the charger and ready to receive charge.

        This does not mean that the car is actually able to charge, for which
        you can use can_charge().

        When the connected car is not authorised (and therefore the charger is not
        ready) we consider it a "disconnected" state.
        """

    @abstractmethod
    def can_charge(self) -> bool:
        """Return whether the car is connected and charging or accepting charge."""

    async def async_start_charger(self) -> None:
        """Start charger."""

    async def async_stop_charger(self) -> None:
        """Stop charger."""

    @abstractmethod
    async def async_unload(self) -> None:
        """Unload the charger instance."""
