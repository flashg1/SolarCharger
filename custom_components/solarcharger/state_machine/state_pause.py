# ruff: noqa: TRY401, TID252
"""State machine state."""

import asyncio
import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import SENSOR_SHARE_ALLOCATION, RunState

# Import Modules, Not Classes: Instead of from machine import StateA, use
# import machine and refer to machine.StateA. This breaks the cycle because
# Python only needs to locate the module, not resolve its contents immediately.
from . import state_initialise
from .solar_charge_state import SolarChargeState

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StatePause(SolarChargeState):
    """Pause state: Turn off charger and wait for external trigger."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state_name = RunState.STATE_PAUSED.value

    # ----------------------------------------------------------------------------
    async def _async_pause_charge(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Pause charge and wait for external trigger to continue. Let device sleep."""

        assert self.solarcharge.entities.sensors is not None
        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(0)

        try:
            await self.solarcharge.async_set_charge_current(charger, 0)
            await self.solarcharge.async_turn_charger_switch(charger, turn_on=False)
            await self.solarcharge.async_update_ha(chargeable)

            self.solarcharge.power_allocations = []

            while True:
                is_enough_power = self.solarcharge.is_average_allocated_power_more_than_min_workable_power(
                    self.solarcharge.max_allocation_count,
                    self.solarcharge.power_allocations,
                )

                if (
                    (is_enough_power is not None and is_enough_power)
                    or self.solarcharge.is_calibrate_max_charge_speed()
                    or self.solarcharge.is_fast_charge_mode()
                    # Can't do this for now since running goal is not running!
                    # or self.solarcharge.running_goal.has_charge_endtime
                    or self.solarcharge.max_allocation_count == 0
                ):
                    break

                await asyncio.sleep(self.solarcharge.wait_net_power_update)

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to pause charge: %s", self.solarcharge.caller, e
            )

        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(1)

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start pause state."""

        self.solarcharge.set_run_state(self.state_name)
        await self._async_pause_charge(
            self.solarcharge.charger, self.solarcharge.chargeable
        )

        # WL: This also worked.
        # Local Imports (Lazy Loading): Move from state_a import StateA inside
        # the handle method of StateB. This delays the import until the method runs.
        # from .state_initialise import StateInitialise
        # self.solarcharge.set_state(StateInitialise())

        # Import Modules, Not Classes
        self.solarcharge.set_state(state_initialise.StateInitialise())
