"""Module to manage the charging process."""

import asyncio
from asyncio import Task, timeout
from datetime import date, datetime, time, timedelta
import inspect
import logging

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers import device_registry as dr

# Might be of help in the future.
# from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.util.dt import as_local, utcnow

from ..const import (  # noqa: TID252
    CALLBACK_ALLOCATE_POWER,
    CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE,
    DATETIME,
    DATETIME_NEXT_CHARGE_TIME,
    DOMAIN,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_EFFECTIVE_VOLTAGE,
    OPTION_CHARGER_MAX_SPEED,
    OPTION_CHARGER_MIN_CURRENT,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER,
    OPTION_SUNSET_ELEVATION_END_TRIGGER,
    OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
    OPTION_WAIT_CHARGEE_UPDATE_HA,
    OPTION_WAIT_CHARGEE_WAKEUP,
    OPTION_WAIT_CHARGER_AMP_CHANGE,
    OPTION_WAIT_CHARGER_OFF,
    OPTION_WAIT_CHARGER_ON,
    SWITCH,
    SWITCH_FAST_CHARGE_MODE,
    SWITCH_SCHEDULE_CHARGE,
    SWITCH_START_CHARGE,
)
from ..entity import compose_entity_id  # noqa: TID252
from ..model_config import ConfigValueDict  # noqa: TID252
from ..sc_option_state import ScheduleData, ScOptionState  # noqa: TID252
from ..utils import (  # noqa: TID252
    get_is_sun_rising,
    get_next_sunrise_time,
    get_sec_per_degree_sun_elevation,
    get_sun_attribute_or_abort,
    get_sun_elevation,
    log_is_event_loop,
)
from .chargeable import Chargeable
from .charger import Charger
from .tracker import Tracker

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

