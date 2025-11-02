"""Base Chargeable Class."""

from abc import ABC, abstractmethod

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class Chargeable(ABC):
    """Base class for all chargeable devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        config_subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the chargeable device instance."""
        self.hass = hass
        self.config_entry = config_entry
        self.config_subentry = config_subentry
        self.device = device

    # ----------------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def is_chargeable_device(device: DeviceEntry) -> bool:
        """Check if given device is of class type chargeable."""

    @abstractmethod
    def get_chargeable_name(self) -> str:
        """Get chargeable name."""

    # @abstractmethod
    async def async_setup_chargeable(self) -> None:
        """Set up chargeable device."""
        return

    # @abstractmethod
    async def async_wake_up(self) -> None:
        """Wake up chargeable device."""
        return

    # @abstractmethod
    async def async_update_ha(self) -> None:
        """Force chargeable device to update data in HA."""
        return

    # @abstractmethod
    def is_at_location(self) -> bool:
        """Is chargeable device at charger location?"""
        return True

    # @abstractmethod
    def get_state_of_charge(self) -> int | None:
        """Get state of charge (SoC) of chargeable device."""
        return 0

    # @abstractmethod
    def get_charge_limit(self) -> int | None:
        """Get chargeable device charge limit."""
        return 100

    # @abstractmethod
    async def async_set_charge_limit(self, charge_limit: int) -> None:
        """Set chargeable device charge limit."""
        return
