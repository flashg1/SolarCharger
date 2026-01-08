"""Module to track entity updates."""

from collections.abc import Callable, Coroutine
from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from hassil import check_required_context

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_sunrise,
    async_track_sunset,
)

# Might be of help in the future.
# from homeassistant.helpers.sun import get_astral_event_next
from ..const import (  # noqa: TID252
    CALLBACK_ALLOCATE_POWER,
    CALLBACK_CHANGE_SUNRISE_ELEVATION_TRIGGER,
    CALLBACK_NEXT_CHARGE_TIME_TRIGGER,
    CALLBACK_NEXT_CHARGE_TIME_UPDATE,
    CALLBACK_PLUG_IN_CHARGER,
    CALLBACK_SUN_ELEVATION_UPDATE,
    CALLBACK_SUNRISE_START_CHARGE,
    CALLBACK_SUNSET_DAILY_MAINTENANCE,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    HA_SUN_ENTITY,
    NUMBER_CHARGER_ALLOCATED_POWER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
)
from ..sc_option_state import ScOptionState  # noqa: TID252
from ..utils import (  # noqa: TID252
    remove_all_callback_subscriptions,
    remove_callback_subscription,
    save_callback_subscription,
)

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

type STATE_CHANGE_CALLBACK = Callable[
    [Event[EventStateChangedData]], Coroutine[Any, Any, None]
]