INITIAL_CHARGE_CURRENT = 6  # Initial charge current in Amps
MIN_TIME_BETWEEN_UPDATE = 10  # Minimum seconds between charger current updates
ENVIRONMENT_CHECK_INTERVAL = 60  # Seconds to sleep between environment checks


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ChargeController(ScOptionState):
    """Class to manage the charging process."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        charger: Charger,
        chargeable: Chargeable,
    ) -> None:
        """Initialize the Charge instance."""

        caller = subentry.unique_id
        if caller is None:
            caller = __name__
        ScOptionState.__init__(self, hass, entry, subentry, caller)

        self._charger = charger
        self._chargeable = chargeable
        self._charge_task: Task | None = None
        self._end_charge_task: Task | None = None
        self._charge_current_updatetime: float = 0

        # Fixed control entities (local device entities only)
        self._charger_switch_entity_id = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_START_CHARGE
        )
        self._fast_charge_switch_entity_id = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_FAST_CHARGE_MODE
        )
        self._schedule_charge_switch_entity_id = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_SCHEDULE_CHARGE
        )
        self._next_charge_time_trigger_entity_id = compose_entity_id(
            DATETIME, subentry.unique_id, DATETIME_NEXT_CHARGE_TIME
        )

        self._tracker: Tracker = Tracker(hass, entry, subentry, caller)

        self._session_triggered_by_timer = False
        self._goal: ScheduleData = ScheduleData([])

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

    # ----------------------------------------------------------------------------
    # Charger utils
    # ----------------------------------------------------------------------------
    def _is_fast_charge(self) -> bool:
        state = self.get_string(self._fast_charge_switch_entity_id)
        return state == STATE_ON

    # ----------------------------------------------------------------------------
    def _is_schedule_charge(self) -> bool:
        state = self.get_string(self._schedule_charge_switch_entity_id)
        return state == STATE_ON

    # ----------------------------------------------------------------------------
    def _turn_on_charger_switch(self) -> None:
        """Create a task to turn on the charger switch."""

        # async_track_sunrise() does not directly support coroutine callback, so create coroutine in event loop.
        # self._hass.loop.create_task(self.async_start_charge())
        self._hass.loop.create_task(
            self.async_turn_switch_on(self._charger_switch_entity_id)
        )

    # ----------------------------------------------------------------------------
    # Called by next charge time trigger only
    async def _async_turn_on_charger_switch(self, now: datetime) -> None:
        """Start charger from coroutine callback."""

        # async_call_later do support coroutine callback, so can call directly.
        await self.async_turn_switch_on(self._charger_switch_entity_id)

    # ----------------------------------------------------------------------------
    # Tracker callbacks
    # ----------------------------------------------------------------------------
    async def _async_handle_sun_elevation_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_sun_state: State | None = data["old_state"]
        new_sun_state: State | None = data["new_state"]

        self._tracker.log_state_change(event)

        if new_sun_state is not None:
            if old_sun_state is not None:
                # new_state.state can equal old_state.state, ie. below_horizon or above_horizon
                if new_sun_state.state not in (
                    STATE_UNKNOWN,
                    STATE_UNAVAILABLE,
                ) and old_sun_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    elevation_start_trigger = self.option_get_entity_number_or_abort(
                        OPTION_SUNRISE_ELEVATION_START_TRIGGER
                    )

                    is_sun_rising: bool = get_is_sun_rising(self._caller, old_sun_state)
                    old_elevation: float = get_sun_elevation(
                        self._caller, old_sun_state
                    )
                    new_elevation: float = get_sun_elevation(
                        self._caller, new_sun_state
                    )

                    _LOGGER.debug(
                        "%s: is_sun_rising=%s, old_elevation=%s, new_elevation=%s",
                        self._caller,
                        is_sun_rising,
                        old_elevation,
                        new_elevation,
                    )

                    if (
                        is_sun_rising
                        and elevation_start_trigger > old_elevation
                        and elevation_start_trigger <= new_elevation
                    ):
                        # Start charger
                        await self.async_turn_switch_on(self._charger_switch_entity_id)

    # ----------------------------------------------------------------------------
    async def _async_handle_plug_in_charger_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        self._tracker.log_state_change(event)

        # Not sure why on startup, getting a lot of updates here with old_state=None causing crash.
        # if new_state is not None:
        #     if old_state is not None:
        #         if new_state.state == old_state.state:
        #             return
        #         # Only process updates with both old and new states
        #         if self._charger.is_connected():
        #             self._turn_on_charger_switch()

        # Not sure why on startup, getting a lot of updates here with old_state=None causing crash.
        if new_state is not None:
            if old_state is not None:
                if (
                    new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                    and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                    and new_state.state != old_state.state
                ):
                    if self._charger.is_connected():
                        self._turn_on_charger_switch()

    # ----------------------------------------------------------------------------
    async def _async_handle_next_charge_time_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        self._tracker.log_state_change(event)

        if new_state is not None and old_state is not None:
            if new_state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ) and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                new_starttime = self.parse_local_datetime(new_state.state)

                self._tracker.schedule_next_charge_time(
                    new_starttime, self._async_turn_on_charger_switch
                )

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Async setup of the ChargeController."""
        await self._charger.async_setup()
        await self._tracker.async_setup()

        # Track charger plug in
        self._tracker.track_charger_plugged_in_sensor(
            self._async_handle_plug_in_charger_event
        )

        # Track sun elevation
        # self._set_up_sun_triggers()
        # self._track_sunrise_elevation_trigger()
        self._tracker.track_sun_elevation(self._async_handle_sun_elevation_update)

        # Track next charge time trigger
        self._tracker.track_next_charge_time_trigger(
            self._next_charge_time_trigger_entity_id,
            self._async_handle_next_charge_time_update,
        )
        # Trigger is lost on restart, so reschedule if applicable.
        next_charge_time = self.get_datetime(self._next_charge_time_trigger_entity_id)
        if next_charge_time is not None:
            self._tracker.schedule_next_charge_time(
                next_charge_time, self._async_turn_on_charger_switch
            )

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of the ChargeController."""
        await self._tracker.async_unload()
        await self._charger.async_unload()

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
        next_charge_time = self.get_datetime(self._next_charge_time_trigger_entity_id)
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
    # use_charge_schedule and has_charge_endtime are always set and correct.
    # If use_charge_schedule is true, all other parameters are set.
    # If use_charge_schedule is false, only has_charge_endtime is set. All others are not set.
    #
    # Timer-triggered automation usually need to run at night to meet charge limit at charge end time.
    # Timer-triggered automation will try to reach charge limit at charge end time using solar and/or grid.
    # For charge limit with charge end time, today = 00:00 to sunset, tomorrow = sunset to 00:00.
    # For charge limit without charge end time, today = 00:00 to 23:59.  Reaching charge limit is best effort only and depends on solar.
    def _get_schedule_data(
        self, triggered_by_timer: bool, chargeable: Chargeable
    ) -> ScheduleData:
        """Calculate charge schedule data for today or tomorrow if session is started by timer."""

        sd = ScheduleData(weekly_schedule=[])

        if self._is_schedule_charge():
            sd.use_charge_schedule = True
            sd.weekly_schedule = self.get_weekly_schedule()

            # Ensure time is in local timezone
            now_time = self.get_local_datetime()
            sd.session_starttime = now_time

            # 0 = Monday, 6 = Sunday
            today_index = now_time.weekday()
            sd.day_index = today_index
            sd.charge_limit = sd.weekly_schedule[today_index].charge_limit
            today_endtime = sd.weekly_schedule[today_index].charge_end_time

            if today_endtime != time.min:
                sd.has_charge_endtime = True
                sd.charge_endtime = self.combine_local_date_time(
                    now_time.date(), today_endtime
                )

            # Required if session is started by next_charge_time trigger or to calc next trigger
            if triggered_by_timer:
                battery_soc = chargeable.get_state_of_charge()
                if (
                    sd.has_charge_endtime
                    and sd.charge_endtime > now_time
                    and battery_soc is not None
                    and battery_soc < sd.charge_limit
                ):
                    # Use today's goal
                    pass
                else:
                    tomorrow_index = (today_index + 1) % 7
                    tomorrow_endtime = sd.weekly_schedule[
                        tomorrow_index
                    ].charge_end_time
                    if tomorrow_endtime != time.min:
                        # Use tomorrow's goal
                        sd.has_charge_endtime = True
                        sd.day_index = tomorrow_index
                        sd.charge_limit = sd.weekly_schedule[
                            tomorrow_index
                        ].charge_limit
                        sd.charge_endtime = self.combine_local_date_time(
                            now_time.date() + timedelta(days=1),
                            tomorrow_endtime,
                        )

        _LOGGER.warning("%s: ScheduleData=%s", self._caller, sd)
        return sd

    # ----------------------------------------------------------------------------
    async def _async_wakeup_device(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_WAKE_UP_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_wake_up(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self._async_option_sleep(OPTION_WAIT_CHARGEE_WAKEUP)

    # ----------------------------------------------------------------------------
    async def _async_update_ha(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_UPDATE_HA_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_update_ha(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self._async_option_sleep(OPTION_WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    def _check_is_at_location(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_LOCATION_SENSOR
        val_dict = ConfigValueDict(config_item, {})

        is_at_location = chargeable.is_at_location(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            if not is_at_location:
                raise RuntimeError(f"{self._caller}: Device not at charger location")

    # ----------------------------------------------------------------------------
    async def _async_init_device(self, chargeable: Chargeable) -> None:
        """Init charge device."""

        sun_state = self.get_sun_state_or_abort()
        sun_elevation: float = get_sun_elevation(self._caller, sun_state)
        _LOGGER.warning("%s: Started at sun_elevation=%s", self._caller, sun_elevation)

        await self._async_wakeup_device(chargeable)
        await self._async_update_ha(chargeable)
        self._check_is_at_location(chargeable)

    # ----------------------------------------------------------------------------
    async def _async_init_charge_limit(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Initialize charge limit if charge schedule is enabled, otherwise use existing charge limit."""

        if self._goal.use_charge_schedule:
            _LOGGER.info(
                "%s: Setting charge limit to %.1f %% for %s",
                self._caller,
                self._goal.charge_limit,
                # now_time.strftime("%A"),
                self._goal.weekly_schedule[self._goal.day_index].charge_day,
            )
            await chargeable.async_set_charge_limit(self._goal.charge_limit)
            await self._async_option_sleep(OPTION_WAIT_CHARGEE_LIMIT_CHANGE)

    # ----------------------------------------------------------------------------
    def _is_abort_charge(self) -> bool:
        return False

    # ----------------------------------------------------------------------------
    def _is_below_charge_limit(self, chargeable: Chargeable) -> bool:
        """Is device SOC below charge limit?"""
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
        except TimeoutError:
            _LOGGER.warning("Timeout while communicating with charger %s", self._caller)
        except Exception as e:
            _LOGGER.error("Error in charging task for charger %s: %s", self._caller, e)

        return is_below_limit

    # ----------------------------------------------------------------------------
    def _is_sun_above_start_end_elevations(self) -> tuple[bool, float]:
        sun_above_start_end_elevations = False

        sun_state: State = self.get_sun_state_or_abort()
        sunrise_elevation_start_trigger: float = self.option_get_entity_number_or_abort(
            OPTION_SUNRISE_ELEVATION_START_TRIGGER
        )
        sunset_elevation_end_trigger: float = self.option_get_entity_number_or_abort(
            OPTION_SUNSET_ELEVATION_END_TRIGGER
        )
        sun_elevation: float = get_sun_attribute_or_abort(
            self._caller, sun_state, "elevation"
        )
        sun_is_rising: bool = get_sun_attribute_or_abort(
            self._caller, sun_state, "rising"
        )

        if (sun_is_rising and sun_elevation >= sunrise_elevation_start_trigger) or (
            not sun_is_rising and sun_elevation > sunset_elevation_end_trigger
        ):
            sun_above_start_end_elevations = True

        return (sun_above_start_end_elevations, sun_elevation)

    # ----------------------------------------------------------------------------
    def _is_use_secondary_power_source(self) -> bool:
        return self._is_fast_charge()

    # ----------------------------------------------------------------------------
    def _is_not_enough_time(
        self,
        chargeable: Chargeable,
        old_charge_current: float,
        charger_max_current: float,
        sd: ScheduleData,
    ) -> bool:
        """Is there not enough time to complete charging before scheduled end time?"""
        is_not_enough_time = False

        if sd.has_charge_endtime:
            now_time = self.get_local_datetime()
            available_charge_duration = sd.charge_endtime - now_time

            battery_soc = chargeable.get_state_of_charge()
            if battery_soc is None:
                return False

            charge_limit = chargeable.get_charge_limit()
            if charge_limit is None:
                return False

            need_charge_duration = self._calculate_need_charge_duration(
                battery_soc, charge_limit
            )

            battery_max_charge_speed = self.option_get_entity_number_or_abort(
                OPTION_CHARGER_MAX_SPEED
            )
            # Duration in seconds to increase battery level by 1%
            one_percent_charge_duration = timedelta(
                seconds=60 * 60 / battery_max_charge_speed
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
    async def _async_turn_charger_switch_on(self, charger: Charger) -> None:
        switched_on = charger.is_charger_switch_on()
        if not switched_on:
            await charger.async_turn_charger_switch_on()
            await self._async_option_sleep(OPTION_WAIT_CHARGER_ON)

    # ----------------------------------------------------------------------------
    async def _async_turn_charger_switch_off(self, charger: Charger) -> None:
        await charger.async_turn_charger_switch_off()
        await self._async_option_sleep(OPTION_WAIT_CHARGER_OFF)

    # ----------------------------------------------------------------------------
    async def _async_set_charge_current(self, charger: Charger, current: float) -> None:
        await charger.async_set_charge_current(current)
        await self._async_option_sleep(OPTION_WAIT_CHARGER_AMP_CHANGE)

    # ----------------------------------------------------------------------------
    def _check_current(self, max_current: float, current: float) -> float:
        if current < 0:
            current = 0
        elif current > max_current:
            current = max_current

        return current

    # ----------------------------------------------------------------------------
    def _calc_current_change(
        self, charger: Charger, chargeable: Chargeable, allocated_power: float
    ) -> tuple[float, float]:
        """Calculate new charge current based on allocated power."""

        charger_max_current = charger.get_max_charge_current()
        if charger_max_current is None or charger_max_current <= 0:
            raise ValueError(f"{self._caller}: Failed to get charger max current")

        battery_charge_current = charger.get_charge_current()
        if battery_charge_current is None:
            raise ValueError(f"{self._caller}: Failed to get charge current")
        old_charge_current = self._check_current(
            charger_max_current, battery_charge_current
        )

        #####################################
        # Charge at max current if fast charge
        #####################################
        if self._is_fast_charge():
            new_charge_current = charger_max_current
            return (new_charge_current, old_charge_current)

        #####################################
        # Set minimum charge current
        #####################################
        config_min_current = self.option_get_entity_number_or_abort(
            OPTION_CHARGER_MIN_CURRENT
        )
        config_min_current = self._check_current(
            charger_max_current, config_min_current
        )

        charger_min_current = config_min_current
        if self._goal.use_charge_schedule:
            if self._is_not_enough_time(
                chargeable,
                old_charge_current,
                charger_max_current,
                self._goal,
            ):
                charger_min_current = charger_max_current

        #####################################
        # Calculate new current from allocated power
        #####################################
        charger_effective_voltage = self.option_get_entity_number_or_abort(
            OPTION_CHARGER_EFFECTIVE_VOLTAGE
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
            OPTION_CHARGER_MIN_WORKABLE_CURRENT
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
        new_charge_current, old_charge_current = self._calc_current_change(
            charger, chargeable, allocated_power
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
            self.emit_solarcharger_event(
                self._device.id, EVENT_ACTION_NEW_CHARGE_CURRENT, new_charge_current
            )
            await self._async_update_ha(chargeable)

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
    ) -> bool:
        """Check if to continue charging."""

        is_abort_charge = self._is_abort_charge()
        is_connected = charger.is_connected()
        is_below_charge_limit = self._is_below_charge_limit(chargeable)
        is_charging = charger.is_charging()
        (is_sun_above_start_end_elevations, elevation) = (
            self._is_sun_above_start_end_elevations()
        )
        is_use_secondary_power_source = self._is_use_secondary_power_source()
        now_time = self.get_local_datetime()

        continue_charge = (
            not is_abort_charge
            and is_connected
            and is_below_charge_limit
            and (loop_count == 0 or is_charging)
            and (
                is_sun_above_start_end_elevations
                or is_use_secondary_power_source
                or (
                    self._goal.has_charge_endtime
                    and self._goal.charge_endtime > now_time
                )
            )
        )

        if not continue_charge:
            _LOGGER.warning(
                "%s: Stopping charge: is_abort_charge=%s, is_connected=%s, "
                "is_below_charge_limit=%s, loop_count=%s, is_charging=%s, "
                "is_sun_above_start_end_elevations=%s, elevation=%s, is_use_secondary_power_source=%s, "
                "has_charge_endtime=%s",
                self._caller,
                is_abort_charge,
                is_connected,
                is_below_charge_limit,
                loop_count,
                is_charging,
                is_sun_above_start_end_elevations,
                elevation,
                is_use_secondary_power_source,
                self._goal.has_charge_endtime,
            )

        return continue_charge

    # ----------------------------------------------------------------------------
    async def _async_charge_device(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        loop_count = 0

        while self._is_continue_charge(charger, chargeable, loop_count):
            try:
                # Turn on charger if looping for the first time
                if loop_count == 0:
                    await self._async_turn_charger_switch_on(charger)
                    await self._async_set_charge_current(
                        charger, INITIAL_CHARGE_CURRENT
                    )
                    await self._async_update_ha(chargeable)
                    self._tracker.track_allocated_power_update(
                        CALLBACK_ALLOCATE_POWER,
                        self._async_handle_allocated_power_update,
                    )

            except TimeoutError:
                _LOGGER.warning(
                    "Timeout while communicating with charger %s", self._caller
                )
            except Exception as e:
                _LOGGER.error(
                    "Error in charge task for charger %s: %s", self._caller, e
                )

            # Sleep before re-evaluating charging conditions.
            # Charging state must be "charging" for loop_count > 0.
            # Tesla BLE need 25 seconds here, ie. OPTION_WAIT_CHARGEE_UPDATE_HA = 25 seconds
            await asyncio.sleep(ENVIRONMENT_CHECK_INTERVAL)
            loop_count = loop_count + 1

        self._tracker.remove_callback(CALLBACK_ALLOCATE_POWER)

    # ----------------------------------------------------------------------------
    def _calculate_need_charge_duration(
        self, battery_soc: float, charge_limit: float
    ) -> timedelta:
        """Calculate needed charge duration to reach charge limit."""

        battery_max_charge_speed = self.option_get_entity_number_or_abort(
            OPTION_CHARGER_MAX_SPEED
        )
        # Duration in seconds to increase battery level by 1%
        one_percent_charge_duration = 60 * 60 / battery_max_charge_speed

        # Give extra 1 hour if required to charge to 100%
        extra_seconds = 0
        if charge_limit >= 100:
            extra_seconds = 60 * 60

        # Sometimes charge can decrease by 1% during charging at the beginning, so add extra onePercentChargeDuration for good measure.
        need_charge_seconds = (
            (charge_limit - battery_soc) * one_percent_charge_duration
            + one_percent_charge_duration
            + extra_seconds
        )

        _LOGGER.info(
            "%s: charge_limit=%.1f %%, "
            "battery_soc=%.1f %%, "
            "battery_max_charge_speed=%.1f %%/hr, "
            "one_percent_charge_duration=%.2f sec, ",
            self._caller,
            charge_limit,
            battery_soc,
            battery_max_charge_speed,
            one_percent_charge_duration,
        )

        return timedelta(seconds=need_charge_seconds)

    # ----------------------------------------------------------------------------
    async def _async_set_next_charge_time(self, next_charge_time: datetime) -> None:
        """Set next charge time."""

        # Note: Cannot set next_charge_time = datetime.min
        await self.async_set_datetime(
            self._next_charge_time_trigger_entity_id,
            next_charge_time,
        )

    # ----------------------------------------------------------------------------
    async def _async_schedule_next_charge_session(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Schedule next charge session."""

        # Clear next charge time trigger
        await self._async_set_next_charge_time(datetime(2025, 1, 1, 0, 0, 0))

        if self._is_schedule_charge():
            battery_soc = chargeable.get_state_of_charge()
            if battery_soc is None:
                _LOGGER.info(
                    "%s: Unable to get battery SOC, cannot schedule next charge session",
                    self._caller,
                )
                return
                # For testing only
                # battery_soc = 0.0

            weekly_schedule = self.get_weekly_schedule()

            # Ensure time is in local timezone
            now_time = self.get_local_datetime()
            today_index = now_time.weekday()
            tomorrow_index = (today_index + 1) % 7
            tomorrow_charge_limit = weekly_schedule[tomorrow_index].charge_limit
            charge_end_time = weekly_schedule[tomorrow_index].charge_end_time

            if charge_end_time != time.min:
                tomorrow_charge_endtime = self.combine_local_date_time(
                    now_time.date() + timedelta(days=1), charge_end_time
                )

                if battery_soc >= tomorrow_charge_limit:
                    _LOGGER.info(
                        "%s: Battery SOC %.1f %% is at or above tomorrow's charge limit %.1f %%, no need to schedule next charge session",
                        self._caller,
                        battery_soc,
                        tomorrow_charge_limit,
                    )
                    return

                sun_state = self.get_sun_state_or_abort()
                sec_per_degree_sunrise: float = get_sec_per_degree_sun_elevation(
                    self._caller, sun_state
                )
                elevation_start_trigger = self.option_get_entity_number_or_abort(
                    OPTION_SUNRISE_ELEVATION_START_TRIGGER
                )
                sunrise_offset = timedelta(
                    seconds=(
                        elevation_start_trigger
                        + CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE
                    )
                    * sec_per_degree_sunrise
                )
                next_sunrise = get_next_sunrise_time(self._caller, sun_state)

                tomorrow_charge_starttime = (
                    self.combine_local_date_time(
                        now_time.date() + timedelta(days=1),
                        next_sunrise.time(),
                    )
                    + sunrise_offset
                )
                tomorrow_available_charge_duration = (
                    tomorrow_charge_endtime - tomorrow_charge_starttime
                )

                tomorrow_need_charge_duration = self._calculate_need_charge_duration(
                    battery_soc, tomorrow_charge_limit
                )

                _LOGGER.warning(
                    "%s: tomorrow_charge_endtime=%s, "
                    "sec_per_degree_sunrise=%.2f sec, "
                    "elevation_start_trigger=%.2f, "
                    "sunrise_offset=%s, "
                    "next_sunrise=%s, "
                    "tomorrow_charge_starttime=%s, "
                    "tomorrow_available_charge_duration=%s, "
                    "tomorrow_need_charge_duration=%s, ",
                    self._caller,
                    tomorrow_charge_endtime,
                    sec_per_degree_sunrise,
                    elevation_start_trigger,
                    sunrise_offset,
                    next_sunrise,
                    tomorrow_charge_starttime,
                    tomorrow_available_charge_duration,
                    tomorrow_need_charge_duration,
                )

                # Check if need to start earlier than tomorrow sunrise
                if tomorrow_need_charge_duration > tomorrow_available_charge_duration:
                    tomorrow_propose_charge_starttime = (
                        tomorrow_charge_endtime - tomorrow_need_charge_duration
                    )

                    if tomorrow_propose_charge_starttime <= now_time:
                        # Need to start ASAP
                        tomorrow_new_charge_starttime = now_time + timedelta(minutes=2)
                    else:
                        # Can start later at proposed time
                        tomorrow_new_charge_starttime = (
                            tomorrow_propose_charge_starttime
                        )

                    _LOGGER.warning(
                        "%s: Setting next charge session start time: %s",
                        self._caller,
                        tomorrow_new_charge_starttime,
                    )

                    await self._async_set_next_charge_time(
                        tomorrow_new_charge_starttime
                    )

    # ----------------------------------------------------------------------------
    async def _async_tidy_up_on_exit(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        await self._async_update_ha(chargeable)

        switched_on = charger.is_charger_switch_on()
        if switched_on:
            await self._async_set_charge_current(charger, 0)
            await self._async_turn_charger_switch_off(charger)

        sun_state = self.get_sun_state_or_abort()
        sun_elevation: float = get_sun_elevation(self._caller, sun_state)
        _LOGGER.warning("%s: Stopped at sun_elevation=%s", self._caller, sun_elevation)

        await self._async_schedule_next_charge_session(charger, chargeable)

    # ----------------------------------------------------------------------------
    async def _async_start_charge_task(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Async task to start the charging process."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # chargeable: Chargeable | None = self.get_chargee

        #####################################
        # Set up instance variables
        #####################################
        # Must run this first thing to estimate if session started by timer
        self._session_triggered_by_timer = self._is_session_triggered_by_timer()
        self._goal = self._get_schedule_data(
            self._session_triggered_by_timer, chargeable
        )

        #####################################
        # Start charge session
        #####################################
        await self._async_init_device(chargeable)
        await self._async_init_charge_limit(charger, chargeable)
        await self._async_charge_device(charger, chargeable)
        await self._async_tidy_up_on_exit(charger, chargeable)

    # ----------------------------------------------------------------------------
    async def _async_start_charge(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Async task to start the charger."""
        await self._async_start_charge_task(charger, chargeable)

    # ----------------------------------------------------------------------------
    async def async_start_charge(self) -> Task:
        """Start charge."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # self.charge_task = self.config_entry.async_create_background_task(
        #     self.hass,
        #     self._async_start_charge_task(self.charger),
        #     "start_charge"
        # )

        if self._charge_task and not self._charge_task.done():
            _LOGGER.warning("Task %s already running", self._charge_task.get_name())
            return self._charge_task

        _LOGGER.info("Starting charge task for charger %s", self._caller)
        self._charge_task = self._hass.async_create_task(
            self._async_start_charge(self._charger, self._chargeable),
            f"{self._caller} charge",
        )
        return self._charge_task

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def _async_stop_charge_task(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Stop charge task."""
        if self._charge_task:
            if not self._charge_task.done():
                self._charge_task.cancel()

                try:
                    await self._charge_task
                except asyncio.CancelledError:
                    _LOGGER.info(
                        "Task %s cancelled successfully", self._charge_task.get_name()
                    )
                    await self._async_tidy_up_on_exit(charger, chargeable)
                except Exception as e:
                    _LOGGER.error(
                        "Error stopping charge task for charger %s: %s",
                        self._caller,
                        e,
                    )

                self._tracker.remove_callback(CALLBACK_ALLOCATE_POWER)

            else:
                _LOGGER.info("Task %s already completed", self._charge_task.get_name())

    # ----------------------------------------------------------------------------
    async def _async_stop_charge(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Async task to start the charger."""
        await self._async_stop_charge_task(charger, chargeable)

    # ----------------------------------------------------------------------------
    def stop_charge(self) -> Task | None:
        """Stop charge."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        if self._charge_task:
            if not self._charge_task.done():
                if self._end_charge_task:
                    if not self._end_charge_task.done():
                        _LOGGER.warning(
                            "Task %s already running", self._end_charge_task.get_name()
                        )
                        return self._end_charge_task

                _LOGGER.info("Ending charge task for charger %s", self._caller)
                self._end_charge_task = self._hass.async_create_task(
                    self._async_stop_charge(self._charger, self._chargeable),
                    f"{self._caller} end charge",
                )
                return self._end_charge_task

            _LOGGER.info("Task %s already completed", self._charge_task.get_name())
        else:
            _LOGGER.info("No running charge task to stop for charger %s", self._caller)
        return None
