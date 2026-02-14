"""Module to manage the solar charging."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import date, datetime, time, timedelta
import inspect
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers import device_registry as dr

# Might be of help in the future.
# from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.util.dt import as_local, utcnow

from ..const import (  # noqa: TID252
    CALIBRATE_MAX_SOC,
    CALIBRATE_SOC_INCREASE,
    CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE,
    CONF_WAIT_NET_POWER_UPDATE,
    DATETIME,
    DATETIME_NEXT_CHARGE_TIME,
    DOMAIN,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MAX_SPEED,
    NUMBER_CHARGER_MIN_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
    NUMBER_WAIT_CHARGEE_UPDATE_HA,
    NUMBER_WAIT_CHARGEE_WAKEUP,
    NUMBER_WAIT_CHARGER_AMP_CHANGE,
    NUMBER_WAIT_CHARGER_OFF,
    NUMBER_WAIT_CHARGER_ON,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    SWITCH,
    SWITCH_CALIBRATE_MAX_CHARGE_SPEED,
    SWITCH_CHARGE,
    SWITCH_FAST_CHARGE_MODE,
    SWITCH_PLUGIN_TRIGGER,
    SWITCH_POLL_CHARGER_UPDATE,
    SWITCH_SCHEDULE_CHARGE,
    SWITCH_SUN_TRIGGER,
)
from ..entity import compose_entity_id  # noqa: TID252
from ..exceptions.entity_exception import EntityExceptionError  # noqa: TID252
from ..model_config import ConfigValueDict  # noqa: TID252
from ..sc_option_state import (  # noqa: TID252
    ChargeSchedule,
    ScheduleData,
    ScOptionState,
    StateOfCharge,
)
from ..utils import (  # noqa: TID252
    get_next_sunrise_time,
    get_sec_per_degree_sun_elevation,
    get_sun_elevation,
    log_is_event_loop,
)
from .chargeable import Chargeable
from .charger import Charger
from .tracker import Tracker

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

type SWITCH_ACTION = Callable[[bool], Coroutine[Any, Any, None]]


INITIAL_CHARGE_CURRENT = 6  # Initial charge current in Amps
MIN_TIME_BETWEEN_UPDATE = 10  # Minimum seconds between charger current updates

# Look ahead charge limit list including today.
# Use MAX_CHARGE_LIMIT_DIFF to calculate charge limit for all days except one day before maximum charge limit day.
# The day before maximum charge limit day will use MIN_CHARGE_LIMIT_DIFF to minimise charge limit difference for the next day.
MIN_CHARGE_LIMIT_DIFF = 5
MAX_CHARGE_LIMIT_DIFF = 10
LOOK_AHEAD_CHARGE_LIMIT_DAYS = 4


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarCharge(ScOptionState):
    """Class to manage the charging process."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        tracker: Tracker,
        charger: Any,
        chargeable: Any,
        # charger: Charger,
        # chargeable: Chargeable,
    ) -> None:
        """Initialize the Charge instance."""

        caller = subentry.unique_id
        if caller is None:
            caller = __name__
        ScOptionState.__init__(self, hass, entry, subentry, caller)

        self._tracker = tracker
        self._charger = charger
        self._chargeable = chargeable

        # Non-modifiable local device entities, ie.
        # not defined in config_options_flow _charger_control_entities_schema().
        # These entities are also defined in config options, but not created until
        # after first initialisation (see above).
        self._next_charge_time_trigger = compose_entity_id(
            DATETIME, subentry.unique_id, DATETIME_NEXT_CHARGE_TIME
        )

        self._fast_charge_mode_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_FAST_CHARGE_MODE
        )
        self._poll_charger_update_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_POLL_CHARGER_UPDATE
        )

        self._charge_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_CHARGE
        )
        self._schedule_charge_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_SCHEDULE_CHARGE
        )
        self._plugin_trigger_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_PLUGIN_TRIGGER
        )
        self._sun_trigger_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_SUN_TRIGGER
        )
        self._calibrate_max_charge_speed_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_CALIBRATE_MAX_CHARGE_SPEED
        )

        self._history_date = datetime(2026, 1, 1, 0, 0, 0)

        self._session_triggered_by_timer = False
        self._starting_goal: ScheduleData
        self._running_goal: ScheduleData

        self._started_calibrate_max_charge_speed = False
        self._charge_current_updatetime: float = 0
        self._soc_updates: list[StateOfCharge] = []
        self._calibrate_max_charge_limit: float

    # ----------------------------------------------------------------------------
    @cached_property
    def _device(self) -> dr.DeviceEntry:
        """Get the device entry for the controller."""
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._subentry.subentry_id)}
        )
        if device is None:
            raise RuntimeError(f"{self._caller} device entry not found.")
        return device

    # ----------------------------------------------------------------------------
    @property
    def is_chargeable(self) -> bool:
        """Return True if the charger is chargeable."""
        return isinstance(self._charger, Chargeable)

    @property
    def get_chargee(self) -> Chargeable | None:
        """Return the chargeable device if applicable."""
        if self.is_chargeable:
            return self._charger  # type: ignore[return-value]
        return None

    @property
    def next_charge_time_trigger(self) -> str:
        """Return the next charge time trigger entity ID."""
        return self._next_charge_time_trigger

    @property
    def fast_charge_mode_switch(self) -> str:
        """Return the fast charge mode switch entity ID."""
        return self._fast_charge_mode_switch

    @property
    def poll_charger_update_switch(self) -> str:
        """Return the poll charger update switch entity ID."""
        return self._poll_charger_update_switch

    @property
    def charge_switch(self) -> str:
        """Return the charge switch entity ID."""
        return self._charge_switch

    @property
    def schedule_charge_switch(self) -> str:
        """Return the schedule charge switch entity ID."""
        return self._schedule_charge_switch

    @property
    def plugin_trigger_switch(self) -> str:
        """Return the plugin trigger switch entity ID."""
        return self._plugin_trigger_switch

    @property
    def sun_trigger_switch(self) -> str:
        """Return the sun trigger switch entity ID."""
        return self._sun_trigger_switch

    @property
    def calibrate_max_charge_speed_switch(self) -> str:
        """Return the calibrate max charge speed switch entity ID."""
        return self._calibrate_max_charge_speed_switch

    # ----------------------------------------------------------------------------
    # Local device control entities
    # ----------------------------------------------------------------------------
    def is_fast_charge_mode(self) -> bool:
        """Is fast charge mode on?"""
        return self.get_boolean_or_abort(self.fast_charge_mode_switch)

    # ----------------------------------------------------------------------------
    def is_poll_charger_update(self) -> bool:
        """Is poll charger update on?"""
        return self.get_boolean_or_abort(self.poll_charger_update_switch)

    # ----------------------------------------------------------------------------
    def is_schedule_charge(self) -> bool:
        """Is schedule charge on?"""
        return self.get_boolean_or_abort(self.schedule_charge_switch)

    # ----------------------------------------------------------------------------
    def is_plugin_trigger(self) -> bool:
        """Is plugin trigger on?"""
        return self.get_boolean_or_abort(self.plugin_trigger_switch)

    # ----------------------------------------------------------------------------
    def is_sun_trigger(self) -> bool:
        """Is sun trigger on?"""
        return self.get_boolean_or_abort(self.sun_trigger_switch)

    # ----------------------------------------------------------------------------
    def is_charge_switch_on(self) -> bool:
        """Is charge switch on?"""
        return self.get_boolean_or_abort(self.charge_switch)

    # ----------------------------------------------------------------------------
    def is_calibrate_max_charge_speed(self) -> bool:
        """Is calibrate max charge speed on?"""
        return self.get_boolean_or_abort(self.calibrate_max_charge_speed_switch)

    # ----------------------------------------------------------------------------
    async def async_stop_calibrate_max_charge_speed(self) -> None:
        """Stop tracking SOC and reset flag."""

        self._tracker.untrack_soc_sensor()
        self._started_calibrate_max_charge_speed = False

    # ----------------------------------------------------------------------------
    async def _async_turn_off_calibrate_max_charge_speed_switch(self) -> None:
        """Turn off switch if on."""

        if self.is_calibrate_max_charge_speed():
            await self.async_stop_calibrate_max_charge_speed()
            await self.async_turn_switch(
                self._calibrate_max_charge_speed_switch, turn_on=False
            )

    # ----------------------------------------------------------------------------
    def _get_charge_limit_or_abort(self, chargeable: Chargeable) -> float:
        """Get charge limit from chargeable device or abort."""

        charge_limit = chargeable.get_charge_limit()
        if charge_limit is None:
            raise EntityExceptionError(
                f"{self._caller}: Cannot get charge limit from chargeable device"
            )

        return charge_limit

    # ----------------------------------------------------------------------------
    # Subscriptions
    # ----------------------------------------------------------------------------
    def _subscribe_allocated_power_update(self) -> None:
        """Subscribe for allocated power update."""

        self._tracker.track_allocated_power_update(
            self._async_handle_allocated_power_update
        )

    # ----------------------------------------------------------------------------
    def _unsubscribe_allocated_power_update(self) -> None:
        """Unsubscribe allocated power update."""

        self._tracker.untrack_allocated_power_update()

    # ----------------------------------------------------------------------------
    async def async_handle_soc_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        self._tracker.log_state_change(event)

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
                    self._soc_updates.append(StateOfCharge(soc, update_time))
                    max_charge_speed = 0.0

                    _LOGGER.warning(
                        "%s: soc=%s %%, update_time=%s",
                        self._caller,
                        soc,
                        update_time,
                    )
                    if len(self._soc_updates) > 1:
                        soc_diff = soc - self._soc_updates[0].state_of_charge
                        time_diff = update_time - self._soc_updates[0].update_time
                        hour_diff = time_diff.total_seconds() / 3600.0
                        max_charge_speed = soc_diff / hour_diff
                        _LOGGER.warning(
                            "%s: max_charge_speed=%s %%/hr, %s",
                            self._caller,
                            max_charge_speed,
                            self._soc_updates,
                        )

                    if soc >= self._calibrate_max_charge_limit:
                        await self.async_option_set_entity_number(
                            NUMBER_CHARGER_MAX_SPEED, max_charge_speed
                        )
                        await self._async_turn_off_calibrate_max_charge_speed_switch()

                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "%s: Failed to parse SOC state '%s': %s",
                        self._caller,
                        new_state.state,
                        e,
                    )

    # ----------------------------------------------------------------------------
    # Set up and unload
    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Async setup of SolarCharge."""

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of SolarCharge."""

        self._unsubscribe_allocated_power_update()
        self._tracker.untrack_soc_sensor()

    # ----------------------------------------------------------------------------
    # Charger code
    # ----------------------------------------------------------------------------
    # Estimation only.
    # Run this first thing before starting session.
    def _is_session_triggered_by_timer(self) -> bool:
        """Trigger by timer?"""
        triggered_by_timer = False
        time_diff = timedelta(seconds=0)

        charge_start_time = self.get_local_datetime()
        next_charge_time = self.get_datetime(self._next_charge_time_trigger)
        if next_charge_time is not None:
            if charge_start_time > next_charge_time:
                time_diff = charge_start_time - next_charge_time
            else:
                time_diff = next_charge_time - charge_start_time
            if time_diff < timedelta(seconds=30):
                triggered_by_timer = True

        _LOGGER.warning(
            "%s: charge_start_time=%s, next_charge_time=%s, time_diff=%s, triggered_by_timer=%s",
            self._caller,
            charge_start_time,
            next_charge_time,
            time_diff,
            triggered_by_timer,
        )

        return triggered_by_timer

    # ----------------------------------------------------------------------------
    def _calc_charge_starttime(self, goal: ScheduleData) -> None:
        """Calculate charge start time required to reach charge limit at charge end time."""

        if goal.has_charge_endtime:
            if goal.battery_soc is None:
                _LOGGER.info(
                    "%s: Unable to get battery SOC, cannot schedule next charge session",
                    self._caller,
                )
                return

            if goal.battery_soc >= goal.new_charge_limit:
                _LOGGER.info(
                    "%s: Battery SOC %.1f %% is at or above charge limit %.1f %%, no need to schedule next charge session",
                    self._caller,
                    goal.battery_soc,
                    goal.new_charge_limit,
                )
                return

            # Must check propose_charge_starttime before use due to return above, otherwise will get following exception when comparing times:
            # tesla_custom_tesla23m3: Abort charge: can't compare offset-naive and offset-aware datetimes
            goal.need_charge_duration = self._calculate_need_charge_duration(
                goal.battery_soc, goal.new_charge_limit
            )

            goal.propose_charge_starttime = (
                goal.charge_endtime - goal.need_charge_duration
            )

            if goal.propose_charge_starttime <= goal.data_timestamp:
                goal.is_immediate_start = True

    # ----------------------------------------------------------------------------
    def _look_ahead_to_reduce_charge_limit_difference(self, goal: ScheduleData) -> None:
        """Look ahead to reduce charge limit difference between days."""

        # Automatically charge more today if today has no charge end time and next 3 days have much higher charge limit.
        if not goal.has_charge_endtime:
            look_ahead_schedule: list[ChargeSchedule] = []
            today_index = goal.day_index

            for i in range(0, LOOK_AHEAD_CHARGE_LIMIT_DAYS, 1):
                day_index = (today_index + i) % 7
                look_ahead_schedule.append(goal.weekly_schedule[day_index])

            # Find first occurance of maximum charge limit
            look_ahead_max_charge_limit = -1
            look_ahead_max_charge_limit_index = -1
            for i in range(len(look_ahead_schedule)):
                if look_ahead_schedule[i].charge_limit > look_ahead_max_charge_limit:
                    look_ahead_max_charge_limit = look_ahead_schedule[i].charge_limit
                    look_ahead_max_charge_limit_index = i

            if look_ahead_max_charge_limit_index == 1:
                look_ahead_charge_limit = (
                    look_ahead_max_charge_limit - MIN_CHARGE_LIMIT_DIFF
                )
            else:
                look_ahead_charge_limit = look_ahead_max_charge_limit - (
                    look_ahead_max_charge_limit_index * MAX_CHARGE_LIMIT_DIFF
                )

            if look_ahead_charge_limit > goal.new_charge_limit:
                goal.new_charge_limit = look_ahead_charge_limit

    # ----------------------------------------------------------------------------
    def _get_soc_for_max_charge_speed_calibration(
        self, chargeable: Chargeable
    ) -> float:
        """Check and get SOC required for max charge speed calibration."""

        battery_soc = chargeable.get_state_of_charge()
        if battery_soc is None:
            raise EntityExceptionError(
                f"{self._caller}: Cannot calibrate max charge speed due to missing SOC sensor"
            )
        if battery_soc > CALIBRATE_MAX_SOC:
            raise EntityExceptionError(
                f"{self._caller}: Cannot calibrate max charge speed due to SOC > {CALIBRATE_MAX_SOC} %"
            )

        return battery_soc

    # ----------------------------------------------------------------------------
    async def _async_set_charge_limit_goal_if_calibration(
        self, chargeable: Chargeable, goal: ScheduleData
    ) -> None:
        """Set new charge limit for calibration if required."""

        if self.is_calibrate_max_charge_speed():
            try:
                # Save calibration charge limit only once at start of calibration.
                if not self._started_calibrate_max_charge_speed:
                    battery_soc = self._get_soc_for_max_charge_speed_calibration(
                        chargeable
                    )
                    self._calibrate_max_charge_limit = (
                        battery_soc + CALIBRATE_SOC_INCREASE
                    )

                # Set new charge limit if required
                min_charge_limit = self.get_min_charge_limit()
                if (
                    goal.new_charge_limit < self._calibrate_max_charge_limit
                    and self._calibrate_max_charge_limit >= min_charge_limit
                ):
                    goal.new_charge_limit = self._calibrate_max_charge_limit

            except EntityExceptionError as e:
                _LOGGER.error(
                    "%s: Abort calibrate max charge speed: %s", self._caller, e
                )
                await self._async_turn_off_calibrate_max_charge_speed_switch()

    # ----------------------------------------------------------------------------
    # use_charge_schedule and has_charge_endtime are always set and correct.
    # If use_charge_schedule is true, all other parameters are set.
    # If use_charge_schedule is false, only has_charge_endtime is set. All others are not set.
    #
    # Timer-triggered automation usually need to run at night to meet charge limit at charge end time.
    # Timer-triggered automation will try to reach charge limit at charge end time using solar and/or grid.
    # For charge limit with charge end time, today = 00:00 to sunset, tomorrow = sunset to 00:00.
    # For charge limit without charge end time, today = 00:00 to 23:59.  Reaching charge limit is best effort only and depends on solar.
    async def _async_get_schedule_data(
        self, chargeable: Chargeable, include_tomorrow: bool, log_it: bool = False
    ) -> ScheduleData:
        """Calculate charge schedule data for today or tomorrow if session is started by timer."""

        goal = ScheduleData(weekly_schedule=[])
        # Ensure time is in local timezone
        now_time = self.get_local_datetime()
        goal.data_timestamp = now_time
        goal.old_charge_limit = self._get_charge_limit_or_abort(chargeable)
        goal.new_charge_limit = goal.old_charge_limit

        # Normal schedule
        if self.is_schedule_charge():
            goal.use_charge_schedule = True
            goal.weekly_schedule = self.get_weekly_schedule()

            # 0 = Monday, 6 = Sunday
            today_index = now_time.weekday()
            today_charge_limit = goal.weekly_schedule[today_index].charge_limit
            goal.day_index = today_index
            goal.new_charge_limit = today_charge_limit

            # Get today's schedule
            today_endtime = goal.weekly_schedule[today_index].charge_end_time
            if today_endtime != time.min:
                goal.charge_endtime = self.combine_local_date_time(
                    now_time.date(), today_endtime
                )
                if goal.charge_endtime > now_time:
                    goal.has_charge_endtime = True

            goal.battery_soc = chargeable.get_state_of_charge()

            # If today has no schedule or passed schedule, or if include_tomorrow, then get tomorrow's schedule.
            if not goal.has_charge_endtime:
                tomorrow_index = (today_index + 1) % 7
                tomorrow_charge_limit = goal.weekly_schedule[
                    tomorrow_index
                ].charge_limit
                tomorrow_endtime = goal.weekly_schedule[tomorrow_index].charge_end_time

                # _get_schedule_data() behaves differently when called for normal session, timer session and ending session.
                # Normal session: Started by anything except timer, so include_tomorrow=False.
                # Timer session: Started by timer only, so include_tomorrow=True.
                # Ending session: Called to calculate next trigger time, so include_tomorrow=True
                if (
                    # Use tomorrow's charge limit if time is between end elevation trigger and midnight, or include_tomorrow is true.
                    include_tomorrow
                    # or self._is_sun_between_end_elevation_trigger_and_sunset()
                    # or self.is_time_between_sunset_and_midnight()
                ):
                    if tomorrow_endtime != time.min:
                        # Use tomorrow's goal
                        goal.has_charge_endtime = True
                        goal.day_index = tomorrow_index
                        goal.new_charge_limit = tomorrow_charge_limit
                        goal.charge_endtime = self.combine_local_date_time(
                            now_time.date() + timedelta(days=1),
                            tomorrow_endtime,
                        )

            # Look ahead to reduce charge limit difference between days.
            if self.is_reduce_charge_limit_difference_between_days():
                self._look_ahead_to_reduce_charge_limit_difference(goal)

        # Modify goal charge limit if required calibration.
        await self._async_set_charge_limit_goal_if_calibration(chargeable, goal)

        # Calculate charge start time required to reach charge limit at charge end time.
        self._calc_charge_starttime(goal)

        if log_it:
            _LOGGER.warning("%s: ScheduleData=%s", self._caller, goal)

        return goal

    # ----------------------------------------------------------------------------
    async def _async_wakeup_device(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_WAKE_UP_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_wake_up(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self._async_option_sleep(NUMBER_WAIT_CHARGEE_WAKEUP)

    # ----------------------------------------------------------------------------
    async def _async_poll_charger_update(self, wait_after_update: bool) -> None:
        """Poll charger for update using charger switch entity since every charger must have one."""

        charger_entity = self.option_get_id(OPTION_CHARGER_ON_OFF_SWITCH)
        if charger_entity:
            await self.async_poll_entity_id(charger_entity)
            if wait_after_update:
                await self._async_option_sleep(NUMBER_WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    async def _async_update_ha(
        self, chargeable: Chargeable, wait_after_update: bool = True
    ) -> None:
        """Get third party integration to update HA with latest data."""

        if self.is_poll_charger_update():
            await self._async_poll_charger_update(wait_after_update)
        else:
            config_item = OPTION_CHARGEE_UPDATE_HA_BUTTON
            val_dict = ConfigValueDict(config_item, {})

            await chargeable.async_update_ha(val_dict)
            if val_dict.config_values[config_item].entity_id is not None:
                if wait_after_update:
                    await self._async_option_sleep(NUMBER_WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    def _is_at_location(self, chargeable: Chargeable) -> bool:
        """Is chargeable device at charger location? Always return true if sensor not defined."""

        config_item = OPTION_CHARGEE_LOCATION_SENSOR
        val_dict = ConfigValueDict(config_item, {})

        is_at_location = chargeable.is_at_location(val_dict)
        if val_dict.config_values[config_item].entity_id is None:
            is_at_location = True

        return is_at_location

    # ----------------------------------------------------------------------------
    def is_connected(self, charger: Charger) -> bool:
        """Is charger connected to chargeable device? Always return true if sensor not defined."""

        config_item = OPTION_CHARGER_PLUGGED_IN_SENSOR
        val_dict = ConfigValueDict(config_item, {})

        is_connected = charger.is_connected(val_dict)
        if val_dict.config_values[config_item].entity_id is None:
            is_connected = True

        return is_connected

    # ----------------------------------------------------------------------------
    def _check_if_at_location_or_abort(self, chargeable: Chargeable) -> None:
        is_at_location = self._is_at_location(chargeable)
        if not is_at_location:
            raise RuntimeError(f"{self._caller}: Device not at charger location")

    # ----------------------------------------------------------------------------
    async def _async_init_device(self, chargeable: Chargeable) -> None:
        """Init charge device."""

        #####################################
        # Set up instance variables
        #####################################
        # Must run this first thing to estimate if session started by timer
        self._session_triggered_by_timer = self._is_session_triggered_by_timer()
        self._started_calibrate_max_charge_speed = False

        sun_state = self.get_sun_state_or_abort()
        sun_elevation: float = get_sun_elevation(self._caller, sun_state)
        _LOGGER.warning("%s: Started at sun_elevation=%s", self._caller, sun_elevation)

        await self._async_wakeup_device(chargeable)
        await self._async_update_ha(chargeable)

        self._check_if_at_location_or_abort(chargeable)

        #####################################
        # Set starting goal
        #####################################
        self._starting_goal = await self._async_get_schedule_data(
            chargeable, self._session_triggered_by_timer, log_it=True
        )

    # ----------------------------------------------------------------------------
    async def _async_set_charge_limit(
        self, chargeable: Chargeable, charge_limit: float
    ) -> None:
        """Set charge limit."""

        await chargeable.async_set_charge_limit(charge_limit)
        await self._async_option_sleep(NUMBER_WAIT_CHARGEE_LIMIT_CHANGE)

    # ----------------------------------------------------------------------------
    async def _async_init_charge_limit(
        self, chargeable: Chargeable, goal: ScheduleData
    ) -> bool:
        """Set new charge limit if changed, otherwise use existing charge limit."""

        if charge_limit_changed := (goal.old_charge_limit != goal.new_charge_limit):
            _LOGGER.info(
                "%s: Changing charge limit from %.1f %% to %.1f %% for %s",
                self._caller,
                goal.old_charge_limit,
                goal.new_charge_limit,
                # now_time.strftime("%A"),
                goal.weekly_schedule[goal.day_index].charge_day,
            )
            await self._async_set_charge_limit(chargeable, goal.new_charge_limit)

        return charge_limit_changed

    # ----------------------------------------------------------------------------
    def _is_below_charge_limit(self, chargeable: Chargeable) -> bool:
        """Is device SOC below charge limit? Always return true in case of error."""
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
                        self._caller,
                    )
                else:
                    _LOGGER.info(
                        "SOC %s %% is at or above charge limit %s %%, stopping charger %s",
                        soc,
                        charge_limit,
                        self._caller,
                    )
        except TimeoutError as e:
            _LOGGER.warning(
                "%s: Timeout getting SOC or charge limit: %s", self._caller, e
            )
        except Exception as e:
            _LOGGER.exception("%s: Error getting SOC or charge limit", self._caller)

        return is_below_limit

    # ----------------------------------------------------------------------------
    def _is_charging(self, charger: Charger) -> bool:
        """Is charger currently charging? Always return false in case of error."""

        config_item = OPTION_CHARGER_CHARGING_SENSOR
        val_dict = ConfigValueDict(config_item, {})
        is_charging = charger.is_charging(val_dict=val_dict)

        # If there is no charging sensor defined, then use the next best thing,
        # ie. use charger switch state to determine whether charger is charging or not.
        if val_dict.config_values[config_item].entity_id is None:
            is_charging = charger.is_charger_switch_on()

        return is_charging

    # ----------------------------------------------------------------------------
    def _is_use_secondary_power_source(self) -> bool:
        return self.is_fast_charge_mode()

    # ----------------------------------------------------------------------------
    def _is_not_enough_time_to_complete_charge(
        self,
        chargeable: Chargeable,
        old_charge_current: float,
        charger_max_current: float,
        goal: ScheduleData,
    ) -> bool:
        """Is there not enough time to complete charging before scheduled end time?"""
        is_not_enough_time = False

        if goal.has_charge_endtime:
            now_time = self.get_local_datetime()
            available_charge_duration = goal.charge_endtime - now_time

            battery_soc = chargeable.get_state_of_charge()
            if battery_soc is None:
                return False

            charge_limit = chargeable.get_charge_limit()
            if charge_limit is None:
                return False

            need_charge_duration = self._calculate_need_charge_duration(
                battery_soc, charge_limit
            )

            charger_max_charge_speed = self.option_get_entity_number_or_abort(
                NUMBER_CHARGER_MAX_SPEED
            )
            # Duration in seconds to increase battery level by 1%
            one_percent_charge_duration = timedelta(
                seconds=60 * 60 / charger_max_charge_speed
            )

            # Maximise minimum charge current if charge end time is set and it is night time or
            # there is not enough time to charge, but only before charge end time.
            # chargerMinCurrent might bounce between 0 and chargerMaxCurrent due to
            # battery level not up-to-date or decimal inaccuracy, so stablise it to chargerMaxCurrent
            # if current is already at chargerMaxCurrent and needChargeDuration is only
            # slightly less than availableChargeDuration.
            is_not_enough_time = available_charge_duration.total_seconds() > 0 and (
                not self.is_daytime()
                or need_charge_duration >= available_charge_duration
                or (
                    (need_charge_duration + one_percent_charge_duration)
                    >= available_charge_duration
                    and round(old_charge_current) == round(charger_max_current)
                )
            )

        return is_not_enough_time

    # ----------------------------------------------------------------------------
    async def _async_turn_charger_switch(self, charger: Charger, turn_on: bool) -> None:
        if turn_on:
            switched_on = charger.is_charger_switch_on()
            if not switched_on:
                await charger.async_turn_charger_switch(turn_on)
                await self._async_option_sleep(NUMBER_WAIT_CHARGER_ON)
        else:
            await charger.async_turn_charger_switch(turn_on)
            await self._async_option_sleep(NUMBER_WAIT_CHARGER_OFF)

    # ----------------------------------------------------------------------------
    async def _async_set_charge_current(self, charger: Charger, current: float) -> None:
        """Set charge current."""

        await charger.async_set_charge_current(current)
        self.emit_solarcharger_event(
            self._device.id, EVENT_ACTION_NEW_CHARGE_CURRENT, current
        )
        await self._async_option_sleep(NUMBER_WAIT_CHARGER_AMP_CHANGE)

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
            raise ValueError(f"{self._caller}: Failed to get charger max current")

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
            raise ValueError(f"{self._caller}: Failed to get charge current")
        old_charge_current = self._check_current(
            charger_max_current, battery_charge_current
        )

        #####################################
        # Charge at max current if fast charge
        #####################################
        if self.is_fast_charge_mode() or self.is_calibrate_max_charge_speed():
            new_charge_current = charger_max_current
            return (new_charge_current, old_charge_current)

        #####################################
        # Set minimum charge current
        #####################################
        config_min_current = self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_MIN_CURRENT
        )
        config_min_current = self._check_current(
            charger_max_current, config_min_current
        )

        charger_min_current = config_min_current
        if goal.use_charge_schedule:
            if self._is_not_enough_time_to_complete_charge(
                chargeable,
                old_charge_current,
                charger_max_current,
                goal,
            ):
                charger_min_current = charger_max_current

        #####################################
        # Calculate new current from allocated power
        #####################################
        charger_effective_voltage = self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_EFFECTIVE_VOLTAGE
        )
        if charger_effective_voltage <= 0:
            raise ValueError(
                f"{self._caller}: Invalid charger effective voltage {charger_effective_voltage}"
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

        charger_min_workable_current = self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_MIN_WORKABLE_CURRENT
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
            self._caller,
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
    async def _async_adjust_charge_current(
        self, charger: Charger, chargeable: Chargeable, allocated_power: float
    ) -> None:
        """Adjust charge current."""

        new_charge_current, old_charge_current = self._calc_current_change(
            charger, chargeable, allocated_power, self._running_goal
        )
        if new_charge_current != old_charge_current:
            _LOGGER.info(
                "%s: Update current from %s to %s",
                self._caller,
                old_charge_current,
                new_charge_current,
            )
            await self._async_set_charge_current(charger, new_charge_current)
            self._charge_current_updatetime = utcnow().timestamp()

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
                new_state.last_changed_timestamp - self._charge_current_updatetime
            )

            if old_state is not None:
                _LOGGER.debug(
                    "%s: entity_id=%s, old_state=%s, new_state=%s, duration_since_last_change=%s",
                    self._caller,
                    entity_id,
                    old_state.state,
                    new_state.state,
                    duration_since_last_change,
                )
            else:
                _LOGGER.debug(
                    "%s: entity_id=%s, new_state=%s, duration_since_last_change=%s",
                    self._caller,
                    entity_id,
                    new_state.state,
                    duration_since_last_change,
                )

            # Make sure we don't change the charge current too often
            if duration_since_last_change >= MIN_TIME_BETWEEN_UPDATE:
                await self._async_adjust_charge_current(
                    self._charger, self._chargeable, float(new_state.state)
                )

    # ----------------------------------------------------------------------------
    def _is_continue_charge(
        self,
        charger: Charger,
        chargeable: Chargeable,
        loop_count: int,
        goal: ScheduleData,
    ) -> bool:
        """Check if to continue charging."""

        is_connected = self.is_connected(charger)
        is_below_charge_limit = self._is_below_charge_limit(chargeable)
        is_charging = self._is_charging(charger)
        (is_sun_above_start_end_elevations, elevation) = (
            self.is_sun_above_start_end_elevation_triggers()
        )
        is_use_secondary_power_source = self._is_use_secondary_power_source()
        is_calibrate_max_charge_speed = self.is_calibrate_max_charge_speed()

        # Add 30 minutes grace period to avoid time drift stopping charge
        # and scheduling next session immediately.
        current_time_with_grace = goal.data_timestamp + timedelta(minutes=30)
        if goal.has_charge_endtime and goal.propose_charge_starttime != datetime.min:
            is_immediate_start_with_grace = (
                goal.propose_charge_starttime <= current_time_with_grace
            )
        else:
            is_immediate_start_with_grace = False

        continue_charge = (
            is_connected
            and (is_below_charge_limit or is_calibrate_max_charge_speed)
            and (loop_count == 0 or is_charging)
            and (
                is_sun_above_start_end_elevations
                or is_use_secondary_power_source
                or is_calibrate_max_charge_speed
                or (goal.has_charge_endtime and is_immediate_start_with_grace)
            )
        )

        if not continue_charge:
            _LOGGER.warning(
                "%s: Stopping charge: is_connected=%s, "
                "is_below_charge_limit=%s, loop_count=%s, is_charging=%s, "
                "is_sun_above_start_end_elevations=%s, elevation=%s, is_use_secondary_power_source=%s, "
                "is_calibrate_max_charge_speed=%s, has_charge_endtime=%s, is_immediate_start=%s, "
                "propose_charge_starttime=%s, current_time_with_grace=%s, is_immediate_start_with_grace=%s",
                self._caller,
                is_connected,
                is_below_charge_limit,
                loop_count,
                is_charging,
                is_sun_above_start_end_elevations,
                elevation,
                is_use_secondary_power_source,
                is_calibrate_max_charge_speed,
                goal.has_charge_endtime,
                goal.is_immediate_start,
                goal.propose_charge_starttime,
                current_time_with_grace,
                is_immediate_start_with_grace,
            )

        return continue_charge

    # ----------------------------------------------------------------------------
    def _log_charging_status(self, charger: Charger, msg: str) -> None:
        """Generate debug message only if required."""

        _LOGGER.warning(
            "%s: %s: is_connected=%s, is_charger_switch_on=%s, is_charging=%s",
            self._caller,
            msg,
            self.is_connected(charger),
            charger.is_charger_switch_on(),
            self._is_charging(charger),
        )

    # ----------------------------------------------------------------------------
    async def _async_check_if_calibration(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Check if calibration is required during charge."""

        if self.is_calibrate_max_charge_speed():
            if not self._started_calibrate_max_charge_speed:
                # Track SOC
                self._soc_updates = []
                if self._tracker.track_soc_sensor(self.async_handle_soc_update):
                    charger_max_current = self._get_charger_max_current(charger)
                    await self._async_set_charge_current(charger, charger_max_current)
                    self._started_calibrate_max_charge_speed = True

    # ----------------------------------------------------------------------------
    async def _async_charge_device(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        loop_count = 0

        wait_net_power_update = self.config_get_number_or_abort(
            CONF_WAIT_NET_POWER_UPDATE
        )

        while self._is_continue_charge(
            charger,
            chargeable,
            loop_count,
            goal := await self._async_get_schedule_data(
                chargeable, self._session_triggered_by_timer
            ),
        ):
            try:
                # Check schedule change and update charge limit if required
                self._running_goal = goal
                if await self._async_init_charge_limit(chargeable, self._running_goal):
                    _LOGGER.warning(
                        "%s: ScheduleData=%s", self._caller, self._running_goal
                    )

                # Turn on charger if looping for the first time
                if loop_count == 0:
                    await self._async_turn_charger_switch(charger, turn_on=True)
                    await self._async_set_charge_current(
                        charger, INITIAL_CHARGE_CURRENT
                    )
                    self._subscribe_allocated_power_update()

                    self._log_charging_status(charger, "Before update")
                    await self._async_update_ha(chargeable)
                    self._log_charging_status(charger, "After update")

                # Check if calibration is required during charge
                await self._async_check_if_calibration(charger, chargeable)

                # Update status after turning on power, or at every interval.
                # This is either required here or after setting current.
                # It is better here since it is garanteed periodic.
                # Do not wait here. Depends on the main loop to wait.
                await self._async_update_ha(chargeable, wait_after_update=False)

            except TimeoutError as e:
                _LOGGER.warning("%s: Timeout charging device: %s", self._caller, e)
            except Exception as e:
                _LOGGER.exception("%s: Error charging device", self._caller)

            # Sleep before re-evaluating charging conditions.
            # Charging state must be "charging" for loop_count > 0.
            # Tesla BLE need 25 seconds here, ie. OPTION_WAIT_CHARGEE_UPDATE_HA = 25 seconds
            await asyncio.sleep(wait_net_power_update)
            loop_count = loop_count + 1

        await self.async_unload()

    # ----------------------------------------------------------------------------
    def _calculate_need_charge_duration(
        self, battery_soc: float, charge_limit: float
    ) -> timedelta:
        """Calculate needed charge duration to reach charge limit."""

        charger_max_charge_speed = self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_MAX_SPEED
        )
        # Duration in seconds to increase battery level by 1%
        one_percent_charge_duration = 60 * 60 / charger_max_charge_speed

        # SOC can be incorrect by 6% (approx. 1 hour) if required to charge to 100%
        extra_seconds = 0
        if charge_limit >= 100:
            extra_seconds = 6 * one_percent_charge_duration

        # Sometimes charge can decrease by 1% during charging at the beginning, so add extra onePercentChargeDuration for good measure.
        need_charge_seconds = (
            (charge_limit - battery_soc) * one_percent_charge_duration
            + one_percent_charge_duration
            + extra_seconds
        )

        _LOGGER.info(
            "%s: charge_limit=%.1f %%, "
            "battery_soc=%.1f %%, "
            "charger_max_charge_speed=%.1f %%/hr, "
            "one_percent_charge_duration=%.2f sec, ",
            self._caller,
            charge_limit,
            battery_soc,
            charger_max_charge_speed,
            one_percent_charge_duration,
        )

        return timedelta(seconds=need_charge_seconds)

    # ----------------------------------------------------------------------------
    async def _async_set_next_charge_time(self, next_charge_time: datetime) -> None:
        """Set next charge time."""

        # Note: Cannot set next_charge_time = datetime.min
        await self.async_set_datetime(
            self._next_charge_time_trigger,
            next_charge_time,
        )

    # ----------------------------------------------------------------------------
    async def _async_clear_next_charge_time(self) -> None:
        """Clear next charge time trigger."""

        await self._async_set_next_charge_time(self._history_date)

    # ----------------------------------------------------------------------------
    # This is an estimated time only and could have unexpected results for edge cases.
    def _get_next_start_elevation_trigger_time(self) -> datetime:
        """Get next start elevation trigger time."""

        sun_state = self.get_sun_state_or_abort()
        sec_per_degree_sunrise: float = get_sec_per_degree_sun_elevation(
            self._caller, sun_state
        )
        elevation_start_trigger = self.option_get_entity_number_or_abort(
            NUMBER_SUNRISE_ELEVATION_START_TRIGGER
        )
        sunrise_offset = timedelta(
            seconds=(
                elevation_start_trigger + CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE
            )
            * sec_per_degree_sunrise
        )

        now_time = self.get_local_datetime()
        next_sunrise = get_next_sunrise_time(self._caller, sun_state)

        # Get today sunrise time
        next_start_elevation_trigger_time = (
            self.combine_local_date_time(
                now_time.date(),
                next_sunrise.time(),
            )
            + sunrise_offset
        )

        # Check if today start elevation trigger time has passed
        if now_time > next_start_elevation_trigger_time:
            next_start_elevation_trigger_time = next_sunrise + sunrise_offset

        return next_start_elevation_trigger_time

    # ----------------------------------------------------------------------------
    async def _async_schedule_next_charge_session(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Schedule next charge session."""

        next_goal = await self._async_get_schedule_data(
            chargeable, include_tomorrow=True, log_it=True
        )
        if next_goal.use_charge_schedule:
            await self._async_clear_next_charge_time()

            # Only schedule next charge session if car is connected and at location.
            if self.is_connected(charger) and self._is_at_location(chargeable):
                if next_goal.has_charge_endtime:
                    if next_goal.propose_charge_starttime != datetime.min:
                        if next_goal.is_immediate_start:
                            now_time = self.get_local_datetime()
                            next_starttime = now_time + timedelta(minutes=2)
                        else:
                            next_starttime = next_goal.propose_charge_starttime

                        next_start_elevation_trigger_time = (
                            self._get_next_start_elevation_trigger_time()
                        )

                        set_next_charge_time = (
                            next_starttime < next_start_elevation_trigger_time
                            or not self.is_sun_trigger()
                        )
                        if set_next_charge_time:
                            await self._async_set_next_charge_time(next_starttime)

                        _LOGGER.warning(
                            "%s: set_next_charge_time=%s, next_starttime=%s, next_start_elevation_trigger_time=%s",
                            self._caller,
                            set_next_charge_time,
                            next_starttime,
                            next_start_elevation_trigger_time,
                        )

    # ----------------------------------------------------------------------------
    async def async_tidy_up_on_exit(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Tidy up on exit."""

        await self.async_unload()

        await self._async_update_ha(chargeable)

        switched_on = charger.is_charger_switch_on()
        if switched_on:
            await self._async_set_charge_current(charger, 0)
            await self._async_turn_charger_switch(charger, turn_on=False)

        sun_state = self.get_sun_state_or_abort()
        sun_elevation: float = get_sun_elevation(self._caller, sun_state)
        _LOGGER.warning("%s: Stopped at sun_elevation=%s", self._caller, sun_elevation)

        await self._async_turn_off_calibrate_max_charge_speed_switch()
        await self._async_schedule_next_charge_session(charger, chargeable)

    # ----------------------------------------------------------------------------
    async def async_start_charge_task(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Async task to start the charging process."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # chargeable: Chargeable | None = self.get_chargee

        #####################################
        # Start charge session
        #####################################
        try:
            await self._async_init_device(chargeable)
            await self._async_init_charge_limit(chargeable, self._starting_goal)
            await self._async_charge_device(charger, chargeable)
            await self.async_tidy_up_on_exit(charger, chargeable)

        except Exception as e:
            _LOGGER.exception("%s: Abort charge", self._caller)
            await self.async_tidy_up_on_exit(charger, chargeable)

            # To show exception location, eg.
            # 2026-02-05 04:27:43.054 ERROR (MainThread) [custom_components.solarcharger.chargers.controller] ocpp_charger: Abort charge
            # Traceback (most recent call last):
            #   File "/workspaces/core/config/custom_components/solarcharger/chargers/controller.py", line 1623, in _async_start_charge_task
            #     await self._async_charge_device(charger, chargeable)
            #   File "/workspaces/core/config/custom_components/solarcharger/chargers/controller.py", line 1402, in _async_charge_device
            #     while self._is_continue_charge(
            #           ~~~~~~~~~~~~~~~~~~~~~~~~^
            #         charger,
            #         ^^^^^^^^
            #     ...<4 lines>...
            #         ),
            #         ^^
            #     ):
            #     ^
            #   File "/workspaces/core/config/custom_components/solarcharger/chargers/controller.py", line 1322, in _is_continue_charge
            #     goal.propose_charge_starttime <= current_time_with_grace
            # TypeError: can't compare offset-naive and offset-aware datetimes
