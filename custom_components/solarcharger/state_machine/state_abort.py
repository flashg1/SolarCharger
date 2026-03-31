# ruff: noqa: TID252
"""State machine state."""

import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from .solar_charge_state import SolarChargeState

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateAbort(SolarChargeState):
    """Abort state: Abort charge."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start abort state."""
