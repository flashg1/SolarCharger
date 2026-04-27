# ruff: noqa: TRY401, TID252
"""State machine state."""

import asyncio
import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, State
from homeassistant.util.dt import as_local, utcnow

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import (
    NUMBER_CHARGER_MAX_SPEED,
    NUMBER_POWER_MONITOR_DURATION,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_GET_CHARGE_CURRENT,
    SENSOR_CONSUMED_POWER,
    ChargeStatus,
    RunState,
)
from ..exceptions.entity_exception import EntityExceptionError
from ..models.model_charge_stats import ChargeStats
from ..models.model_config import ConfigValueDict
from ..models.model_context_data import ContextData
from ..models.model_schedule_data import ScheduleData
from ..models.model_state_of_charge import StateOfCharge
from .solar_charge_state import SolarChargeState
from .state_pause import StatePause
from .state_tidyup import StateTidyUp

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

INITIAL_CHARGE_CURRENT = 6  # Initial charge current in Amps
MIN_TIME_BETWEEN_UPDATE = 10  # Minimum seconds between charger current updates


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateCharge(SolarChargeState):
    """Charging state: Turn on charger and start charging."""

    def __init__(
        self,
    ) -> None:
        """Initialise machine state."""
        self.state = RunState.CHARGING

    # ----------------------------------------------------------------------------
    # Subscriptions
    # ----------------------------------------------------------------------------
    async def _async_adjust_charge_current(
        self, charger: Charger, chargeable: Chargeable, allocated_power: float
    ) -> None:
        """Adjust charge current."""

        new_charge_current, old_charge_current = self._calc_current_change(
            charger, chargeable, allocated_power, self.solarcharge.running_goal
        )
        if new_charge_current != old_charge_current:
            _LOGGER.info(
                "%s: Update current from %s to %s",
                self.solarcharge.caller,
                old_charge_current,
                new_charge_current,
            )
            await self.solarcharge.async_set_charge_current(charger, new_charge_current)
            self.solarcharge.charge_current_updatetime = utcnow().timestamp()

        # No need to update status here because it is now done at the main loop.
        # Power update here is not garanteed because HA will not send the same value
        # if the second value is same as first.
        # await self._async_update_ha(chargeable)

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

            # Make sure we don't change the charge current too often
            if duration_since_last_change >= MIN_TIME_BETWEEN_UPDATE:
                try:
                    allocated_power = float(new_state.state)

                    # Save allocated power to calculate moving average.
                    if self.solarcharge.max_allocation_count > 0:
                        if not self.solarcharge.is_monitor_available_power():
                            self.solarcharge.power_allocations = []
                        elif (
                            len(self.solarcharge.power_allocations)
                            >= self.solarcharge.max_allocation_count
                        ):
                            self.solarcharge.power_allocations.pop(0)

                        assert self.solarcharge.entities.sensors is not None
                        consumed_power = float(
                            self.solarcharge.entities.sensors[
                                SENSOR_CONSUMED_POWER
                            ].state
                        )
                        self.solarcharge.power_allocations.append(
                            allocated_power - consumed_power
                        )

                    # This callback is still running in paused state.
                    # Only adjust charge current if we are still in charging state
                    if self.solarcharge.machine_state.state == RunState.CHARGING:
                        await self._async_adjust_charge_current(
                            self.solarcharge.charger,
                            self.solarcharge.chargeable,
                            allocated_power,
                        )

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

        self.solarcharge.tracker.track_allocated_power_update(
            self._async_handle_allocated_power_update
        )

    # ----------------------------------------------------------------------------
    async def async_handle_soc_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        self.solarcharge.tracker.log_state_change(event)

        if new_state is not None and old_state is not None:
            if (
                new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                # Sometimes new state was updated with much later time, indicating a possible refresh
                # caused by initial subscription. So compare old and new states and ignore if same.
                and new_state.state != old_state.state
            ):
                try:
                    soc = float(new_state.state)
                    update_time = as_local(new_state.last_updated)
                    self.solarcharge.soc_updates.append(StateOfCharge(soc, update_time))
                    max_charge_speed = 0.0

                    _LOGGER.warning(
                        "%s: soc=%s %%, update_time=%s",
                        self.solarcharge.caller,
                        soc,
                        update_time,
                    )
                    if len(self.solarcharge.soc_updates) > 1:
                        soc_diff = soc - self.solarcharge.soc_updates[0].state_of_charge
                        time_diff = (
                            update_time - self.solarcharge.soc_updates[0].update_time
                        )
                        hour_diff = time_diff.total_seconds() / 3600.0
                        max_charge_speed = soc_diff / hour_diff
                        _LOGGER.warning(
                            "%s: max_charge_speed=%s %%/hr, %s",
                            self.solarcharge.caller,
                            max_charge_speed,
                            self.solarcharge.soc_updates,
                        )

                    if soc >= self.solarcharge.scheduler.calibration_charge_limit:
                        if max_charge_speed > 0:
                            await self.solarcharge.async_option_set_entity_number(
                                NUMBER_CHARGER_MAX_SPEED, max_charge_speed
                            )
                        else:
                            _LOGGER.error(
                                "%s: Abort setting invalid max charge speed: %s %%/hr",
                                self.solarcharge.caller,
                                max_charge_speed,
                            )
                        await self.solarcharge.async_turn_off_calibrate_max_charge_speed_switch()

                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "%s: Failed to parse SOC state '%s': %s",
                        self.solarcharge.caller,
                        new_state.state,
                        e,
                    )

    # ----------------------------------------------------------------------------
    # Charge loop
    # ----------------------------------------------------------------------------
    def _calc_current_change(
        self,
        charger: Charger,
        chargeable: Chargeable,
        allocated_power: float,
        goal: ScheduleData,
    ) -> tuple[float, float]:
        """Calculate new charge current based on allocated power."""

        charger_max_current = self.solarcharge.get_charger_max_current()

        config_item = OPTION_CHARGER_GET_CHARGE_CURRENT
        val_dict = ConfigValueDict(config_item, {})
        battery_charge_current = self.solarcharge.get_charge_current(charger, val_dict)
        if val_dict.config_values[OPTION_CHARGER_GET_CHARGE_CURRENT].entity_id is None:
            # So we can't get the current, ie. a resistive load.
            # All devices must have max charge current configured.
            new_charge_current = charger_max_current
            old_charge_current = charger_max_current
            return (new_charge_current, old_charge_current)

        if battery_charge_current is None:
            raise ValueError("Failed to get charge current")
        old_charge_current = self.solarcharge.validate_current(
            charger_max_current, battery_charge_current
        )

        #####################################
        # Charge at max current if fast charge
        #####################################
        if (
            self.solarcharge.is_fast_charge_mode()
            or self.solarcharge.is_calibrate_max_charge_speed()
            or (goal.has_charge_endtime and goal.max_charge_now)
        ):
            new_charge_current = charger_max_current
            return (new_charge_current, old_charge_current)

        #####################################
        # Set minimum charge current
        #####################################
        config_min_current = self.solarcharge.get_charger_min_current(
            charger_max_current
        )

        charger_min_current = config_min_current
        # if goal.use_charge_schedule:
        #     if self.solarcharge.scheduler.is_not_enough_time_to_complete_charge(
        #         old_charge_current,
        #         charger_max_current,
        #         goal,
        #     ):
        #         charger_min_current = charger_max_current

        #####################################
        # Calculate new current from allocated power
        #####################################
        charger_effective_voltage = self.solarcharge.get_charger_effective_voltage()
        one_amp_watt_step = charger_effective_voltage * 1
        power_offset = 0
        all_power_net = allocated_power + (one_amp_watt_step * 0.3) + power_offset
        all_current_net = all_power_net / charger_effective_voltage

        if all_current_net > 0:
            propose_charge_current = round(
                max([charger_min_current, old_charge_current - all_current_net])
            )
        else:
            propose_charge_current = round(
                min([charger_max_current, old_charge_current - all_current_net])
            )
        propose_new_charge_current = max([charger_min_current, propose_charge_current])

        charger_min_workable_current = (
            self.solarcharge.get_charger_min_workable_current()
        )
        if propose_new_charge_current < charger_min_workable_current:
            new_charge_current = 0
        else:
            new_charge_current = propose_new_charge_current

        _LOGGER.debug(
            "%s: allocated_power=%s, charger_effective_voltage=%s, config_min_current=%s, "
            "charger_min_current=%s, charger_max_current=%s, old_charge_current=%s, "
            "all_power_net=%s, all_current_net=%s, propose_charge_current=%s, "
            "propose_new_charge_current=%s, charger_min_workable_current=%s, "
            "new_charge_current=%s ",
            self.solarcharge.caller,
            allocated_power,
            charger_effective_voltage,
            config_min_current,
            charger_min_current,
            charger_max_current,
            old_charge_current,
            all_power_net,
            all_current_net,
            propose_charge_current,
            propose_new_charge_current,
            charger_min_workable_current,
            new_charge_current,
        )

        return (new_charge_current, old_charge_current)

    # ----------------------------------------------------------------------------
    def _log_charging_status(self, charger: Charger, msg: str) -> None:
        """Generate debug message only if required."""

        val_dict = ConfigValueDict(OPTION_CHARGER_CHARGING_SENSOR, {})
        is_charging = self.solarcharge.is_charging(charger, val_dict=val_dict)

        _LOGGER.warning(
            "%s: %s: is_connected=%s, is_charger_switch_on=%s, is_charging=%s (%s)",
            self.solarcharge.caller,
            msg,
            self.solarcharge.is_connected(charger),
            charger.is_charger_switch_on(),
            is_charging,
            val_dict.config_values[OPTION_CHARGER_CHARGING_SENSOR].entity_value,
        )

    # ----------------------------------------------------------------------------
    async def _async_start_max_charge_speed_calibration(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Start max charge speed calibration."""

        # Set the calibration charge limit
        goal = await self.solarcharge.scheduler.async_get_schedule_data(
            chargeable,
            timer_session=self.solarcharge.session_triggered_by_timer,
            include_tomorrow=self.solarcharge.session_triggered_by_timer,
            started_calibration=self.solarcharge.started_calibrate_max_charge_speed,
            started_max_charge=self.solarcharge.started_max_charge,
            msg="Calibration",
        )
        if self.solarcharge.scheduler.calibration_charge_limit == -1:
            raise EntityExceptionError("Charge limit not set")

        # Track SOC
        self.solarcharge.soc_updates = []
        if self.solarcharge.tracker.track_soc_sensor(self.async_handle_soc_update):
            # Change charge limit if required
            await self.solarcharge.async_set_charge_limit_if_required(chargeable, goal)
            # Set max current
            charger_max_current = self.solarcharge.get_charger_max_current()
            await self.solarcharge.async_set_charge_current(
                charger, charger_max_current
            )
        else:
            raise EntityExceptionError("Missing SOC sensor")

        self.solarcharge.scheduler.log_goal(goal, "Calibrate charge speed")

    # ----------------------------------------------------------------------------
    async def _async_calibrate_max_charge_speed_if_required(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Check if calibration is required during charge."""

        if self.solarcharge.is_calibrate_max_charge_speed():
            if not self.solarcharge.started_calibrate_max_charge_speed:
                try:
                    await self._async_start_max_charge_speed_calibration(
                        charger, chargeable
                    )

                    self.solarcharge.started_calibrate_max_charge_speed = True

                except EntityExceptionError as e:
                    _LOGGER.error(
                        "%s: Abort calibrate max charge speed: %s",
                        self.solarcharge.caller,
                        e,
                    )
                    await self.solarcharge.async_turn_off_calibrate_max_charge_speed_switch()

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
    async def _switch_on_charger_and_set_current(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Switch on charger and set initial current."""

        self.solarcharge.starting_goal = self.solarcharge.running_goal
        self.solarcharge.scheduler.log_goal(
            self.solarcharge.starting_goal, "Start session"
        )
        await self.solarcharge.async_turn_charger_switch(charger, turn_on=True)
        await self.solarcharge.async_set_charge_current(charger, INITIAL_CHARGE_CURRENT)
        await self.solarcharge.async_update_ha(chargeable)
        self._subscribe_allocated_power_update()
        self._log_charging_status(charger, "Charger ON")

    # ----------------------------------------------------------------------------
    async def _async_charge_device(
        self,
        charger: Charger,
        chargeable: Chargeable,
        state: RunState,
        stats: ChargeStats,
    ) -> ContextData:
        """Loop to charge device."""

        # Init power monitor duration
        self.solarcharge.wait_net_power_update = (
            self.solarcharge.get_wait_net_power_update()
        )
        self._set_max_allocation_count(self.solarcharge.wait_net_power_update)
        self.solarcharge.power_allocations = []

        # Initialise counts before starting loop
        stats.loop_success_count = 0
        stats.loop_consecutive_fail_count = 0
        done_switch_on_charger = False
        while True:
            self.solarcharge.abort_if_exceed_max_consecutive_failure()

            try:
                # Update status periodically, and just before checking status.
                # Do not wait here. Depends on the main loop to wait.
                await self.solarcharge.async_update_ha(
                    chargeable, wait_after_update=False
                )

                # Check if continue charging or exit loop.
                context = await self.solarcharge.async_set_charge_status(
                    charger, chargeable, state, stats
                )
                if context.next_step != ChargeStatus.CHARGE_CONTINUE:
                    break

                # Turn on charger if looping for the first time.
                # Do async_update_ha() after turning on power or setting current.
                if not done_switch_on_charger:
                    await self._switch_on_charger_and_set_current(charger, chargeable)
                    done_switch_on_charger = True

                # Check if calibration is required during charge.
                await self._async_calibrate_max_charge_speed_if_required(
                    charger, chargeable
                )

                # Completed loop successfully at this point.
                stats.loop_success_count += 1
                stats.loop_consecutive_fail_count = 0

            except TimeoutError as e:
                stats.loop_total_fail_count += 1
                stats.loop_consecutive_fail_count += 1
                _LOGGER.warning(
                    "%s: Timeout charging device: %s", self.solarcharge.caller, e
                )
            except Exception as e:
                stats.loop_total_fail_count += 1
                stats.loop_consecutive_fail_count += 1
                _LOGGER.exception(
                    "%s: Error charging device: %s", self.solarcharge.caller, e
                )

            # Sleep before re-evaluating charging conditions.
            # Charging state must be "charging" for loop_count > 0.
            # Tesla BLE need 25 seconds here, ie. OPTION_WAIT_CHARGEE_UPDATE_HA = 25 seconds
            await asyncio.sleep(self.solarcharge.wait_net_power_update)
            stats.loop_total_count += 1

        return context

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start charging state."""

        self.solarcharge.set_run_state(self.state)

        context = await self._async_charge_device(
            self.solarcharge.charger,
            self.solarcharge.chargeable,
            self.solarcharge.machine_state.state,
            self.solarcharge.stats,
        )

        self.solarcharge.log_context(context)

        if context.next_step == ChargeStatus.CHARGE_PAUSE:
            self.solarcharge.set_machine_state(StatePause())
        else:
            self.solarcharge.set_machine_state(StateTidyUp())
