# ruff: noqa: TID252
"""State machine state."""

import logging

from ..const import SENSOR_DELTA_ALLOCATED_POWER, RunState
from .solar_charge_state import SolarChargeState

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateEnd(SolarChargeState):
    """End state: Exit task."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state = RunState.ENDED

    # ----------------------------------------------------------------------------
    async def _async_end_session(self) -> None:
        """End charge session."""

        # Delta allocated power is set in the coordinator timer thread.
        # Should not be set here, but no choice.
        # Reset here in case it is missed in the coordinator due to race condition.
        self.solarcharge.entities.sensors[SENSOR_DELTA_ALLOCATED_POWER].set_state(0)

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start end state."""

        self.solarcharge.set_run_state(self.state)
        self._async_end_session()
