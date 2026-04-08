# ruff: noqa: TID252
"""State machine interface."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..const import RunState

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
    def state(self) -> RunState:
        """Get the run state."""
        return self._state

    @state.setter
    def state(self, state: RunState) -> None:
        """Set the run state."""
        self._state = state

    # ----------------------------------------------------------------------------
    @abstractmethod
    async def async_activate_state(self) -> None:
        """Start state action."""
