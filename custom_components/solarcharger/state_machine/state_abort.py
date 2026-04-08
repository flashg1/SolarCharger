# ruff: noqa: TID252
"""State machine state."""

import logging

from ..const import RunState
from .solar_charge_state import SolarChargeState

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateAbort(SolarChargeState):
    """Abort state: Abort charge."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state = RunState.STATE_ABORTING

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start abort state."""

        self.solarcharge.set_run_state(self.state)
