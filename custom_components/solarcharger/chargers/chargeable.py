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
        """Check if given device is of class' type chargeable."""

    @abstractmethod
    async def async_setup_chargeable(self) -> None:
        """Set up chargeable device."""

    @abstractmethod
    async def async_wake_up_chargee(self) -> None:
        """Wake up chargeable device."""

    @abstractmethod
    async def async_get_chargee_update(self) -> None:
        """Force chargeable device to update data in HA."""

    @abstractmethod
    def get_state_of_charge(self) -> int | None:
        """Get the state of charge of the chargeable device."""

    @abstractmethod
    def get_charge_limit(self) -> int | None:
        """Get chargeable device charge limit."""

    @abstractmethod
    async def async_set_charge_limit(self, charge_limit: int) -> None:
        """Set chargeable device charge limit."""
