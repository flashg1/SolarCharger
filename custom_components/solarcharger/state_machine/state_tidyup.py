# ruff: noqa: TRY401, TID252
"""State machine state."""

import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import (
    SENSOR_MEDIAN_NET_ALLOCATED_POWER,
    SENSOR_NET_ALLOCATED_POWER,
    SENSOR_SMA_NET_ALLOCATED_POWER,
    RunState,
)
from .solar_charge_state import SolarChargeState
from .state_end import StateEnd

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateTidyUp(SolarChargeState):
    """Tidy up state: Turn off charger."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state = RunState.ENDING

    # ----------------------------------------------------------------------------
    def _unsubscribe_updates(self) -> None:
        """Unsubscribe updates."""

        # Unsubscribe delta allocated power
        self.solarcharge.give_up_real_power_allocation()
        self.solarcharge.tracker.untrack_delta_allocated_power_update()
        # Unsubscribe sync charge current
        self.solarcharge.tracker.untrack_sync_update()

        # reset sensors
        self.solarcharge.entities.sensors[SENSOR_NET_ALLOCATED_POWER].set_state(0)
        self.solarcharge.entities.sensors[SENSOR_MEDIAN_NET_ALLOCATED_POWER].set_state(
            0
        )
        self.solarcharge.entities.sensors[SENSOR_SMA_NET_ALLOCATED_POWER].set_state(0)

    # ----------------------------------------------------------------------------
    async def async_tidy_up_on_exit(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Tidy up on exit."""

        try:
            self.solarcharge.started_max_charge = 0
            self._unsubscribe_updates()
            await self.solarcharge.async_turn_off_calibrate_max_charge_speed_switch()

            # async_update_ha() most likely not required here
            # await self.solarcharge.async_update_ha(chargeable)
            await self.solarcharge.async_turn_off_charger(charger, chargeable)

            # Only schedule next charge session if car is connected and at location.
            if self.solarcharge.is_connected(
                charger
            ) and self.solarcharge.is_at_location(chargeable):
                await self.solarcharge.scheduler.async_schedule_next_charge_session(
                    chargeable, self.solarcharge.started_calibrate_max_charge_speed
                )

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to tidy up charge task on exit: %s",
                self.solarcharge.caller,
                e,
            )

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start tidy up state."""

        self.solarcharge.set_run_state(self.state)

        await self.async_tidy_up_on_exit(
            self.solarcharge.charger, self.solarcharge.chargeable
        )

        self.solarcharge.set_machine_state(StateEnd())
