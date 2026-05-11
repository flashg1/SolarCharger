# ruff: noqa: TRY401, TID252
"""Solar charger coordinator."""

from datetime import datetime, time, timedelta
import inspect
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import utcnow

from ..chargers.sc_option_state import ScOptionState
from ..config.config_utils import get_subentry_id
from ..const import (
    DEFAULT_CHARGE_LIMIT_MAP,
    DOMAIN,
    ERROR_DEFAULT_CHARGE_LIMIT,
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR_LAST_CHECK,
    SENSOR_SYNC_UPDATE,
    WEEKLY_CHARGE_ENDTIMES,
)

# from ..exceptions.entity_exception import EntityExceptionError
from ..helpers.utils import log_is_event_loop
from ..models.model_charge_control import ChargeControl
from ..models.model_device_control import DeviceControl
from .allocator import PowerAllocator
from .tracker import Tracker

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

PERIODIC_MAINTENANCE_INTERVAL = 60  # 60 seconds

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# TODO: Think about running multiple coordinators if multiple chargers are defined.
# See Tesla Custom integration for reference.


class SolarChargerCoordinator(ScOptionState):
    """Coordinator for the Solar Charger."""

    # Class variable declared outside __init__() are shared by all instances.
    # Important "Shadowing" Warning
    # If you try to modify a class variable through an instance (e.g., instance.class_var = 10),
    # Python creates a new instance variable with that same name for that specific object.
    # This "shadows" the class variable for that instance only, while the actual class variable
    # remains unchanged for everyone else.
    _last_check_timestamp: datetime | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        global_defaults_subentry: ConfigSubentry,
    ):
        """Initialize the coordinator."""
        caller = "Coordinator"

        # Instance variable declared inside __init__() are unique to the instance.
        self.device_controls: dict[str, DeviceControl] = {}
        self._unsub: list[CALLBACK_TYPE] = []

        ScOptionState.__init__(
            self,
            hass,
            entry,
            global_defaults_subentry,
            caller=caller,
        )

        self._tracker = Tracker(hass, entry, global_defaults_subentry, caller)

        # Charge current update period.
        self._current_update_period: float = 0

        # Slightly smaller charge current update period to allow for variation in net power update interval.
        self._min_current_update_period: float = 0

        # Sync charge current time.
        self._sync_charge_current_time: float = 0  # UTC time

    # ----------------------------------------------------------------------------
    @cached_property
    def _device(self) -> dr.DeviceEntry:
        """Get the device entry for the coordinator."""

        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._entry.entry_id)}
        )
        if device is None:
            raise RuntimeError("SolarCharger device entry not found.")
        return device

    # ----------------------------------------------------------------------------
    @property
    def get_last_check_timestamp(self) -> datetime | None:
        """Get the timestamp of the last check cycle."""
        return self._last_check_timestamp

    def is_charging(self, control: ChargeControl) -> bool | None:
        """Return if the charger is currently charging."""
        return control.switch_charge

    # ----------------------------------------------------------------------------
    # Config flow functions
    # ----------------------------------------------------------------------------
    # Charge limit defaults are no longer set in config flow, so no need to check here.
    # Charge limit defaults are now checked when reset charge limit button is pressed.
    # Code left here for reference only, and as example to how to check option values.
    def validate_default_charge_limits(
        self, control: DeviceControl, data: dict[str, Any]
    ) -> bool:
        """Validate default charge limits."""
        # ok = True

        # min_charge_limit = control.controller.option_get_entity_number_or_abort(
        #     NUMBER_CHARGEE_MIN_CHARGE_LIMIT
        # )
        # max_charge_limit = control.controller.option_get_entity_number_or_abort(
        #     NUMBER_CHARGEE_MAX_CHARGE_LIMIT
        # )

        # # Check default charge limits
        # for day_limit_default in DEFAULT_CHARGE_LIMIT_MAP:
        #     # default_val = data.get(day_limit_default)
        #     # if default_val is None:
        #     #     continue
        #     default_val = control.controller.option_get_entity_number_or_abort(
        #         day_limit_default
        #     )

        #     if not (min_charge_limit <= default_val <= max_charge_limit):
        #         _LOGGER.error(
        #             "%s: Invalid default charge limit %s for %s, min_charge_limit=%s, max_charge_limit=%s",
        #             self.caller,
        #             default_val,
        #             day_limit_default,
        #             min_charge_limit,
        #             max_charge_limit,
        #         )
        #         ok = False
        #         break

        #         # Do no raise exception inside the coordinator as it breaks the coordinator loop.
        #         # Raise exception at source of call instead.
        #         # raise ValidationExceptionError("base", "invalid_default_charge_limit")

        # return ok
        return True

    # ----------------------------------------------------------------------------
    def validate_config_options(self, config_name: str, data: dict[str, Any]) -> str:
        """Validate configuration options."""
        error_code = ""

        subentry_id = get_subentry_id(self._entry, config_name)
        if subentry_id:
            control = self.device_controls.get(subentry_id)
            if control:
                if not self.validate_default_charge_limits(control, data):
                    error_code = ERROR_DEFAULT_CHARGE_LIMIT

        return error_code

    # ----------------------------------------------------------------------------
    # Coordinator functions
    # ----------------------------------------------------------------------------
    async def async_switch_dummy(self, control: DeviceControl, turn_on: bool) -> None:
        """Dummy switch."""

    # ----------------------------------------------------------------------------
    async def async_switch_charge(self, control: DeviceControl, turn_on: bool) -> None:
        """Schedule charge switch."""

        if control.controller is not None:
            await control.controller.async_switch_charge(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_schedule_charge(
        self, control: DeviceControl, turn_on: bool
    ) -> None:
        """Schedule charge switch."""

        if control.controller is not None:
            await control.controller.async_switch_schedule_charge(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_plugin_trigger(
        self, control: DeviceControl, turn_on: bool
    ) -> None:
        """Plugin trigger switch."""

        if control.controller is not None:
            await control.controller.async_switch_plugin_trigger(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_presence_trigger(
        self, control: DeviceControl, turn_on: bool
    ) -> None:
        """Device presence trigger switch."""

        if control.controller is not None:
            await control.controller.async_switch_presence_trigger(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_sun_elevation_trigger(
        self, control: DeviceControl, turn_on: bool
    ) -> None:
        """Sun elevation trigger switch."""

        if control.controller is not None:
            await control.controller.async_switch_sun_elevation_trigger(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_calibrate_max_charge_speed(
        self, control: DeviceControl, turn_on: bool
    ) -> None:
        """Calibrate max charge speed switch."""

        if control.controller is not None:
            await control.controller.async_switch_calibrate_max_charge_speed(turn_on)

    # ----------------------------------------------------------------------------
    async def async_reset_charge_limit_default(self, control: DeviceControl) -> None:
        """Reset charge limit defaults."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # Global defaults subentry has controller, but no charger nor chargeable devices.
        if control:
            subentry = self._entry.subentries.get(control.subentry_id)
            if (
                control.controller.charge_control.entities.numbers
                and control.controller.charge_control.entities.times
                and subentry
            ):
                _LOGGER.info(
                    "%s: Resetting charge limit and charge end time defaults",
                    control.config_name,
                )

                min_charge_limit = self.option_get_entity_number_or_abort(
                    NUMBER_CHARGEE_MIN_CHARGE_LIMIT
                )
                max_charge_limit = self.option_get_entity_number_or_abort(
                    NUMBER_CHARGEE_MAX_CHARGE_LIMIT
                )

                # Set charge limits
                for day_limit_default in DEFAULT_CHARGE_LIMIT_MAP:
                    # default_val = get_saved_option_value(
                    #     self._entry, subentry, day_limit_default, True
                    # )
                    default_val = self.option_get_entity_number_or_abort(
                        day_limit_default
                    )

                    day_limit = DEFAULT_CHARGE_LIMIT_MAP[day_limit_default]
                    if (
                        default_val is not None
                        and min_charge_limit <= default_val <= max_charge_limit
                    ):
                        await control.controller.charge_control.entities.numbers[
                            day_limit
                        ].async_set_native_value(default_val)
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
                    await control.controller.charge_control.entities.times[
                        day_endtime
                    ].async_set_value(time.min)

    # ----------------------------------------------------------------------------
    # Config flow
    # ----------------------------------------------------------------------------
    # For some reason, this function has been called twice irrespective of the number of chargers defined.
    # Not sure why? Maybe to ensure the reload is successful?
    # eg. try changing the wait_net_power_update.
    async def _async_handle_options_update(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Handle options update by reloading the config entry."""

        # From AI: Why reload the whole config entry instead of just updating the
        # coordinator or impacted subentries?
        #
        # Answer: Reloading the whole config entry ensures that all changes are
        # applied correctly and consistently across the entire integration. Options
        # can impact multiple subentries and components, and reloading the whole
        # config entry ensures that all components are updated with the new options
        # without having to track which specific components are impacted by which
        # options. Additionally, reloading the whole config entry is not expensive
        # since it only reloads the coordinator and chargers but not the entities,
        # so it provides a good balance between simplicity and performance.

        # await hass.config_entries.async_reload(entry.entry_id)
        hass.config_entries.async_schedule_reload(entry.entry_id)

    # ----------------------------------------------------------------------------
    def _track_config_options_update(self) -> None:
        """Track options update."""

        subscription = self._entry.add_update_listener(
            self._async_handle_options_update
        )
        self._unsub.append(subscription)

    # ----------------------------------------------------------------------------
    # Subscriptions
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
            duration_since_last_sync = (
                new_state.last_changed_timestamp - self._sync_charge_current_time
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
                await self._async_allocate_net_power(utcnow())

                # Synchronise charge current update for all chargers.
                if duration_since_last_sync >= self._min_current_update_period:
                    await self._async_synchronise_charge_current_update(utcnow())

            except Exception as e:
                _LOGGER.exception(
                    "%s: Failed to synchronise charge current update for net power %s W: %s",
                    self.solarcharge.caller,
                    new_state.state,
                    e,
                )

    # ----------------------------------------------------------------------------
    def _track_net_power_update(self) -> None:
        """Track net power update."""

        ok = self._tracker.track_net_power_update(self._async_handle_net_power_update)
        if not ok:
            _LOGGER.error("%s: Invalid net power sensor", self.caller)
            # raise EntityExceptionError("Invalid net power sensor")

    # ----------------------------------------------------------------------------
    # Periodic functions
    # ----------------------------------------------------------------------------
    # @callback
    async def _async_allocate_net_power(self, now: datetime) -> None:
        """Execute an update cycle."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        try:
            await self._allocator.async_allocate_net_power()

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed to allocate net power: %s",
                self.caller,
                e,
            )

    # ----------------------------------------------------------------------------
    # def _start_periodic_power_allocation(self) -> None:
    #     """Start periodic power allocation."""

    #     subscription = async_track_time_interval(
    #         self._hass,
    #         self._async_allocate_net_power,
    #         timedelta(seconds=self._wait_net_power_update),
    #     )

    #     self._unsub.append(subscription)

    # ----------------------------------------------------------------------------
    async def _async_synchronise_charge_current_update(self, now: datetime) -> None:
        """Synchronise charge current update for all chargers."""

        try:
            # Coordinator has global defaults subentry
            control = self.device_controls[self._subentry.subentry_id]

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
    # def _start_periodic_charge_current_update(self) -> None:
    #     """Start periodic charge current update."""

    #     subscription = async_track_time_interval(
    #         self._hass,
    #         self._async_synchronise_charge_current_update,
    #         timedelta(seconds=self._current_update_period),
    #     )

    #     self._unsub.append(subscription)

    # ----------------------------------------------------------------------------
    async def _async_periodic_maintenance(self, now: datetime) -> None:
        """Periodic maintenance."""

        try:
            # Get datetime in local time zone. HA OS running in UTC timezone.
            # local_timezone=ZoneInfo(hass.config.time_zone)
            self._last_check_timestamp = datetime.now().astimezone()

            #####################################
            # TODO: Should remove last check sensor since not used.
            # Update last check sensor
            #####################################
            for control in self.device_controls.values():
                if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                    continue

                assert control.controller.charge_control.entities.sensors is not None
                control.controller.charge_control.entities.sensors[
                    SENSOR_LAST_CHECK
                ].set_state(datetime.now().astimezone())

            #####################################
            # Check to see if need to reschedule charge.
            #####################################
            for control in self.device_controls.values():
                if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                    continue

                await control.controller.async_check_if_need_to_reschedule_charge()

        except Exception as e:
            _LOGGER.exception(
                "%s: Failed periodic maintenance: %s",
                self.caller,
                e,
            )

    # ----------------------------------------------------------------------------
    def _start_periodic_maintenance(self) -> None:
        """Schedule periodic maintenance."""

        subscription = async_track_time_interval(
            self._hass,
            self._async_periodic_maintenance,
            timedelta(seconds=PERIODIC_MAINTENANCE_INTERVAL),
        )

        self._unsub.append(subscription)

    # ----------------------------------------------------------------------------
    # Setup
    # ----------------------------------------------------------------------------
    def _get_min_charge_current_update_period(
        self, current_update_period: float
    ) -> float:

        # Allow for slight variation in net power update interval.
        variation = current_update_period * 5 / 100

        return current_update_period - variation

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Set up the coordinator and its managed components."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        for control in self.device_controls.values():
            if control.config_name != OPTION_GLOBAL_DEFAULTS_ID:
                # Only setup real chargers with controller
                await control.controller.async_setup()

        # device_controls must be initialised first since allocator needs to access device_controls.
        self._allocator = PowerAllocator(self._subentry, self.device_controls)
        self._current_update_period = self.get_charger_current_update_period()
        self._min_current_update_period = self._get_min_charge_current_update_period(
            self._current_update_period
        )

        _LOGGER.info(
            "%s: current_update_period=%s, min_current_update_period=%s",
            self.caller,
            self._current_update_period,
            self._min_current_update_period,
        )

        # Global default entities MUST be created first before running the coordinator.setup().
        # Otherwise cannot get entity config values here.
        await self._tracker.async_setup()

        self._track_net_power_update()

        # self._start_periodic_power_allocation()
        # self._start_periodic_charge_current_update()
        self._start_periodic_maintenance()

        # Enable system config flow callbacks after completing local setup.
        self._track_config_options_update()

    # ----------------------------------------------------------------------------
    # Unload
    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the coordinator and its managed components."""

        for control in self.device_controls.values():
            if control.config_name != OPTION_GLOBAL_DEFAULTS_ID:
                await control.controller.async_unload()

        await self._tracker.async_unload()

        for unsub_method in self._unsub:
            unsub_method()
        self._unsub.clear()
