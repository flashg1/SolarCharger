# ruff: noqa: TID252
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

    @property
    def state_name(self) -> str:
        """Get the state name."""
        return self._state_name

    @state_name.setter
    def state_name(self, name: str) -> None:
        """Set the state name."""
        self._state_name = name

    # ----------------------------------------------------------------------------
    @abstractmethod
    async def async_activate_state(self) -> None:
        """Start state action."""
