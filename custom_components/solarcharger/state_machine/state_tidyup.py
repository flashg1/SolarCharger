# ruff: noqa: TID252
"""State machine state."""

import logging

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import RunState
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
        self.state_name = RunState.STATE_ENDING.value

    # ----------------------------------------------------------------------------
    def _unsubscribe_allocated_power_update(self) -> None:
        """Unsubscribe allocated power update."""

        self.solarcharge.tracker.untrack_allocated_power_update()

    # ----------------------------------------------------------------------------
    async def async_tidy_up_on_exit(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Tidy up on exit."""

        try:
            self._unsubscribe_allocated_power_update()
            await self.solarcharge.async_turn_off_calibrate_max_charge_speed_switch()

            await self.solarcharge.async_update_ha(chargeable)

            switched_on = charger.is_charger_switch_on()
            if switched_on:
                await self.solarcharge.async_set_charge_current(charger, 0)
                await self.solarcharge.async_turn_charger_switch(charger, turn_on=False)

            # Only schedule next charge session if car is connected and at location.
            if self.solarcharge.is_connected(
                charger
            ) and self.solarcharge.is_at_location(chargeable):
                await self.solarcharge.scheduler.async_schedule_next_charge_session(
                    chargeable, self.solarcharge.started_calibrate_max_charge_speed
                )

        except Exception as e:
            _LOGGER.error(
                "%s: Failed to tidy up charge task on exit: %s",
                self.solarcharge.caller,
                e,
            )

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start tidy up state."""

        self.solarcharge.set_run_state(self.state_name)
        await self.async_tidy_up_on_exit(
            self.solarcharge.charger, self.solarcharge.chargeable
        )
        self.solarcharge.set_state(StateEnd())
