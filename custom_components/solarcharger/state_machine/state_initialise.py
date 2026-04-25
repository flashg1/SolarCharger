# ruff: noqa: TID252
"""State machine state."""

import logging

from ..chargers.chargeable import Chargeable
from ..const import RunState
from .solar_charge_state import SolarChargeState
from .state_charge import StateCharge

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateInitialise(SolarChargeState):
    """Initialising state: wake up device, etc."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state = RunState.INITIALISING

    # ----------------------------------------------------------------------------
    def _check_if_at_location_or_abort(self, chargeable: Chargeable) -> None:
        is_at_location = self.solarcharge.is_at_location(chargeable)
        if not is_at_location:
            raise RuntimeError("Device not at charger location")

    # ----------------------------------------------------------------------------
    async def _async_init_device(self, chargeable: Chargeable) -> None:
        """Init charge device."""

        await self.solarcharge.async_wake_up_and_update_ha(chargeable)
        self._check_if_at_location_or_abort(chargeable)

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start initialising state."""

        self.solarcharge.set_run_state(self.state)

        await self._async_init_device(self.solarcharge.chargeable)

        self.solarcharge.set_machine_state(StateCharge())
