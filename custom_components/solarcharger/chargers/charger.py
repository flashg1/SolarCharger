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
        """Check if device is of class type charger."""

    @abstractmethod
    async def async_setup(self) -> None:
        """Set up charger."""

    @abstractmethod
    def get_max_charge_current(self) -> float | None:
        """Get charger max allowable current in amps."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Is charger connected to chargeable device?

        This does not mean that the car is actually able to charge, for which
        you can use can_charge().

        When the connected car is not authorised (and therefore the charger is not
        ready) we consider it a "disconnected" state.
        """

    @abstractmethod
    async def async_charger_switch_on(self) -> None:
        """Switch on charger."""

    @abstractmethod
    async def async_charger_switch_off(self) -> None:
        """Switch off charger."""

    @abstractmethod
    def is_charging(self) -> bool:
        """Is device charging?"""

    @abstractmethod
    def get_charge_current(self) -> float | None:
        """Get charger charge current in AMPS."""

    @abstractmethod
    async def async_set_charge_current(self, charge_current: float) -> None:
        """Set charger charge current in AMPS."""

    @abstractmethod
    async def async_unload(self) -> None:
        """Unload the charger instance."""
