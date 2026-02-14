"""Base Charger Class."""

from abc import ABC, abstractmethod

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from ..model_config import ConfigValueDict  # noqa: TID252


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class Charger(ABC):
    """Base class for all chargers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        device: DeviceEntry,
    ) -> None:
        """Initialize the Charger instance."""

        self._hass = hass
        self._entry = entry
        self._subentry = subentry
        self._device = device

    # ----------------------------------------------------------------------------
    @property
    def id(self) -> str:
        """Return the unique ID of the charger."""
        # return self.config_entry.entry_id
        return self._subentry.subentry_id

    # ----------------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if device is of class type charger."""

    @abstractmethod
    def get_charger_name(self) -> str:
        """Get charger name."""

    @abstractmethod
    async def async_setup(self) -> None:
        """Set up charger."""

    @abstractmethod
    def get_max_charge_current(
        self, val_dict: ConfigValueDict | None = None
    ) -> float | None:
        """Get charger max allowable current in amps."""

    @abstractmethod
    def is_connected(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is charger connected to chargeable device?

        This does not mean that the car is actually able to charge, for which
        you can use can_charge().

        When the connected car is not authorised (and therefore the charger is not
        ready) we consider it a "disconnected" state.
        """

    @abstractmethod
    def is_charger_switch_on(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is charger switched on?"""

    @abstractmethod
    async def async_turn_charger_switch(
        self, turn_on: bool, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Switch on or off charger."""

    @abstractmethod
    def is_charging(self, val_dict: ConfigValueDict | None = None) -> bool:
        """Is device charging?"""

    @abstractmethod
    def get_charge_current(
        self, val_dict: ConfigValueDict | None = None
    ) -> float | None:
        """Get charger charge current in AMPS."""

    @abstractmethod
    async def async_set_charge_current(
        self, charge_current: float, val_dict: ConfigValueDict | None = None
    ) -> None:
        """Set charger charge current in AMPS."""

    @abstractmethod
    async def async_unload(self) -> None:
        """Unload the charger instance."""
