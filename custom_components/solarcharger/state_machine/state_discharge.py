# ruff: noqa: TRY401, TID252
"""State machine state."""

from datetime import timedelta
import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import RunState, RunStep
from ..models.model_charge_stats import ChargeStats
from ..models.model_context_data import ContextData
from . import state_charge
from .solar_charge_state import SolarChargeState

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateDischarge(SolarChargeState):
    """Discharge state: Do not turn off charger. Wait for external trigger."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state = RunState.DISCHARGE

    # ----------------------------------------------------------------------------
    def _update_pause_stats(
        self, stats: ChargeStats, paused_duration: timedelta
    ) -> None:
        """Update pause/discharge stats."""

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
    async def _async_discharge(
        self,
        charger: Charger,
        chargeable: Chargeable,
        state: RunState,
        stats: ChargeStats,
    ) -> ContextData:
        """Pause charge and wait for external trigger to continue. Let device sleep."""

        start_time = self.solarcharge.get_local_datetime()
        self.solarcharge.give_up_real_power_allocation()

        # Initialise counts before starting loop
        stats.loop_success_count = 0
        stats.loop_consecutive_fail_count = 0
        done_set_zero_current = False
        while True:
            self.solarcharge.abort_if_exceed_max_consecutive_failure()

            try:
                # Set 0A charge current if looping for the first time.
                if not done_set_zero_current:
                    await self.solarcharge.async_set_charge_current(charger, 0)
                    done_set_zero_current = True

                # Update status periodically, and just before checking status.
                # Do not wait here. Depends on the main loop to wait.
                await self.solarcharge.async_update_ha(
                    chargeable, wait_after_update=False
                )

                context = await self.solarcharge.async_set_charge_status(
                    charger, chargeable, state, stats
                )
                if context.next_step != RunStep.DISCHARGE:
                    break

                # Show running pause duration.
                self.solarcharge.set_last_pause_duration(
                    self.solarcharge.get_local_datetime() - start_time
                )

                # Completed loop successfully at this point.
                stats.loop_success_count += 1
                stats.loop_consecutive_fail_count = 0

            except Exception as e:
                stats.loop_consecutive_fail_count += 1
                _LOGGER.exception(
                    "%s: Failed to discharge: %s", self.solarcharge.caller, e
                )

            await self.solarcharge.async_charger_sleep()
            stats.loop_total_count += 1

        end_time = self.solarcharge.get_local_datetime()
        paused_duration = end_time - start_time

        # Think about only update stats when pause exit was due to having enough power.
        # if next_step == ChargeStatus.CHARGE_CONTINUE:
        self._update_pause_stats(stats, paused_duration)

        return context

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start discharge state."""

        self.solarcharge.set_run_state(self.state)

        context = await self._async_discharge(
            self.solarcharge.charger,
            self.solarcharge.chargeable,
            self.solarcharge.machine_state.state,
            self.solarcharge.stats,
        )

        self.solarcharge.log_context(context)

        self.solarcharge.set_machine_state(state_charge.StateCharge())
