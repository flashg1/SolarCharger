# ruff: noqa: TRY401, TID252
"""State machine state."""

import asyncio
from datetime import timedelta
import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import SENSOR_SHARE_ALLOCATION, ChargeStatus, RunState
from ..model_charge_stats import ChargeStats
from ..model_context_data import ContextData

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
        self.state = RunState.PAUSED

    # ----------------------------------------------------------------------------
    def _update_pause_stats(
        self, stats: ChargeStats, paused_duration: timedelta
    ) -> None:
        """Update pause stats."""

        stats.pause_last_duration = paused_duration
        stats.pause_total_duration += paused_duration
        stats.pause_total_count += 1
        stats.pause_average_duration = timedelta(
            seconds=(
                stats.pause_total_duration.total_seconds() / stats.pause_total_count
            )
        )

        self.solarcharge.set_pause_stats(stats)

    # ----------------------------------------------------------------------------
    async def _async_pause_charge(
        self,
        charger: Charger,
        chargeable: Chargeable,
        state: RunState,
        stats: ChargeStats,
    ) -> ContextData:
        """Pause charge and wait for external trigger to continue. Let device sleep."""

        start_time = self.solarcharge.get_local_datetime()

        assert self.solarcharge.entities.sensors is not None
        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(0)

        # Reset buffer for moving average
        self.solarcharge.power_allocations = []

        # Initialise counts before starting loop
        stats.loop_success_count = 0
        stats.loop_consecutive_fail_count = 0
        done_switch_off_charger = False
        while True:
            self.solarcharge.abort_if_exceed_max_consecutive_failure()

            try:
                # Turn off charger if looping for the first time.
                if not done_switch_off_charger:
                    await self.solarcharge.async_turn_off_charger(charger, chargeable)
                    done_switch_off_charger = True

                context = await self.solarcharge.async_set_charge_status(
                    charger, chargeable, state, stats
                )
                if context.next_step != ChargeStatus.CHARGE_PAUSE:
                    break

                # Completed loop successfully at this point.
                stats.loop_success_count += 1
                stats.loop_consecutive_fail_count = 0

            except Exception as e:
                stats.loop_consecutive_fail_count += 1
                _LOGGER.exception(
                    "%s: Failed to pause charge: %s", self.solarcharge.caller, e
                )

            await asyncio.sleep(self.solarcharge.wait_net_power_update)
            stats.loop_total_count += 1

        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(1)

        end_time = self.solarcharge.get_local_datetime()
        paused_duration = end_time - start_time

        # Think about only update stats when pause exit was due to having enough power.
        # if next_step == ChargeStatus.CHARGE_CONTINUE:
        self._update_pause_stats(stats, paused_duration)

        return context

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start pause state."""

        self.solarcharge.set_run_state(self.state)

        context = await self._async_pause_charge(
            self.solarcharge.charger,
            self.solarcharge.chargeable,
            self.solarcharge.machine_state.state,
            self.solarcharge.stats,
        )

        self.solarcharge.log_context(context)

        # WL: This also worked.
        # Local Imports (Lazy Loading): Move from state_a import StateA inside
        # the handle method of StateB. This delays the import until the method runs.
        # from .state_initialise import StateInitialise
        # self.solarcharge.set_state(StateInitialise())

        # Import Modules, Not Classes
        self.solarcharge.set_machine_state(state_initialise.StateInitialise())
