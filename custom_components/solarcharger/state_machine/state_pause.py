# ruff: noqa: TRY401, TID252
"""State machine state."""

import asyncio
from datetime import timedelta
import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import SENSOR_SHARE_ALLOCATION, RunState
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
        self.state_name = RunState.STATE_PAUSED.value

    # ----------------------------------------------------------------------------
    def _update_pause_stats(
        self, stats: ChargeStats, paused_duration: timedelta
    ) -> None:
        """Update pause stats."""

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
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Pause charge and wait for external trigger to continue. Let device sleep."""

        start_time = self.solarcharge.get_local_datetime()

        is_enough_power = None
        average_allocated_power = 0
        data_points = 0

        assert self.solarcharge.entities.sensors is not None
        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(0)

        try:
            await self.solarcharge.async_set_charge_current(charger, 0)
            await self.solarcharge.async_turn_charger_switch(charger, turn_on=False)
            await self.solarcharge.async_update_ha(chargeable)

            self.solarcharge.power_allocations = []

            while True:
                is_sun_trigger = self.solarcharge.is_sun_trigger()
                (is_sun_above_start_end_elevations, _) = (
                    self.solarcharge.is_sun_above_start_end_elevation_triggers()
                )

                is_enough_power, average_allocated_power, data_points = (
                    self.solarcharge.is_average_allocated_power_more_than_min_workable_power(
                        self.solarcharge.max_allocation_count,
                        self.solarcharge.power_allocations,
                        raise_the_bar=True,
                    )
                )

                if (
                    (is_sun_trigger and not is_sun_above_start_end_elevations)
                    or (is_enough_power is not None and is_enough_power)
                    or not self.solarcharge.is_monitor_available_power()
                ):
                    break

                await asyncio.sleep(self.solarcharge.wait_net_power_update)

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to pause charge: %s", self.solarcharge.caller, e
            )

        self.solarcharge.entities.sensors[SENSOR_SHARE_ALLOCATION].set_state(1)

        end_time = self.solarcharge.get_local_datetime()
        paused_duration = end_time - start_time

        # Only update stats when exit pause state is due to having enough power.
        if is_enough_power is not None and is_enough_power:
            self._update_pause_stats(self.solarcharge.stats, paused_duration)

        _LOGGER.warning(
            "%s: paused_duration=%s (is_enough_power=%s, average_allocated_power=%s, data_points=%s)",
            self.solarcharge.caller,
            paused_duration,
            is_enough_power,
            average_allocated_power,
            data_points,
        )

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
        self.solarcharge.set_machine_state(state_initialise.StateInitialise())
