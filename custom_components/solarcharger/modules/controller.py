# ruff: noqa: TRY401, TID252, PLR5501
"""Module to manage the charging process and entity subscriptions."""

import asyncio
from asyncio import Task
from collections.abc import Callable, Coroutine
from datetime import datetime, time
import inspect
import logging
from typing import TYPE_CHECKING, Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.typing import NoEventData
from homeassistant.util.dt import utcnow

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..chargers.sc_option_state import ScOptionState
from ..const import (
    DEFAULT_CHARGE_LIMIT_MAP,
    DELTA_CHARGER_CURRENT_UPDATE_PERIOD,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
    SENSOR_INSTANCE_COUNT,
    SENSOR_SYNC_UPDATE,
    SENSOR_WEATHER_FORECAST,
    SUBENTRY_CHARGER_TYPES,
    SUBENTRY_TYPE_DEFAULTS,
    SWITCH_CHARGE,
    WEEKLY_CHARGE_ENDTIMES,
)
from ..helpers.utils import get_is_sun_rising, get_sun_elevation, log_is_event_loop
from ..models.model_charge_control import ChargeControl
from ..models.model_schedule_data import ScheduleData
from ..state_machine.solar_charge import SolarCharge
from .tracker import Tracker

if TYPE_CHECKING:
    from ..models.model_device_control import DeviceControl

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

