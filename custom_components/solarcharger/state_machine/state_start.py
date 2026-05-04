# ruff: noqa: TID252
"""State machine state."""

from datetime import timedelta
import logging

from homeassistant.core import Event, EventStateChangedData

from ..const import NUMBER_POWER_MONITOR_DURATION, SENSOR_CONSUMED_POWER, RunState
from ..models.model_charge_stats import ChargeStats
from .solar_charge_state import SolarChargeState
from .state_initialise import StateInitialise

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateStart(SolarChargeState):
    """Starting state: Set up session variables."""

    def __init__(
        self,
    ) -> None:
        """Start machine state."""
        self.state = RunState.STARTING

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
    def _set_max_allocation_count(self, wait_net_power_update: float) -> None:
        """Initialize max allocation count."""

        monitor_duration = self.solarcharge.option_get_entity_number_or_abort(
            NUMBER_POWER_MONITOR_DURATION
        )
        monitor_duration_seconds = monitor_duration * 60

        # Set to 0 to disable power monitoring by default.
        self.solarcharge.max_allocation_count = 0

        if monitor_duration > 0:
            if monitor_duration_seconds > (2 * wait_net_power_update):
                self.solarcharge.max_allocation_count = round(
                    monitor_duration_seconds / wait_net_power_update
                )
            else:
                _LOGGER.error(
                    "%s: Power monitor duration (%s minutes) must be more than 2 times longer than net power update interval (%s seconds)",
                    self.solarcharge.caller,
                    monitor_duration,
                    wait_net_power_update,
                )

    # ----------------------------------------------------------------------------
    def _init_power_monitor_window(self, seconds_between_update: int) -> None:

        self._set_max_allocation_count(seconds_between_update)
        self.solarcharge.power_allocations = []

    # ----------------------------------------------------------------------------
    def _init_instance_variables(self) -> None:
        """Set up instance variables once per session."""

        # Must run this first thing to estimate if session started by timer
        self.solarcharge.session_triggered_by_timer = (
            self._is_session_triggered_by_timer()
        )
        self.solarcharge.started_max_charge = 0
        self.solarcharge.started_calibrate_max_charge_speed = False

        # Init power monitor duration
        self.solarcharge.wait_net_power_update = (
            self.solarcharge.get_wait_net_power_update()
        )
        self._init_power_monitor_window(self.solarcharge.wait_net_power_update)

    # ----------------------------------------------------------------------------
    # 2025-11-02 09:01:48.009 INFO (MainThread) [custom_components.solarcharger.chargers.controller] tesla_custom_tesla23m3:
    # entity_id=number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power,
    #
    # old_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-500.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:00:32.962356+11:00>,
    #
    # new_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-200.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:01:48.008211+11:00>
    async def _async_handle_allocated_power_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        entity_id = data["entity_id"]
        old_state = data["old_state"]
        new_state = data["new_state"]

        if new_state is not None:
            duration_since_last_change = (
                new_state.last_changed_timestamp
                - self.solarcharge.charge_current_updatetime
            )

            if old_state is not None:
                _LOGGER.debug(
                    "%s: entity_id=%s, old_state=%s, new_state=%s, duration_since_last_change=%s",
                    self.solarcharge.caller,
                    entity_id,
                    old_state.state,
                    new_state.state,
                    duration_since_last_change,
                )
            else:
                _LOGGER.debug(
                    "%s: entity_id=%s, new_state=%s, duration_since_last_change=%s",
                    self.solarcharge.caller,
                    entity_id,
                    new_state.state,
                    duration_since_last_change,
                )

            # # Make sure we don't change the charge current too often
            # if duration_since_last_change >= MIN_TIME_BETWEEN_UPDATE:
            try:
                allocated_power = float(new_state.state)

                # Save allocated power to calculate moving average.
                if self.solarcharge.max_allocation_count > 0:
                    # TODO: No running goal on start need is_monitor_available_power()
                    if not self.solarcharge.is_monitor_available_power():
                        self.solarcharge.power_allocations = []
                    elif (
                        len(self.solarcharge.power_allocations)
                        >= self.solarcharge.max_allocation_count
                    ):
                        self.solarcharge.power_allocations.pop(0)

                    assert self.solarcharge.entities.sensors is not None
                    consumed_power = float(
                        self.solarcharge.entities.sensors[SENSOR_CONSUMED_POWER].state
                    )
                    self.solarcharge.power_allocations.append(
                        allocated_power - consumed_power
                    )

                # This callback is still running in paused state.
                # Only adjust charge current if we are still in charging state
                # if self.solarcharge.machine_state.state == RunState.CHARGING:
                #     await self._async_adjust_charge_current(
                #         self.solarcharge.charger,
                #         self.solarcharge.chargeable,
                #         allocated_power,
                #     )

            except Exception as e:
                _LOGGER.exception(
                    "%s: Failed to adjust current for net power %s W: %s",
                    self.solarcharge.caller,
                    new_state.state,
                    e,
                )

    # ----------------------------------------------------------------------------
    def _subscribe_allocated_power_update(self) -> None:
        """Subscribe for allocated power update."""

        self.solarcharge.give_up_real_power_allocation()
        self.solarcharge.tracker.track_allocated_power_update(
            self._async_handle_allocated_power_update
        )

    # ----------------------------------------------------------------------------
    async def _async_start_session(self) -> None:
        """Start the charging session."""

        # Init instance variables
        self._init_instance_variables()

        # Init stats
        self.solarcharge.stats = ChargeStats()
        self.solarcharge.set_pause_stats(self.solarcharge.stats)

        self.solarcharge.log_configuration()

        # Subscribe for power allocation
        self._subscribe_allocated_power_update()

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Session starting state."""

        self.solarcharge.set_run_state(self.state)

        await self._async_start_session()

        self.solarcharge.set_machine_state(StateInitialise())
