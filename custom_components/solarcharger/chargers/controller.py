"""Module to manage the charging process and entity subscriptions."""

import asyncio
from asyncio import Task, timeout
from collections.abc import Callable, Coroutine
from datetime import datetime
import inspect
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import NoEventData

from ..const import (  # noqa: TID252
    COORDINATOR_STATE_CHARGING,
    COORDINATOR_STATE_STOPPED,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
    SENSOR_RUN_STATE,
    SWITCH_CHARGE,
)
from ..model_charge_control import ChargeControl  # noqa: TID252
from ..sc_option_state import ScOptionState  # noqa: TID252
from ..utils import (  # noqa: TID252
    get_is_sun_rising,
    get_sun_elevation,
    log_is_event_loop,
)
from .chargeable import Chargeable
from .charger import Charger
from .solar_charge import SolarCharge
from .tracker import Tracker

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
        self._initialising = True

        self._control = control
        self._charger = charger
        self._chargeable = chargeable
        self._tracker = Tracker(hass, entry, subentry, caller)
        self.solar_charge = SolarCharge(
            hass, entry, subentry, self._tracker, charger, chargeable
        )
        self._charge_task: Task | None = None
        self._end_charge_task: Task | None = None

        self._is_charge_started_by_calibration_switch = False
        self._check_charge_schedule = False

    # ----------------------------------------------------------------------------
    @cached_property
    def charge_control(self) -> ChargeControl:
        """Return the charge control object if applicable."""
        return self._control

    @property
    def is_check_charge_schedule(self) -> bool:
        """Return whether need to check charge schedule."""
        return self._check_charge_schedule

    def set_check_charge_schedule(self, value: bool) -> None:
        """Set whether need to check charge schedule."""
        self._check_charge_schedule = value

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    async def _async_switch_task(self, action: SWITCH_ACTION, turn_on: bool):
        """Start another task to action a switch state when not initialising. The switch must be in the correct state when starting task."""

        if not self._initialising:
            self._hass.loop.create_task(action(turn_on))

    # ----------------------------------------------------------------------------
    def turn_charger_switch(self, turn_on: bool) -> None:
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
                        self.turn_charger_switch(turn_on=True)

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
                new_starttime = self.parse_local_datetime(new_state.state)

                self._tracker.schedule_next_charge_time(
                    new_starttime, self._async_turn_on_charger_switch
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
            if new_state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ) and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                today_index = datetime.now().date().weekday()
                tomorrow_index = (today_index + 1) % 7
                day_index = self.get_charge_limit_entity_ids.get(new_state.entity_id)
                if day_index in (today_index, tomorrow_index):
                    if self._control.instance_count == 0:
                        self._check_charge_schedule = True

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
            if new_state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ) and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                today_index = datetime.now().date().weekday()
                tomorrow_index = (today_index + 1) % 7
                day_index = self.get_charge_endtime_entity_ids.get(new_state.entity_id)
                if day_index in (today_index, tomorrow_index):
                    if self._control.instance_count == 0:
                        self._check_charge_schedule = True

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
    # Switch actions
    # ----------------------------------------------------------------------------
    async def async_switch_schedule_charge(self, turn_on: bool) -> None:
        """Schedule charge switch."""
        _LOGGER.info("%s: Schedule charge: %s", self._caller, turn_on)

        if not self._initialising:
            if turn_on:
                # Trigger is lost on restart, so reschedule if applicable.
                next_charge_time = self.get_datetime(
                    self.next_charge_time_trigger_entity_id
                )
                self._tracker.schedule_next_charge_time(
                    next_charge_time, self._async_turn_on_charger_switch
                )
            else:
                self._tracker.unschedule_next_charge_time()

    # ----------------------------------------------------------------------------
    async def _async_turn_off_plugin_trigger(self) -> None:
        await self.async_turn_switch(
            self.plugin_trigger_switch_entity_id, turn_on=False
        )

    # ----------------------------------------------------------------------------
    async def async_switch_plugin_trigger(self, turn_on: bool) -> None:
        """Plugin trigger switch."""
        _LOGGER.info("%s: Plugin trigger: %s", self._caller, turn_on)

        if not self._initialising:
            if turn_on:
                ok = self._tracker.track_charger_plugged_in_sensor(
                    self.async_handle_plug_in_charger_event
                )
                if not ok:
                    await self._async_turn_off_plugin_trigger()
            else:
                self._tracker.untrack_charger_plugged_in_sensor()

    # ----------------------------------------------------------------------------
    async def async_switch_sun_elevation_trigger(self, turn_on: bool) -> None:
        """Sun elevation trigger switch."""
        _LOGGER.info("%s: Sun elevation trigger: %s", self._caller, turn_on)

        if not self._initialising:
            if turn_on:
                self._tracker.track_sun_elevation(
                    self.async_handle_sun_elevation_update
                )
            else:
                self._tracker.untrack_sun_elevation()

    # ----------------------------------------------------------------------------
    async def _async_switch_calibrate_max_charge_speed(self, turn_on: bool) -> None:
        """Calibrate max charge speed switch."""
        _LOGGER.info("%s: Calibrate max charge speed: %s", self._caller, turn_on)

        if turn_on:
            if self._charge_task is None or self._charge_task.done():
                self._is_charge_started_by_calibration_switch = True
                self.turn_charger_switch(turn_on=True)
        else:
            await self.solar_charge.async_stop_calibrate_max_charge_speed()

            # Will get error message if charger switch already turned off by user.
            if self._is_charge_started_by_calibration_switch:
                self.turn_charger_switch(turn_on=False)

            self._is_charge_started_by_calibration_switch = False

    # ----------------------------------------------------------------------------
    async def async_switch_calibrate_max_charge_speed(self, turn_on: bool) -> None:
        """Calibrate max charge speed switch."""

        await self._async_switch_task(
            self._async_switch_calibrate_max_charge_speed, turn_on
        )

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

        _LOGGER.info("%s: Starting charge task", self._caller)
        self._charge_task = self._hass.async_create_task(
            self._async_start_charge(self._charger, self._chargeable),
            f"{self._caller} charge",
        )
        return self._charge_task

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def _async_abort_charge_task(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Abort charge task."""

        if self._charge_task:
            if not self._charge_task.done():
                self._charge_task.cancel()

                try:
                    await self._charge_task
                except asyncio.CancelledError:
                    _LOGGER.warning(
                        "%s: Aborted charge task",
                        self._caller,
                    )
                except Exception as e:
                    _LOGGER.error(
                        "%s: Error aborting charge task: %s",
                        self._caller,
                        e,
                    )

                await self.solar_charge.async_unload()

            else:
                _LOGGER.info(
                    "%s: Charge task already completed",
                    self._caller,
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
                    await self.solar_charge.async_tidy_up_on_exit(charger, chargeable)
                except Exception as e:
                    _LOGGER.error(
                        "%s: Error stopping charge task: %s",
                        self._caller,
                        e,
                    )
                    await self.solar_charge.async_unload()

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

                _LOGGER.info("%s: Ending charge task", self._caller)
                self._end_charge_task = self._hass.async_create_task(
                    self._async_stop_charge(self._charger, self._chargeable),
                    f"{self._caller} end charge",
                )
                return self._end_charge_task

            _LOGGER.info("Task %s already completed", self._charge_task.get_name())
        else:
            _LOGGER.info("%s: No running charge task to stop", self._caller)
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

                if control.switches:
                    control.switch_charge = False
                    control.switches[SWITCH_CHARGE].turn_off()

                if control.sensors:
                    control.sensors[SENSOR_RUN_STATE].set_state(
                        COORDINATOR_STATE_STOPPED
                    )

            if control.sensors:
                control.sensors[SENSOR_RUN_STATE].set_state(COORDINATOR_STATE_CHARGING)
            control.charge_task = await self.async_start_charge()
            control.instance_count = 1
            control.charge_task.add_done_callback(_callback_on_charge_end)

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
        """Called by switch entity to start or stop charge."""

        _LOGGER.debug("%s: Switch charge on: %s", self._control.config_name, turn_on)

        if turn_on:
            if self._control.switch_charge:
                _LOGGER.error("%s: Charger already running", self._control.config_name)
            else:
                self._control.switch_charge = True
                await self.async_start_charger(self._control)
        else:
            if self._control.switch_charge:
                self._control.switch_charge = False
                await self.async_stop_charger(self._control)
            else:
                _LOGGER.error("%s: Charger already stopped", self._control.config_name)

    # ----------------------------------------------------------------------------
    async def async_switch_charge(self, turn_on: bool):
        """Called by switch entity to start or stop charge."""

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

        # Subscriptions
        self._subscribe_next_charge_time_update()
        self._subscribe_charge_schedule_update()

        # Track next charge time trigger
        await self.async_switch_schedule_charge(self.is_schedule_charge())

        # Track charger plug in
        await self.async_switch_plugin_trigger(self.is_plugin_trigger())

        # Track sun elevation
        await self.async_switch_sun_elevation_trigger(self.is_sun_trigger())

        # Resume charging if it was charging before HA restart
        await self.async_switch_charge(self.is_charge_switch_on())
        await asyncio.sleep(1)

        # Resume charging if it was charging before HA restart
        await self.async_switch_calibrate_max_charge_speed(
            self.is_calibrate_max_charge_speed()
        )

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Async setup of the ChargeController."""

        # Load charger and tracker.
        await self._charger.async_setup()
        await self._tracker.async_setup()

        self._tracker.on_ha_stop(self._async_abort_solar_charger)

        if self._hass.state == CoreState.running:
            await self._async_activate_controller_switches(None)
        else:
            self._tracker.on_ha_started(self._async_activate_controller_switches)

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of the ChargeController."""

        # Abort charge task if running.
        await self._async_abort_solar_charger(None)

        # Unload charger and tracker.
        await self._charger.async_unload()
        await self._tracker.async_unload()
