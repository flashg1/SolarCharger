# ruff: noqa: TRY401, TID252
"""State machine state."""

import asyncio
from datetime import datetime, timedelta
import logging

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, State

# Might be of help in the future.
# from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.util.dt import as_local, utcnow

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import (
    CONFIG_WAIT_NET_POWER_UPDATE,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MAX_SPEED,
    NUMBER_CHARGER_MIN_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
    NUMBER_POWER_MONITOR_DURATION,
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGER_CHARGING_SENSOR,
    SENSOR_CONSUMED_POWER,
    ChargeStatus,
)
from ..exceptions.entity_exception import EntityExceptionError
from ..model_charge_stats import ChargeStats
from ..model_config import ConfigValueDict
from ..sc_option_state import ScheduleData, StateOfCharge
from .solar_charge_state import SolarChargeState
from .state_pause import StatePause
from .state_tidyup import StateTidyUp

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

INITIAL_CHARGE_CURRENT = 6  # Initial charge current in Amps
MIN_TIME_BETWEEN_UPDATE = 10  # Minimum seconds between charger current updates
MAX_CONSECUTIVE_FAILURE_COUNT = (
    10  # Max number of allowable consecutive failures in charge loop
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateCharge(SolarChargeState):
    """Charging state: Turn on charger and start charging."""

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
                        if (
                            self.solarcharge.is_calibrate_max_charge_speed()
                            or self.solarcharge.is_fast_charge_mode()
                            or self.solarcharge.running_goal.has_charge_endtime
                        ):
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

                    # Only adjust charge current if we are still in charging state
                    if self.solarcharge.get_state_name() == "StateCharge":
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
    async def _async_set_charge_limit(
        self, chargeable: Chargeable, charge_limit: float
    ) -> None:
        """Set charge limit."""

        await chargeable.async_set_charge_limit(charge_limit)
        await self.solarcharge.async_option_sleep(NUMBER_WAIT_CHARGEE_LIMIT_CHANGE)

    # ----------------------------------------------------------------------------
    async def _async_set_charge_limit_if_required(
        self, chargeable: Chargeable, goal: ScheduleData
    ) -> bool:
        """Set new charge limit if changed, otherwise use existing charge limit."""

        if charge_limit_changed := (goal.old_charge_limit != goal.new_charge_limit):
            _LOGGER.warning(
                "%s: Changing charge limit from %.1f %% to %.1f %% for %s",
                self.solarcharge.caller,
                goal.old_charge_limit,
                goal.new_charge_limit,
                # now_time.strftime("%A"),
                goal.weekly_schedule[goal.day_index].charge_day,
            )
            await self._async_set_charge_limit(chargeable, goal.new_charge_limit)

        return charge_limit_changed

    # ----------------------------------------------------------------------------
    def _is_below_charge_limit(self, chargeable: Chargeable) -> bool:
        """Is device SOC below charge limit? Always return true if SOC entity ID is not defined."""

        is_below_limit = True

        try:
            charge_limit = chargeable.get_charge_limit()

            config_item = OPTION_CHARGEE_SOC_SENSOR
            val_dict = ConfigValueDict(config_item, {})
            soc = chargeable.get_state_of_charge(val_dict)
            if val_dict.config_values[config_item].entity_id is None:
                return True

            if soc is not None and charge_limit is not None:
                is_below_limit = soc < charge_limit
                if is_below_limit:
                    _LOGGER.debug(
                        "SOC %s %% is below charge limit %s %%, continuing charger %s",
                        soc,
                        charge_limit,
                        self.solarcharge.caller,
                    )
                else:
                    _LOGGER.info(
                        "SOC %s %% is at or above charge limit %s %%, stopping charger %s",
                        soc,
                        charge_limit,
                        self.solarcharge.caller,
                    )
        except TimeoutError as e:
            _LOGGER.warning(
                "%s: Timeout getting SOC or charge limit: %s",
                self.solarcharge.caller,
                e,
            )
        except Exception as e:
            _LOGGER.exception(
                "%s: Error getting SOC or charge limit: %s",
                self.solarcharge.caller,
                e,
            )

        return is_below_limit

    # ----------------------------------------------------------------------------
    def _is_charging(
        self, charger: Charger, val_dict: ConfigValueDict | None = None
    ) -> bool:
        """Is charger currently charging? Always return false in case of error."""

        config_item = OPTION_CHARGER_CHARGING_SENSOR
        val_dict = ConfigValueDict(config_item, {}) if val_dict is None else val_dict
        is_charging = charger.is_charging(val_dict=val_dict)

        # If there is no charging sensor defined, then use the next best thing,
        # ie. use charger switch state to determine whether charger is charging or not.
        if val_dict.config_values[config_item].entity_id is None:
            is_charging = charger.is_charger_switch_on()

        return is_charging

    # ----------------------------------------------------------------------------
    def _is_use_secondary_power_source(self) -> bool:
        return self.solarcharge.is_fast_charge_mode()

    # ----------------------------------------------------------------------------
    def _check_current(self, max_current: float, current: float) -> float:
        if current < 0:
            current = 0
        elif current > max_current:
            current = max_current

        return current

    # ----------------------------------------------------------------------------
    def _get_charger_max_current(self, charger) -> float:
        """Get charger max current."""

        charger_max_current = charger.get_max_charge_current()
        if charger_max_current is None or charger_max_current <= 0:
            raise ValueError("Failed to get charger max current")

        return charger_max_current

    # ----------------------------------------------------------------------------
    def _calc_current_change(
        self,
        charger: Charger,
        chargeable: Chargeable,
        allocated_power: float,
        goal: ScheduleData,
    ) -> tuple[float, float]:
        """Calculate new charge current based on allocated power."""

        charger_max_current = self._get_charger_max_current(charger)

        battery_charge_current = charger.get_charge_current()
        if battery_charge_current is None:
            raise ValueError("Failed to get charge current")
        old_charge_current = self._check_current(
            charger_max_current, battery_charge_current
        )

        #####################################
        # Charge at max current if fast charge
        #####################################
        if (
            self.solarcharge.is_fast_charge_mode()
            or self.solarcharge.is_calibrate_max_charge_speed()
        ):
            new_charge_current = charger_max_current
            return (new_charge_current, old_charge_current)

        #####################################
        # Set minimum charge current
        #####################################
        config_min_current = self.solarcharge.option_get_entity_number_or_abort(
            NUMBER_CHARGER_MIN_CURRENT
        )
        config_min_current = self._check_current(
            charger_max_current, config_min_current
        )

        charger_min_current = config_min_current
        if goal.use_charge_schedule:
            if self.solarcharge.scheduler.is_not_enough_time_to_complete_charge(
                chargeable,
                old_charge_current,
                charger_max_current,
                goal,
            ):
                charger_min_current = charger_max_current

        #####################################
        # Calculate new current from allocated power
        #####################################
        charger_effective_voltage = self.solarcharge.option_get_entity_number_or_abort(
            NUMBER_CHARGER_EFFECTIVE_VOLTAGE
        )
        if charger_effective_voltage <= 0:
            raise ValueError(
                f"Invalid charger effective voltage {charger_effective_voltage}"
            )

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
            self.solarcharge.option_get_entity_number_or_abort(
                NUMBER_CHARGER_MIN_WORKABLE_CURRENT
            )
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
    def _get_charge_status(
        self,
        charger: Charger,
        chargeable: Chargeable,
        goal: ScheduleData,
        max_allocation_count: int,
        power_allocations: list[float],
        stats: ChargeStats,
    ) -> ChargeStatus:
        """Check if to continue charging."""
        charge_status: ChargeStatus = ChargeStatus.CHARGE_EXIT

        is_connected = self.solarcharge.is_connected(charger)

        # Device charge limit must have already been set before this check.
        is_below_charge_limit = self._is_below_charge_limit(chargeable)

        val_dict = ConfigValueDict(OPTION_CHARGER_CHARGING_SENSOR, {})
        is_charging = self._is_charging(charger, val_dict=val_dict)

        is_sun_trigger = self.solarcharge.is_sun_trigger()
        (is_sun_above_start_end_elevations, elevation) = (
            self.solarcharge.is_sun_above_start_end_elevation_triggers()
        )
        is_use_secondary_power_source = self._is_use_secondary_power_source()
        is_calibrate_max_charge_speed = self.solarcharge.is_calibrate_max_charge_speed()

        # Add 30 minutes grace period to avoid time drift stopping charge
        # and scheduling next session immediately.
        current_time_with_grace = goal.data_timestamp + timedelta(minutes=30)
        if goal.has_charge_endtime and goal.propose_charge_starttime != datetime.min:
            is_immediate_start_with_grace = (
                goal.propose_charge_starttime <= current_time_with_grace
            )
        else:
            is_immediate_start_with_grace = False

        # Charge just-in-time feature:
        # If end time is set, charge can still stop at end elevation trigger,
        # and then start again closer to end time to complete charge.
        continue_charge = (
            is_connected
            and is_below_charge_limit
            and (stats.loop_success == 0 or is_charging)
            and (
                not is_sun_trigger  # Sun trigger off, continue.
                or is_sun_above_start_end_elevations  # Sun trigger on, continue if between start and end elevations.
                or is_use_secondary_power_source
                or is_calibrate_max_charge_speed
                or (goal.has_charge_endtime and is_immediate_start_with_grace)
            )
        )

        if continue_charge:
            charge_status = ChargeStatus.CHARGE_CONTINUE
            if max_allocation_count > 0:
                is_enough_power = self.solarcharge.is_average_allocated_power_more_than_min_workable_power(
                    max_allocation_count, power_allocations
                )
                if is_enough_power is not None and not is_enough_power:
                    charge_status = ChargeStatus.CHARGE_PAUSE

        if charge_status != ChargeStatus.CHARGE_CONTINUE:
            _LOGGER.warning(
                "%s: Stopping charge: charge_status=%s, "
                "is_connected=%s, is_below_charge_limit=%s, is_charging=%s (%s), "
                "is_sun_trigger=%s, is_sun_above_start_end_elevations=%s, elevation=%s, "
                "is_use_secondary_power_source=%s, is_calibrate_max_charge_speed=%s, "
                "has_charge_endtime=%s, is_immediate_start=%s, "
                "propose_charge_starttime=%s, current_time_with_grace=%s, is_immediate_start_with_grace=%s, "
                "stats=%s",
                self.solarcharge.caller,
                charge_status,
                is_connected,
                is_below_charge_limit,
                is_charging,
                val_dict.config_values[OPTION_CHARGER_CHARGING_SENSOR].entity_value,
                is_sun_trigger,
                is_sun_above_start_end_elevations,
                elevation,
                is_use_secondary_power_source,
                is_calibrate_max_charge_speed,
                goal.has_charge_endtime,
                goal.is_immediate_start,
                goal.propose_charge_starttime,
                current_time_with_grace,
                is_immediate_start_with_grace,
                stats,
            )

        return charge_status

    # ----------------------------------------------------------------------------
    def _log_charging_status(self, charger: Charger, msg: str) -> None:
        """Generate debug message only if required."""

        val_dict = ConfigValueDict(OPTION_CHARGER_CHARGING_SENSOR, {})
        is_charging = self._is_charging(charger, val_dict=val_dict)

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
            self.solarcharge.session_triggered_by_timer,
            self.solarcharge.started_calibrate_max_charge_speed,
            msg="Calibration",
        )
        if self.solarcharge.scheduler.calibration_charge_limit == -1:
            raise EntityExceptionError("Charge limit not set")

        # Track SOC
        self.solarcharge.soc_updates = []
        if self.solarcharge.tracker.track_soc_sensor(self.async_handle_soc_update):
            # Change charge limit if required
            await self._async_set_charge_limit_if_required(chargeable, goal)
            # Set max current
            charger_max_current = self._get_charger_max_current(charger)
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

        if monitor_duration > 0 and monitor_duration_seconds > wait_net_power_update:
            self.solarcharge.max_allocation_count = int(
                monitor_duration_seconds / wait_net_power_update
            )
        else:
            self.solarcharge.max_allocation_count = 0

    # ----------------------------------------------------------------------------
    async def _async_charge_device(
        self, charger: Charger, chargeable: Chargeable
    ) -> ChargeStatus:
        """Loop to charge device."""
        charge_status: ChargeStatus = ChargeStatus.CHARGE_EXIT

        self.solarcharge.wait_net_power_update = (
            self.solarcharge.config_get_number_or_abort(CONFIG_WAIT_NET_POWER_UPDATE)
        )
        self._set_max_allocation_count(self.solarcharge.wait_net_power_update)
        self.solarcharge.power_allocations = []

        while True:
            # Abort charge if exceeds MAX_CONSECUTIVE_FAILURE_COUNT
            if (
                self.solarcharge.stats.consecutive_failure_count
                > MAX_CONSECUTIVE_FAILURE_COUNT
            ):
                raise RuntimeError(
                    f"Exceeded max number of allowable consecutive failures ({MAX_CONSECUTIVE_FAILURE_COUNT}) in charge loop"
                )

            try:
                # Get schedule data at start of each loop since schedule might change while charging.
                self.solarcharge.running_goal = (
                    await self.solarcharge.scheduler.async_get_schedule_data(
                        chargeable,
                        self.solarcharge.session_triggered_by_timer,
                        self.solarcharge.started_calibrate_max_charge_speed,
                        msg="Loop",
                    )
                )

                # Set charge limit if required.
                # Once set, the latest and correct state can be requested without calling _async_update_ha() first.
                await self._async_set_charge_limit_if_required(
                    chargeable, self.solarcharge.running_goal
                )

                # Check if continue charging or exit loop. Must run after setting charge limit.
                if (
                    charge_status := self._get_charge_status(
                        charger,
                        chargeable,
                        self.solarcharge.running_goal,
                        self.solarcharge.max_allocation_count,
                        self.solarcharge.power_allocations,
                        self.solarcharge.stats,
                    )
                ) != ChargeStatus.CHARGE_CONTINUE:
                    break

                # Turn on charger if looping for the first time.
                if self.solarcharge.stats.loop_success == 0:
                    self.solarcharge.starting_goal = self.solarcharge.running_goal
                    self.solarcharge.scheduler.log_goal(
                        self.solarcharge.starting_goal, "Start session"
                    )
                    await self.solarcharge.async_turn_charger_switch(
                        charger, turn_on=True
                    )
                    await self.solarcharge.async_set_charge_current(
                        charger, INITIAL_CHARGE_CURRENT
                    )
                    await self.solarcharge.async_update_ha(chargeable)
                    self._subscribe_allocated_power_update()
                    self._log_charging_status(charger, "Charger ON")

                # Completed loop successfully at this point.
                self.solarcharge.stats.loop_success += 1
                self.solarcharge.stats.consecutive_failure_count = 0

                # Check if calibration is required during charge.
                await self._async_calibrate_max_charge_speed_if_required(
                    charger, chargeable
                )

            except TimeoutError as e:
                self.solarcharge.stats.loop_failure += 1
                self.solarcharge.stats.consecutive_failure_count += 1
                _LOGGER.warning(
                    "%s: Timeout charging device: %s", self.solarcharge.caller, e
                )
            except Exception as e:
                self.solarcharge.stats.loop_failure += 1
                self.solarcharge.stats.consecutive_failure_count += 1
                _LOGGER.exception(
                    "%s: Error charging device: %s", self.solarcharge.caller, e
                )

            # Update status after turning on power, or at every interval.
            # This is either required here or after setting current.
            # It is better here since it is garanteed periodic.
            # Do not wait here. Depends on the main loop to wait.
            await self.solarcharge.async_update_ha(chargeable, wait_after_update=False)

            # Sleep before re-evaluating charging conditions.
            # Charging state must be "charging" for loop_count > 0.
            # Tesla BLE need 25 seconds here, ie. OPTION_WAIT_CHARGEE_UPDATE_HA = 25 seconds
            await asyncio.sleep(self.solarcharge.wait_net_power_update)
            self.solarcharge.stats.loop_total += 1

        return charge_status

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start charging state."""

        charge_status = await self._async_charge_device(
            self.solarcharge.charger, self.solarcharge.chargeable
        )

        if charge_status == ChargeStatus.CHARGE_PAUSE:
            self.solarcharge.set_state(StatePause())
        else:
            self.solarcharge.set_state(StateTidyUp())