type DELAY_CALLBACK = Callable[[datetime], Coroutine[Any, Any, None]]


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class Tracker(ScOptionState):
    """Class to track entity updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        caller: str,
    ) -> None:
        """Initialize the instance."""

        ScOptionState.__init__(self, hass, entry, subentry, caller)

        # self._unsub_callbacks: dict[
        #     str, Callable[[], Coroutine[Any, Any, None] | None]
        # ] = {}
        self._unsub_callbacks: dict[str, CALLBACK_TYPE] = {}

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Async setup of the Tracker."""

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of the Tracker."""
        remove_all_callback_subscriptions(self._unsub_callbacks)

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    def log_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Log state change event."""

        data = event.data
        entity_id = data["entity_id"]
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        _LOGGER.debug(
            "%s: entity_id=%s, old_state=%s, new_state=%s",
            self._caller,
            entity_id,
            old_state,
            new_state,
        )

    # ----------------------------------------------------------------------------
    def save_callback(self, callback_key: str, subscription: CALLBACK_TYPE) -> None:
        """Save callback."""

        save_callback_subscription(
            self._caller, self._unsub_callbacks, callback_key, subscription
        )

    # ----------------------------------------------------------------------------
    def remove_callback(self, callback_key: str) -> None:
        """Remove callback."""

        remove_callback_subscription(self._caller, self._unsub_callbacks, callback_key)

    # ----------------------------------------------------------------------------
    # Trackers
    # ----------------------------------------------------------------------------
    def track_charger_plugged_in_sensor(self, action: STATE_CHANGE_CALLBACK) -> bool:
        """Track charger plug in event."""
        ok: bool = False

        charger_plugged_in_sensor_entity = self.option_get_id(
            OPTION_CHARGER_PLUGGED_IN_SENSOR
        )

        if charger_plugged_in_sensor_entity:
            entity_entry = self.get_entity_entry(charger_plugged_in_sensor_entity)

            if entity_entry:
                _LOGGER.info(
                    "%s: Tracking charger plugged-in sensor: %s",
                    self._caller,
                    charger_plugged_in_sensor_entity,
                )

                #     self._async_handle_plug_in_charger_event,
                subscription = async_track_state_change_event(
                    self._hass,
                    charger_plugged_in_sensor_entity,
                    action,
                )

                self.save_callback(CALLBACK_PLUG_IN_CHARGER, subscription)
                ok = True
            else:
                _LOGGER.error(
                    "%s: Invalid plug-in sensor: %s",
                    self._caller,
                    charger_plugged_in_sensor_entity,
                )

        return ok

    # ----------------------------------------------------------------------------
    def untrack_charger_plugged_in_sensor(self) -> None:
        """Unsubscribe charger plug in event."""

        self.remove_callback(CALLBACK_PLUG_IN_CHARGER)

    # ----------------------------------------------------------------------------
    # See sun.sun entity.  Updates are at specific intervals.
    # Hard to calculate sun elevation offset time.
    # So just compare state change with configured elevation to trigger start of charge.
    def track_sun_elevation(self, action: STATE_CHANGE_CALLBACK) -> None:
        """Track sun elevation events."""

        _LOGGER.info(
            "%s: Tracking sun elevation: %s",
            self._caller,
            HA_SUN_ENTITY,
        )

        #     self._async_handle_sun_elevation_update,
        subscription = async_track_state_change_event(
            self._hass,
            HA_SUN_ENTITY,
            action,
        )

        self.save_callback(CALLBACK_SUN_ELEVATION_UPDATE, subscription)

    # ----------------------------------------------------------------------------
    def untrack_sun_elevation(self) -> None:
        """Unsubscribe sun elevation events."""

        self.remove_callback(CALLBACK_SUN_ELEVATION_UPDATE)

    # ----------------------------------------------------------------------------
    def unschedule_next_charge_time(self) -> None:
        """Unschedule next charge time."""

        self.remove_callback(CALLBACK_NEXT_CHARGE_TIME_TRIGGER)

    # ----------------------------------------------------------------------------
    def schedule_next_charge_time(
        self, new_starttime: datetime | None, action: DELAY_CALLBACK
    ) -> None:
        """Set up the next charge time trigger. new_starttime must be in local time."""

        local_time = self.get_local_datetime()

        if new_starttime is None or new_starttime < local_time:
            # Remove old callback if exist
            self.unschedule_next_charge_time()
        else:
            # Start charger at new_starttime
            delay: timedelta = new_starttime - local_time
            _LOGGER.info(
                "%s: Scheduling charger to start at %s (after delay %s)",
                self._caller,
                new_starttime,
                delay,
            )
            #     self._async_turn_on_charger_switch,
            subscription = async_call_later(
                self._hass,
                delay,
                action,
            )

            self.save_callback(CALLBACK_NEXT_CHARGE_TIME_TRIGGER, subscription)

    # ----------------------------------------------------------------------------
    def track_next_charge_time_trigger(
        self, entity_id: str, action: STATE_CHANGE_CALLBACK
    ) -> None:
        """Track next charge time trigger events."""

        _LOGGER.info(
            "%s: Tracking next charge time trigger: %s",
            self._caller,
            entity_id,
        )

        #     self._async_handle_next_charge_time_update,
        subscription = async_track_state_change_event(
            self._hass,
            entity_id,
            action,
        )

        self.save_callback(CALLBACK_NEXT_CHARGE_TIME_UPDATE, subscription)

    # ----------------------------------------------------------------------------
    def untrack_next_charge_time_trigger(self) -> None:
        """Unsubscribe next charge time trigger events."""

        self.remove_callback(CALLBACK_NEXT_CHARGE_TIME_UPDATE)

    # ----------------------------------------------------------------------------
    def track_allocated_power_update(self, action: STATE_CHANGE_CALLBACK) -> None:
        """Track allocated power update events."""

        allocated_power_entity = self.option_get_id_or_abort(
            NUMBER_CHARGER_ALLOCATED_POWER
        )
        _LOGGER.info(
            "%s: Tracking allocated power update: %s",
            self._caller,
            allocated_power_entity,
        )

        # Need both changed and unchanged events, eg. update1 at time1=-500W, update2 at time2=-500W
        # Need to handle both updates to make use of the spare power.
        # async_track_state_report_event - send unchanged events.
        # async_track_state_change_event - send changed events.
        # So need both to see all events?
        #     self._async_handle_allocated_power_update,
        subscription = async_track_state_change_event(
            self._hass,
            allocated_power_entity,
            action,
        )

        self.save_callback(CALLBACK_ALLOCATE_POWER, subscription)

    # ----------------------------------------------------------------------------
    def untrack_allocated_power_update(self) -> None:
        """Unsubscribe allocated power update events."""

        self.remove_callback(CALLBACK_ALLOCATE_POWER)

    # ----------------------------------------------------------------------------
    # Sunrise/sunset trigger code
    # ----------------------------------------------------------------------------
    # def _setup_daily_maintenance_at_sunset(self) -> None:
    #     """Every day, set up next sunrise trigger at sunset."""
    #     _LOGGER.info("%s: Setup daily maintenance at sunset", self._caller)
    #     # offset=timedelta(minutes=2)
    #     subscription = async_track_sunset(self._hass, self._setup_next_sunrise_trigger)
    #     save_callback_subscription(
    #         self._caller,
    #         self._unsub_callbacks,
    #         CALLBACK_SUNSET_DAILY_MAINTENANCE,
    #         subscription,
    #     )

    # ----------------------------------------------------------------------------
    # def _start_charge_on_sunrise(self) -> None:
    #     # async_track_sunrise() does not directly support coroutine callback, so create coroutine in event loop.
    #     # self._hass.loop.create_task(self.async_start_charge())
    #     self._turn_on_charger_switch()

    # ----------------------------------------------------------------------------
    # # Convert sun elevation to time offset calculation not correct and hard to do.
    # # So just monitor sun.sun state changes instead.

    # def _setup_next_sunrise_trigger(self) -> None:
    #     """Recalculate and setup next morning's sunrise trigger."""

    #     sun_state = self.get_sun_state_or_abort()
    #     sec_per_degree: float = get_sec_per_degree_sun_elevation(
    #         self._caller, sun_state
    #     )
    #     elevation_start_trigger = self.option_get_entity_number_or_abort(
    #         OPTION_SUNRISE_ELEVATION_START_TRIGGER
    #     )
    #     # Just in case, add 120 seconds.
    #     buffer = 120
    #     sunrise_offset = timedelta(
    #         seconds=sec_per_degree * elevation_start_trigger + buffer
    #     )

    #     # today = date.today()
    #     # Combine the date with the minimum time (00:00:00)
    #     # midnight_datetime = datetime.combine(today, datetime.min.time())

    #     # This is not working because time is in UTC. This method only works with local timezone.
    #     # today_sunrise_time = now_time.replace(
    #     #     hour=next_sunrise_time.hour,
    #     #     minute=next_sunrise_time.minute,
    #     #     second=next_sunrise_time.second,
    #     #     microsecond=next_sunrise_time.microsecond,
    #     # )

    #     is_sun_rising: bool = get_is_sun_rising(self._caller, sun_state)
    #     current_elevation: float = get_sun_elevation(self._caller, sun_state)

    #     if is_sun_rising and current_elevation < elevation_start_trigger:
    #         # Today
    #         now_time = utcnow()
    #         next_sunrise_time: datetime = get_next_sunrise_time(self._caller, sun_state)
    #         next_sunset_time: datetime = get_next_sunset_time(self._caller, sun_state)
    #         if next_sunrise_time > next_sunset_time:
    #             # Passed today sunrise
    #             today_sunrise_time = next_sunrise_time - timedelta(days=1)
    #             today_sunrise_trigger_time = today_sunrise_time + sunrise_offset
    #             duration_from_now = today_sunrise_trigger_time - now_time
    #             duration_to_trigger = timedelta(
    #                 seconds=duration_from_now.total_seconds()
    #             )

    #             _LOGGER.warning(
    #                 "elevation_start_trigger=%s, "
    #                 "sec_per_degree=%s, "
    #                 "sunrise_offset=%s, "
    #                 "now_time=%s, "
    #                 "current_elevation=%s, "
    #                 "today_sunrise_time=%s, "
    #                 "today_sunrise_trigger_time=%s, "
    #                 "duration_from_now=%s, "
    #                 "duration_to_trigger=%s, "
    #                 "next_sunrise_time=%s, "
    #                 "next_sunset_time=%s",
    #                 elevation_start_trigger,
    #                 sec_per_degree,
    #                 sunrise_offset,
    #                 now_time,
    #                 current_elevation,
    #                 today_sunrise_time,
    #                 today_sunrise_trigger_time,
    #                 duration_from_now,
    #                 duration_to_trigger,
    #                 next_sunrise_time,
    #                 next_sunset_time,
    #             )

    #             _LOGGER.info(
    #                 "%s: Past sunrise today with trigger offset %s from now (current_elevation=%s, sec_per_degree=%s)",
    #                 self._caller,
    #                 duration_to_trigger,
    #                 current_elevation,
    #                 sec_per_degree,
    #             )
    #             subscription = async_call_later(
    #                 self._hass, duration_to_trigger, self._async_turn_on_charger_switch
    #             )

    #         else:
    #             # Sunrise yet to happen today
    #             _LOGGER.info(
    #                 "%s: Setup today sunrise trigger offset %s from sunrise (current_elevation=%s, sec_per_degree=%s)",
    #                 self._caller,
    #                 sunrise_offset,
    #                 current_elevation,
    #                 sec_per_degree,
    #             )
    #             subscription = async_track_sunrise(
    #                 self._hass, self._start_charge_on_sunrise, sunrise_offset
    #             )

    #             # next_sunrise_trigger_time = next_sunrise_time + sunrise_offset
    #             # duration_from_now = next_sunrise_trigger_time - now_time
    #             # duration_to_trigger = timedelta(
    #             #     seconds=duration_from_now.total_seconds()
    #             # )

    #     else:
    #         # Tomorrow
    #         _LOGGER.info(
    #             "%s: Setup tomorrow sunrise trigger offset %s from sunrise (current_elevation=%s, sec_per_degree=%s)",
    #             self._caller,
    #             sunrise_offset,
    #             current_elevation,
    #             sec_per_degree,
    #         )
    #         subscription = async_track_sunrise(
    #             self._hass, self._start_charge_on_sunrise, sunrise_offset
    #         )

    #     save_callback_subscription(
    #         self._caller,
    #         self._unsub_callbacks,
    #         CALLBACK_SUNRISE_START_CHARGE,
    #         subscription,
    #     )

    # ----------------------------------------------------------------------------
    # def _set_up_sun_triggers(self) -> None:
    #     # Set up sunset daily maintenance
    #     self._setup_daily_maintenance_at_sunset()

    #     # Set up sunrise trigger
    #     self._setup_next_sunrise_trigger()

    # ----------------------------------------------------------------------------
    # Monitored entities
    # ----------------------------------------------------------------------------
    # async def _async_handle_sunrise_elevation_trigger_change(
    #     self, event: Event[EventStateChangedData]
    # ) -> None:
    #     """Fetch and process state change event."""
    #     data = event.data
    #     old_state: State | None = data["old_state"]
    #     new_state: State | None = data["new_state"]

    #     self._log_state_change(event)

    #     if new_state is not None:
    #         if old_state is not None:
    #             if (
    #                 new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
    #                 and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
    #                 and new_state.state != old_state.state
    #             ):
    #                 self._setup_next_sunrise_trigger()

    # ----------------------------------------------------------------------------
    # def _track_sunrise_elevation_trigger(self) -> None:
    #     sunrise_elevation_trigger_entity = self.option_get_id_or_abort(
    #         OPTION_SUNRISE_ELEVATION_START_TRIGGER
    #     )
    #     _LOGGER.info(
    #         "%s: Tracking sunrise elevation trigger: %s",
    #         self._caller,
    #         sunrise_elevation_trigger_entity,
    #     )

    #     subscription = async_track_state_change_event(
    #         self._hass,
    #         sunrise_elevation_trigger_entity,
    #         self._async_handle_sunrise_elevation_trigger_change,
    #     )

    #     save_callback_subscription(
    #         self._caller,
    #         self._unsub_callbacks,
    #         CALLBACK_CHANGE_SUNRISE_ELEVATION_TRIGGER,
    #         subscription,
    #     )
