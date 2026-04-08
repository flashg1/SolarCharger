# ruff: noqa: TRY401, TID252
"""State machine state."""

import asyncio
from datetime import timedelta
import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import SENSOR_SHARE_ALLOCATION, ChargeStatus, RunState
from ..model_charge_stats import ChargeStats

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
        self.state = RunState.STATE_PAUSED

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
    async def _turn_off_charger(self, charger: Charger, chargeable: Chargeable) -> None:
        """Turn off charger."""

        try:
            await self.solarcharge.async_set_charge_current(charger, 0)
            await self.solarcharge.async_turn_charger_switch(charger, turn_on=False)
            await self.solarcharge.async_update_ha(chargeable)

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to pause charge: %s", self.solarcharge.caller, e
            )

    # ----------------------------------------------------------------------------
    async def _async_pause_charge(
        self,
        charger: Charger,
        chargeable: Chargeable,
        state: RunState,
        stats: ChargeStats,
    ) -> None:
        """Pause charge and wait for external trigger to continue. Let device sleep."""

        start_time = self.solarcharge.get_local_datetime()

        assert self.solarcharge.entities.sensors is not None
        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(0)

        await self._turn_off_charger(charger, chargeable)

        self.solarcharge.power_allocations = []

        # Initialise counts before starting loop
        stats.loop_success_count = 0
        stats.loop_consecutive_fail_count = 0
        while True:
            try:
                self.solarcharge.abort_if_exceed_max_consecutive_failure()

                next_step = await self.solarcharge.async_get_charge_status(
                    charger, chargeable, state
                )
                if next_step != ChargeStatus.CHARGE_PAUSE:
                    break

                stats.loop_success_count += 1
                stats.loop_consecutive_fail_count = 0

                await asyncio.sleep(self.solarcharge.wait_net_power_update)

            except Exception as e:
                stats.loop_consecutive_fail_count += 1
                _LOGGER.exception(
                    "%s: Failed to pause charge: %s", self.solarcharge.caller, e
                )

            stats.loop_total_count += 1

        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(1)

        end_time = self.solarcharge.get_local_datetime()
        paused_duration = end_time - start_time

        # Only update stats when exiting pause state is due to having enough power.
        if next_step == ChargeStatus.CHARGE_CONTINUE:
            self._update_pause_stats(self.solarcharge.stats, paused_duration)

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start pause state."""

        self.solarcharge.set_run_state(self.state)
        await self._async_pause_charge(
            self.solarcharge.charger,
            self.solarcharge.chargeable,
            self.solarcharge.machine_state.state,
            self.solarcharge.stats,
        )

        # WL: This also worked.
        # Local Imports (Lazy Loading): Move from state_a import StateA inside
        # the handle method of StateB. This delays the import until the method runs.
        # from .state_initialise import StateInitialise
        # self.solarcharge.set_state(StateInitialise())

        # Import Modules, Not Classes
        self.solarcharge.set_machine_state(state_initialise.StateInitialise())
