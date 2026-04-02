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
class StateEnd(SolarChargeState):
    """End state: Exit task."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state_name = RunState.STATE_ENDED.value

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start end state."""

        self.solarcharge.set_run_state(self.state_name)