type SWITCH_ACTION = Callable[[bool], Coroutine[Any, Any, None]]


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ChargeController(ScOptionState):
    """Class to manage the charging process."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        control: ChargeControl,
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

        # Do no subscribe callbacks if controller is initialising, because local
        # device entities have not been created yet when first creating device.
        # So problem will only happen when first creating device. Subsequent restarts
        # will not see problem because device subentry and entities have been created.
        # To work around this issue, do not run the switch action during initialisation,
        # and manual subscribe or unsubscribe once after initialisation so as to be in
        # sync with the switches.
        self._initialising: bool = True

        self._control = control
        self._charger = charger
        self._chargeable = chargeable
        self._tracker = Tracker(hass, entry, subentry, caller)
        self._solar_charge = SolarCharge(
            hass,
            entry,
            subentry,
            self._tracker,
            self._control.entities,
            charger,
            chargeable,
        )
        self._charge_task: Task | None = None
        self._end_charge_task: Task | None = None

        self._is_updated_today_tomorrow_schedule: bool = False

        #######################################################
        # Global defaults device only.
        #######################################################
        # Started tracking weather
        self._weather_provider: str = None
        self._tracking_weather: bool = False

        # Required by Allocator
        self._device_controls: dict[str, DeviceControl]
        # Charge current update period.
        self._current_update_period: float = 0
        # Slightly smaller charge current update period to allow for variation in net power update interval.
        self._min_current_update_period: float = 0
        # Sync charge current time.
        self._sync_charge_current_time: float = 0  # UTC time
        # Net power update count
        self._net_power_update_count: int = 0

    # ----------------------------------------------------------------------------
    @cached_property
    def charge_control(self) -> ChargeControl:
        """Return the charge control object."""
        return self._control

    @cached_property
    def solar_charge(self) -> SolarCharge:
        """Return the solar charge object."""
        return self._solar_charge

    @property
    def is_updated_today_tomorrow_schedule(self) -> bool:
        """Return whether need to check charge schedule."""
        return self._is_updated_today_tomorrow_schedule

    def set_updated_today_tomorrow_schedule(self, value: bool) -> None:
        """Set whether need to check charge schedule."""
        self._is_updated_today_tomorrow_schedule = value

    # ----------------------------------------------------------------------------
    # Global defaults functions
    # ----------------------------------------------------------------------------
    # Weather provider
    # ----------------------------------------------------------------------------
    def _update_sensor_attribute(
        self, config_item: str, state_value: str, attributes: dict[str, Any] | None
    ) -> None:
        """Update attribute sensor."""

        try:
            # Global defaults subentry device
            control = self._device_controls[self._subentry.subentry_id]

            assert control.controller.charge_control.entities.sensors is not None
            control.controller.charge_control.entities.sensors[
                config_item
            ].set_complete_state(state_value, attributes)

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to update attribute sensor data: %s",
                self.caller,
                e,
            )

    # ----------------------------------------------------------------------------
    async def _async_update_weather_sensor(self, entity_id: str) -> None:
        """Update weather sensor."""

        state_obj = self._hass.states.get(entity_id)
        if not state_obj:
            return

        # The attributes has current weather condition but no daily data, so get
        # daily data separately below.
        attributes = dict(state_obj.attributes)

        # Request weather forecast data correctly via the standard service engine
        try:
            # Setting blocking=True with return_response=True satisfies HA execution rules
            response = await self._hass.services.async_call(
                domain="weather",
                service="get_forecasts",
                service_data={"type": "daily"},
                target={"entity_id": entity_id},
                blocking=True,  # Required when returning a response
                return_response=True,  # Tells HA to expect data payload mapping
            )

            # Safely extract and map the forecast list to attributes
            if response and entity_id in response:
                attributes["daily_forecast"] = response[entity_id].get("forecast", [])
            else:
                attributes["daily_forecast"] = []

        except Exception as e:
            _LOGGER.warning(
                "%s: Failed get_forecasts: %s: %s", self.caller, entity_id, e
            )

        # Assign and commit the newly bundled metadata state
        self._update_sensor_attribute(
            SENSOR_WEATHER_FORECAST, state_obj.state, attributes
        )

    # ----------------------------------------------------------------------------
    @callback
    def _async_handle_weather_update(
        self, event: Event[EventStateChangedData] | None
    ) -> None:
        """Handle weather update."""

        entity_id = self.get_weather_provider()
        if entity_id is not None:
            self._hass.async_create_task(self._async_update_weather_sensor(entity_id))

    # ----------------------------------------------------------------------------
    def _subscribe_weather(self, weather_provider: str) -> None:
        """Subscribe weather updates."""

        if self._tracker.track_weather_update(self._async_handle_weather_update):
            # Populate weather sensor with data.
            self._async_handle_weather_update(None)
            self._weather_provider = weather_provider
            self._tracking_weather = True
        else:
            self._weather_provider = None
            self._tracking_weather = False

    # ----------------------------------------------------------------------------
    def _unsubscribe_weather(self) -> None:
        """Unsubscribe weather updates."""

        self._tracker.untrack_weather_update()
        self._update_sensor_attribute(SENSOR_WEATHER_FORECAST, STATE_UNKNOWN, None)
        self._weather_provider = None
        self._tracking_weather = False

    # ----------------------------------------------------------------------------
    def check_weather_provider(self) -> None:
        """Track weather if weather provider is defined."""

        entity_id = self.get_weather_provider()
        if entity_id is not None:
            if entity_id != self._weather_provider and self._tracking_weather:
                self._unsubscribe_weather()

            if not self._tracking_weather:
                self._subscribe_weather(entity_id)

        else:
            if self._tracking_weather:
                self._unsubscribe_weather()

    # ----------------------------------------------------------------------------
    # Allocator
    # ----------------------------------------------------------------------------
    async def _async_allocate_net_power(self) -> bool:
        """Execute an update cycle."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())
        ok: bool = False

        try:
            ok = await self._allocator.async_allocate_net_power()

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to allocate net power: %s",
                self.caller,
                e,
            )

        return ok

    # ----------------------------------------------------------------------------
    async def _async_synchronise_charge_current_update(self) -> None:
        """Synchronise charge current update for all chargers."""

        try:
            # Coordinator has global defaults subentry
            control = self._device_controls[self._subentry.subentry_id]

            assert control.controller.charge_control.entities.sensors is not None
            control.controller.charge_control.entities.sensors[
                SENSOR_SYNC_UPDATE
            ].set_state(datetime.now().astimezone())

            self._sync_charge_current_time = utcnow().timestamp()

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to synchronise charge current update: %s",
                self.caller,
                e,
            )

    # ----------------------------------------------------------------------------
    # 2025-11-02 09:01:48.009 INFO (MainThread) [custom_components.solarcharger.chargers.controller] tesla_custom_tesla23m3:
    # entity_id=number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power,
    #
    # old_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-500.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:00:32.962356+11:00>,
    #
    # new_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-200.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:01:48.008211+11:00>
    async def _async_handle_net_power_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Use net power update event to synchronise charge current update when reaching update period."""

        data = event.data
        entity_id = data["entity_id"]
        old_state = data["old_state"]
        new_state = data["new_state"]

        if new_state is not None:
            # Should use last_updated_timestamp instead of last_changed_timestamp since value might not have changed.
            # last_updated_timestamp is updated when state is updated, while last_changed_timestamp is only updated when state changes.
            # duration_since_last_sync = (
            #     new_state.last_updated_timestamp - self._sync_charge_current_time
            # )

            # Note that last_updated_timestamp and last_changed_timestamp are in UTC.
            # For adhering to current_update_period.
            duration_since_last_sync = (
                utcnow().timestamp() - self._sync_charge_current_time
            )

            _LOGGER.debug(
                "Net power update: duration_since_last_sync=%s, new_state=%s, old_state=%s, entity_id=%s",
                duration_since_last_sync,
                new_state.state,
                old_state.state,
                entity_id,
            )

            try:
                # Allocate power for median net allocated power calculation.
                if await self._async_allocate_net_power():
                    self._net_power_update_count += 1

                # Synchronise charge current update for all chargers.
                # During testing with 10s period for both net power and current, not every
                # net power update trigger a current update due to period variation.
                if (
                    self._net_power_update_count > 0
                    and duration_since_last_sync >= self._min_current_update_period
                ):
                    self._net_power_update_count = 0
                    await self._async_synchronise_charge_current_update()

            except Exception as e:
                _LOGGER.exception(
                    "%s: Failed to synchronise charge current update for net power %s W: %s",
                    self.caller,
                    new_state.state,
                    e,
                )

    # ----------------------------------------------------------------------------
    def _track_net_power_update(self) -> None:
        """Track net power update."""

        self._allocator.init_allocator()
        ok = self._tracker.track_net_power_update(self._async_handle_net_power_update)
        if not ok:
            _LOGGER.error("%s: Invalid net power sensor", self.caller)
            # raise EntityExceptionError("Invalid net power sensor")

    # ----------------------------------------------------------------------------
    # Charger functions
    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    # Call HA to turn on or off the actual switch
    # ----------------------------------------------------------------------------
    async def _async_turn_off_plugin_trigger(self) -> None:
        """Turn off plug-in trigger switch."""

        await self.async_turn_switch(
            self.plugin_trigger_switch_entity_id, turn_on=False
        )

    # ----------------------------------------------------------------------------
    async def _async_turn_off_presence_trigger(self) -> None:
        """Turn off detect presence trigger switch."""

        await self.async_turn_switch(
            self.presence_trigger_switch_entity_id, turn_on=False
        )

    # ----------------------------------------------------------------------------
    def _turn_charger_switch(self, turn_on: bool) -> None:
        """Create a task to turn on the charger switch."""

        # async_track_sunrise() does not directly support coroutine callback, so create coroutine in event loop.
        # self._hass.loop.create_task(self.async_start_charge())

        self._hass.loop.create_task(
            self.async_turn_switch(self.charge_switch_entity_id, turn_on)
        )

    # ----------------------------------------------------------------------------
    # Called by next charge time trigger only
    async def _async_turn_on_charger_switch(self, now: datetime) -> None:
        """Start charger from coroutine callback."""

        # async_call_later do support coroutine callback, so can call directly.
        await self.async_turn_switch(self.charge_switch_entity_id, turn_on=True)

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    async def _async_switch_task(self, action: SWITCH_ACTION, turn_on: bool):
        """Start another task to action a switch state when not initialising. The switch must be in the correct state when starting task."""

        if not self._initialising:
            self._hass.loop.create_task(action(turn_on))

    # ----------------------------------------------------------------------------
    async def async_check_if_need_to_reschedule_charge(self) -> None:
        """Reschedule charge due to schedule update."""

        if self.is_updated_today_tomorrow_schedule:
            try:
                _LOGGER.info(
                    "%s: Checking if need to reschedule charge due to schedule update",
                    self.caller,
                )
                if (
                    self.charge_control.instance_count == 0
                    and self.is_schedule_charge()
                ):
                    await self.solar_charge.async_wake_up_and_update_ha(
                        self._chargeable
                    )
                    goal: ScheduleData = (
                        await self.solar_charge.async_get_current_schedule_data()
                    )
                    if goal.use_charge_schedule and (
                        goal.has_charge_endtime
                        or (
                            goal.battery_soc is not None
                            and goal.battery_soc < goal.new_charge_limit
                        )
                    ):
                        if self.solar_charge.is_device_at_location_and_connected():
                            _LOGGER.warning(
                                "%s: Rescheduling charge due to schedule update",
                                self.caller,
                            )
                            self._turn_charger_switch(turn_on=True)

            except Exception as e:
                _LOGGER.exception(
                    "%s: Failed to check if need to reschedule charge: %s",
                    self.caller,
                    e,
                )

            self.set_updated_today_tomorrow_schedule(False)

    # ----------------------------------------------------------------------------
    # Tracker callbacks
    # ----------------------------------------------------------------------------
    async def async_handle_sun_elevation_update(
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
                        NUMBER_SUNRISE_ELEVATION_START_TRIGGER
                    )

                    is_sun_rising: bool = get_is_sun_rising(self.caller, old_sun_state)
                    old_elevation: float = get_sun_elevation(self.caller, old_sun_state)
                    new_elevation: float = get_sun_elevation(self.caller, new_sun_state)

                    _LOGGER.debug(
                        "%s: is_sun_rising=%s, old_elevation=%s, new_elevation=%s",
                        self.caller,
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
                        await self.async_turn_switch(
                            self.charge_switch_entity_id, turn_on=True
                        )

    # ----------------------------------------------------------------------------
    async def async_handle_plug_in_charger_event(
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
                    if self.solar_charge.is_connected(self._charger):
                        self._turn_charger_switch(turn_on=True)

    # ----------------------------------------------------------------------------
    async def async_handle_device_presence_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        self._tracker.log_state_change(event)

        if new_state is not None:
            if old_state is not None:
                if (
                    new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                    and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                    and new_state.state != old_state.state
                ):
                    if new_state.state == STATE_ON and old_state.state == STATE_OFF:
                        self._solar_charge.start_check_charger_connection_task()

    # ----------------------------------------------------------------------------
    async def async_handle_next_charge_time_update(
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
                try:
                    new_starttime = self.parse_local_datetime(new_state.state)
                    self._tracker.schedule_next_charge_time(
                        new_starttime, self._async_turn_on_charger_switch
                    )
                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "%s: Failed to schedule next charge time '%s': %s",
                        self.caller,
                        new_state.state,
                        e,
                    )

    # ----------------------------------------------------------------------------
    def _subscribe_next_charge_time_update(self) -> None:
        """Subscribe for next charge time update. This is always on."""

        self._tracker.track_next_charge_time_trigger(
            self.next_charge_time_trigger_entity_id,
            self.async_handle_next_charge_time_update,
        )

    # ----------------------------------------------------------------------------
    async def async_handle_charge_limit_update(
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
                and new_state.state != old_state.state
            ):
                today_index = self.get_local_datetime().weekday()
                tomorrow_index = (today_index + 1) % 7
                day_index = self.get_charge_limit_entity_ids.get(new_state.entity_id)
                if day_index in (today_index, tomorrow_index):
                    if (
                        self.charge_control.instance_count == 0
                        and self.is_schedule_charge()
                    ):
                        self.set_updated_today_tomorrow_schedule(True)

    # ----------------------------------------------------------------------------
    async def async_handle_charge_endtime_update(
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
                and new_state.state != old_state.state
            ):
                today_index = self.get_local_datetime().weekday()
                tomorrow_index = (today_index + 1) % 7
                day_index = self.get_charge_endtime_entity_ids.get(new_state.entity_id)
                if day_index in (today_index, tomorrow_index):
                    if (
                        self.charge_control.instance_count == 0
                        and self.is_schedule_charge()
                    ):
                        self.set_updated_today_tomorrow_schedule(True)

    # ----------------------------------------------------------------------------
    def _subscribe_charge_schedule_update(self) -> None:
        """Subscribe to charge schedule update. This is always on."""

        if not self._tracker.track_charge_limit_schedule(
            list(self.get_charge_limit_entity_ids.keys()),
            self.async_handle_charge_limit_update,
        ):
            raise RuntimeError("Failed to subscribe to charge limit schedule updates")

        if not self._tracker.track_charge_endtime_schedule(
            list(self.get_charge_endtime_entity_ids.keys()),
            self.async_handle_charge_endtime_update,
        ):
            raise RuntimeError("Failed to subscribe to charge endtime schedule updates")

    # ----------------------------------------------------------------------------
    def _unsubscribe_charge_schedule_update(self) -> None:
        """Unsubscribe from charge schedule update."""

        self._tracker.untrack_charge_limit_schedule()
        self._tracker.untrack_charge_endtime_schedule()

    # ----------------------------------------------------------------------------
    # Button actions
    # ----------------------------------------------------------------------------
    async def async_reset_charge_limit_default(self) -> None:
        """Reset charge limit defaults."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        if not (self._control.entities.numbers and self._control.entities.times):
            return

        _LOGGER.info(
            "%s: Resetting charge limit and charge end time defaults",
            self.caller,
        )

        min_charge_limit = self.get_min_charge_limit()
        max_charge_limit = self.get_max_charge_limit()

        # Set charge limits
        for day_limit_default in DEFAULT_CHARGE_LIMIT_MAP:
            # default_val = get_saved_option_value(
            #     self._entry, subentry, day_limit_default, True
            # )
            default_val = self.option_get_entity_number_or_abort(day_limit_default)

            day_limit = DEFAULT_CHARGE_LIMIT_MAP[day_limit_default]
            if (
                default_val is not None
                and min_charge_limit <= default_val <= max_charge_limit
            ):
                await self._control.entities.numbers[day_limit].async_set_native_value(
                    default_val
                )
            else:
                _LOGGER.error(
                    "%s: Cannot set default charge limit %s for %s, min_charge_limit=%s, max_charge_limit=%s",
                    self.caller,
                    default_val,
                    day_limit,
                    min_charge_limit,
                    max_charge_limit,
                )

        # Set charge end times
        for day_endtime in WEEKLY_CHARGE_ENDTIMES:
            await self._control.entities.times[day_endtime].async_set_value(time.min)

    # ----------------------------------------------------------------------------
    # Switch actions
    # ----------------------------------------------------------------------------
    async def _async_switch_schedule_charge(self, turn_on: bool) -> None:
        """Action schedule charge switch."""

        _LOGGER.info("%s: Schedule charge: %s", self.caller, turn_on)
        if turn_on:
            # Trigger is lost on restart, so reschedule next charge session if applicable.
            next_charge_time = self.get_datetime(
                self.next_charge_time_trigger_entity_id
            )
            self._tracker.schedule_next_charge_time(
                next_charge_time, self._async_turn_on_charger_switch
            )

            # Monitor charge schedule updates for rescheduling.
            self._subscribe_charge_schedule_update()

        else:
            self._tracker.unschedule_next_charge_time()
            self._unsubscribe_charge_schedule_update()

    # ----------------------------------------------------------------------------
    async def _async_switch_plugin_trigger(self, turn_on: bool) -> None:
        """Action plug-in trigger switch."""

        _LOGGER.info("%s: Plugin trigger: %s", self.caller, turn_on)
        if turn_on:
            ok = self._tracker.track_charger_plugged_in_sensor(
                self.async_handle_plug_in_charger_event
            )
            if not ok:
                await self._async_turn_off_plugin_trigger()
        else:
            self._tracker.untrack_charger_plugged_in_sensor()

    # ----------------------------------------------------------------------------
    async def _async_switch_presence_trigger(self, turn_on: bool) -> None:
        """Action presence trigger switch."""

        _LOGGER.info("%s: Presence trigger: %s", self.caller, turn_on)
        if turn_on:
            ok = self._tracker.track_device_presence_sensor(
                self.async_handle_device_presence_event
            )
            if not ok:
                await self._async_turn_off_presence_trigger()
        else:
            self._tracker.untrack_device_presence_sensor()

    # ----------------------------------------------------------------------------
    async def _async_switch_sun_elevation_trigger(self, turn_on: bool) -> None:
        """Action sun elevation trigger switch."""

        _LOGGER.info("%s: Sun elevation trigger: %s", self.caller, turn_on)
        if turn_on:
            self._tracker.track_sun_elevation(self.async_handle_sun_elevation_update)
        else:
            self._tracker.untrack_sun_elevation()

    # ----------------------------------------------------------------------------
    async def _async_switch_calibrate_max_charge_speed(self, turn_on: bool) -> None:
        """Action calibrate max charge speed switch."""

        _LOGGER.info("%s: Calibrate max charge speed: %s", self.caller, turn_on)
        if turn_on:
            if self._charge_task is None or self._charge_task.done():
                self._turn_charger_switch(turn_on=True)
        else:
            await self.solar_charge.async_stop_calibrate_max_charge_speed()

    # ----------------------------------------------------------------------------
    async def _async_start_charge(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Async task to start the charger."""
        await self.solar_charge.async_start_charge_task(charger, chargeable)

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

        _LOGGER.info("%s: Starting charge task", self.caller)
        self._charge_task = self._hass.async_create_task(
            self._async_start_charge(self._charger, self._chargeable),
            f"{self.caller} charge",
        )
        return self._charge_task

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def _async_abort_charge_task(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Abort charge task on HA stop."""

        if self._charge_task:
            if not self._charge_task.done():
                self._charge_task.cancel()

                try:
                    await self._charge_task
                except asyncio.CancelledError:
                    _LOGGER.warning(
                        "%s: Aborted charge task",
                        self.caller,
                    )
                except Exception as e:
                    _LOGGER.exception(
                        "%s: Error aborting charge task: %s",
                        self.caller,
                        e,
                    )

            else:
                _LOGGER.info(
                    "%s: Charge task already completed",
                    self.caller,
                )

    # ----------------------------------------------------------------------------
    async def _async_abort_solar_charger(
        self, event: Event[NoEventData] | None
    ) -> None:
        """Stop solar charger."""

        # Stop charge task to avoid blocking HA shutdown.
        await self._async_abort_charge_task(self._charger, self._chargeable)

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
                    await self.solar_charge.async_tidy_up()

                except Exception as e:
                    _LOGGER.exception(
                        "%s: Error stopping charge task: %s",
                        self.caller,
                        e,
                    )

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

                _LOGGER.info("%s: Ending charge task", self.caller)
                self._end_charge_task = self._hass.async_create_task(
                    self._async_stop_charge(self._charger, self._chargeable),
                    f"{self.caller} end charge",
                )
                return self._end_charge_task

            _LOGGER.info("Task %s already completed", self._charge_task.get_name())
        else:
            _LOGGER.info("%s: No running charge task to stop", self.caller)
        return None

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def async_start_charger(self, control: ChargeControl) -> None:
        """Start the charger."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        if control:
            if control.charge_task:
                if not control.charge_task.done():
                    _LOGGER.debug(
                        "Task %s already running", control.charge_task.get_name()
                    )
                    return

            #####################################
            # Callback on task end
            # Cannot be async due to following error.
            # TypeError: coroutines cannot be used with call_soon()
            #####################################
            def _callback_on_charge_end(task: Task) -> None:
                """Turn off switch on task exit."""
                log_is_event_loop(
                    _LOGGER, self.__class__.__name__, inspect.currentframe()
                )
                if task.cancelled():
                    _LOGGER.warning("Task %s was cancelled", task.get_name())
                elif task.exception():
                    _LOGGER.error(
                        "Task %s failed: %s", task.get_name(), task.exception()
                    )
                else:
                    _LOGGER.info("Task %s completed", task.get_name())

                control.instance_count = 0
                # await async_set_allocated_power(control, 0)

                if control.entities.switches:
                    control.switch_charge = False
                    control.entities.switches[SWITCH_CHARGE].turn_off()

                if control.entities.sensors:
                    control.entities.sensors[SENSOR_INSTANCE_COUNT].set_state(
                        control.instance_count
                    )
                    # I don't think setting SENSOR_CONSUMED_POWER is required here.
                    # control.entities.sensors[SENSOR_CONSUMED_POWER].set_state(0.0)

            control.charge_task = await self.async_start_charge()
            control.instance_count = 1
            control.charge_task.add_done_callback(_callback_on_charge_end)
            if control.entities.sensors:
                control.entities.sensors[SENSOR_INSTANCE_COUNT].set_state(
                    control.instance_count
                )

    # ----------------------------------------------------------------------------
    async def async_stop_charger(self, control: ChargeControl) -> None:
        """Stop the charger."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        if control:
            if control.charge_task:
                if not control.charge_task.done():
                    if control.end_charge_task:
                        if not control.end_charge_task.done():
                            _LOGGER.debug(
                                "Task %s already running",
                                control.end_charge_task.get_name(),
                            )
                            return

                    control.end_charge_task = self.stop_charge()

    # ----------------------------------------------------------------------------
    async def _async_switch_charge(self, turn_on: bool):
        """Action charge switch."""

        _LOGGER.debug(
            "%s: Switch charge on: %s", self.charge_control.config_name, turn_on
        )

        if turn_on:
            if self.charge_control.switch_charge:
                _LOGGER.error(
                    "%s: Charger already running", self.charge_control.config_name
                )
            else:
                self.charge_control.switch_charge = True
                await self.async_start_charger(self.charge_control)
        else:  # noqa: PLR5501
            if self.charge_control.switch_charge:
                self.charge_control.switch_charge = False
                await self.async_stop_charger(self.charge_control)
            else:
                _LOGGER.error(
                    "%s: Charger already stopped", self.charge_control.config_name
                )

    # ----------------------------------------------------------------------------
    # Called by switch entities/coordinator to action the switch state
    # ----------------------------------------------------------------------------
    async def async_switch_schedule_charge(self, turn_on: bool) -> None:
        """Called by switch entity/coordinator to turn on/off schedule charge."""

        await self._async_switch_task(self._async_switch_schedule_charge, turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_plugin_trigger(self, turn_on: bool) -> None:
        """Called by switch entity/coordinator to turn on/off plug-in trigger."""

        await self._async_switch_task(self._async_switch_plugin_trigger, turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_presence_trigger(self, turn_on: bool) -> None:
        """Called by switch entity/coordinator to turn on/off presence trigger."""

        await self._async_switch_task(self._async_switch_presence_trigger, turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_sun_elevation_trigger(self, turn_on: bool) -> None:
        """Called by switch entity/coordinator to turn on/off sun elevation trigger."""

        await self._async_switch_task(self._async_switch_sun_elevation_trigger, turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_calibrate_max_charge_speed(self, turn_on: bool) -> None:
        """Called by switch entity/coordinator to calibrate max charge speed switch."""

        await self._async_switch_task(
            self._async_switch_calibrate_max_charge_speed, turn_on
        )

    # ----------------------------------------------------------------------------
    async def async_switch_charge(self, turn_on: bool):
        """Called by switch entity/coordinator to start or stop charge."""

        await self._async_switch_task(self._async_switch_charge, turn_on)

    # ----------------------------------------------------------------------------
    # Set up and unload
    # ----------------------------------------------------------------------------
    async def _async_activate_controller_switches(
        self, event: Event[NoEventData] | None
    ) -> None:
        """Activate controller switches once after HA has initialised.

        The charge task can hold up HA on restart, so must run charge task after HA has started.
        Other switches are ok, but best to also run after HA has started to ensure the entities are available.
        """

        # Only activate switch actions when HA has fully started, otherwise will hang others during startup.
        # eg. Switch on charge while HA is still starting up.
        self._initialising = False

        # Permanent subscriptions
        self._subscribe_next_charge_time_update()

        # Track next charge time trigger
        await self.async_switch_schedule_charge(self.is_schedule_charge())

        # Track charger plug-in
        await self.async_switch_plugin_trigger(self.is_plugin_trigger())

        # Track device presence
        await self.async_switch_presence_trigger(self.is_presence_trigger())

        # Track sun elevation
        await self.async_switch_sun_elevation_trigger(self.is_sun_trigger())

        # Resume charging if it was charging before HA restart
        await self.async_switch_charge(self.is_charge_switch_on())
        await asyncio.sleep(1)

        # Resume charging if it was charging before HA restart
        await self.async_switch_calibrate_max_charge_speed(
            self.is_calibrate_max_charge_speed()
        )

        # Remove HA started callback if exists
        self._tracker.remove_ha_started_callback()

    # ----------------------------------------------------------------------------

    # ----------------------------------------------------------------------------
    async def _async_activate_power_allocator(
        self, event: Event[NoEventData] | None
    ) -> None:

        # coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

        # # device_controls must be initialised first since allocator needs to access device_controls.
        # self._allocator = PowerAllocator(self._subentry, device_controls)
        self._current_update_period = self.get_charger_current_update_period()
        self._min_current_update_period = (
            self._current_update_period
            * (100 - DELTA_CHARGER_CURRENT_UPDATE_PERIOD)
            / 100
        )

        _LOGGER.info(
            "%s: current_update_period=%s, min_current_update_period=%s",
            self.caller,
            self._current_update_period,
            self._min_current_update_period,
        )

        self._track_net_power_update()

        # Remove HA started callback if exists
        self._tracker.remove_ha_started_callback()

    # ----------------------------------------------------------------------------
    async def _async_init_global_defaults_device(
        self, device_controls: dict[str, DeviceControl]
    ) -> None:
        """Init global defaults device."""

        # device_controls must be initialised first since allocator needs to access device_controls.
        from .allocator import PowerAllocator

        self._device_controls = device_controls
        self._allocator = PowerAllocator(self._subentry, device_controls)

        if self._hass.state == CoreState.running:
            await self._async_activate_power_allocator(None)
        else:
            self._tracker.on_ha_started(self._async_activate_power_allocator)

    # ----------------------------------------------------------------------------
    async def _async_init_charger_device(self) -> None:
        """Init charger device."""

        await self._charger.async_setup()

        self._tracker.on_ha_stop(self._async_abort_solar_charger)

        if self._hass.state == CoreState.running:
            await self._async_activate_controller_switches(None)
        else:
            self._tracker.on_ha_started(self._async_activate_controller_switches)

    # ----------------------------------------------------------------------------
    async def async_setup(self, device_controls: dict[str, DeviceControl]) -> None:
        """Async setup of the ChargeController."""

        # Load tracker.
        await self._tracker.async_setup()

        # Load charger.
        if self._subentry.subentry_type == SUBENTRY_TYPE_DEFAULTS:
            await self._async_init_global_defaults_device(device_controls)

        elif self._subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
            await self._async_init_charger_device()

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of the ChargeController."""

        # Unload charger.
        if self._subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
            # Abort charge task if running.
            await self._async_abort_solar_charger(None)

            await self._charger.async_unload()

        # Unload tracker.
        await self._tracker.async_unload()
