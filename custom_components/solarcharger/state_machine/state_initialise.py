# ruff: noqa: TID252
"""State machine state."""

from datetime import timedelta
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
        self.state = RunState.STATE_INITIALISING

    # ----------------------------------------------------------------------------
    def _check_if_at_location_or_abort(self, chargeable: Chargeable) -> None:
        is_at_location = self.solarcharge.is_at_location(chargeable)
        if not is_at_location:
            raise RuntimeError("Device not at charger location")

    # ----------------------------------------------------------------------------
    # Estimation only.
    # Run this first thing before starting session.
    def _is_session_triggered_by_timer(self) -> bool:
        """Trigger by timer?"""
        triggered_by_timer = False
        time_diff = timedelta(seconds=0)

        charge_start_time = self.solarcharge.get_local_datetime()
        next_charge_time = self.solarcharge.get_datetime(
            self.solarcharge.next_charge_time_trigger_entity_id
        )
        if next_charge_time is not None:
            if charge_start_time > next_charge_time:
                time_diff = charge_start_time - next_charge_time
            else:
                time_diff = next_charge_time - charge_start_time
            if time_diff < timedelta(seconds=30):
                triggered_by_timer = True

        _LOGGER.warning(
            "%s: charge_start_time=%s, next_charge_time=%s, time_diff=%s, triggered_by_timer=%s",
            self.solarcharge.caller,
            charge_start_time,
            next_charge_time,
            time_diff,
            triggered_by_timer,
        )

        return triggered_by_timer

    # ----------------------------------------------------------------------------
    async def _async_init_device(self, chargeable: Chargeable) -> None:
        """Init charge device."""

        #####################################
        # Set up instance variables
        #####################################
        # Must run this first thing to estimate if session started by timer
        self.solarcharge.session_triggered_by_timer = (
            self._is_session_triggered_by_timer()
        )
        self.solarcharge.started_calibrate_max_charge_speed = False

        await self.solarcharge.async_wake_up_and_update_ha(chargeable)
        self._check_if_at_location_or_abort(chargeable)

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start initialising state."""

        self.solarcharge.set_run_state(self.state)
        await self._async_init_device(self.solarcharge.chargeable)
        self.solarcharge.set_machine_state(StateCharge())
