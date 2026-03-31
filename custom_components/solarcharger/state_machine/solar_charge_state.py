"""State machine interface."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .solar_charge import SolarCharge


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargeState(ABC):
    """The common state interface for all the states."""

    # ----------------------------------------------------------------------------
    @property
    def solarcharge(self) -> "SolarCharge":
        """Get the state machine context."""
        return self._context

    @solarcharge.setter
    def solarcharge(self, context: "SolarCharge") -> None:
        """Set the state machine context."""
        self._context = context

    # ----------------------------------------------------------------------------
    @abstractmethod
    async def async_activate_state(self) -> None:
        """Start state action."""
