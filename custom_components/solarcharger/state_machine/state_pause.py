# ruff: noqa: TID252
"""State machine state."""

import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from .solar_charge_state import SolarChargeState
from .state_charge import StateCharge

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StatePause(SolarChargeState):
    """Pause state: Turn off charger and wait for external trigger."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start pause state."""
        self.solarcharge.set_state(StateCharge())
