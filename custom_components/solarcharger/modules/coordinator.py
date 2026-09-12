# ruff: noqa: TRY401, TID252
"""Solar charger coordinator."""

from datetime import datetime, timedelta
import inspect
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

#######################################################
# Do no inherit global defaults ScOptionState or try to use its methods.
# Coordinator is not a charger and has no charger configs.
# eg. Try to reset limit with global defaults subentry device won't work.
#######################################################
# from ..chargers.sc_option_state import ScOptionState
from ..config.config_utils import get_subentry_id
from ..const import (
    ERROR_DEFAULT_CHARGE_LIMIT,
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR_LAST_CHECK,
)

# from ..exceptions.entity_exception import EntityExceptionError
from ..helpers.utils import log_is_event_loop
from ..models.model_charge_control import ChargeControl
from ..models.model_device_control import DeviceControl

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

PERIODIC_MAINTENANCE_INTERVAL = 60  # 60 seconds

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# TODO: Think about running multiple coordinators if multiple chargers are defined.
# See Tesla Custom integration for reference.


class SolarChargerCoordinator:
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
        self._hass = hass
        self._entry = entry
        self._global_defaults_subentry = global_defaults_subentry
        self._caller = "Coordinator"

        # Instance variable declared inside __init__() are unique to the instance.
        self.device_controls: dict[str, DeviceControl] = {}
        self._unsub: list[CALLBACK_TYPE] = []

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
    # Coordinator switch functions
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
    # Coordinator button functions
    # ----------------------------------------------------------------------------
    async def async_reset_charge_limit_default(self, control: DeviceControl) -> None:
        """Reset charge limit defaults."""

        if control.controller is not None:
            await control.controller.async_reset_charge_limit_default()

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
    # Periodic functions
    # ----------------------------------------------------------------------------
    # @callback
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
                    control.controller.check_weather_provider()
                else:
                    await control.controller.async_check_if_need_to_reschedule_charge()

            #####################################
            # Misc
            #####################################

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
    async def async_setup(self) -> None:
        """Set up the coordinator and its managed components."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        for control in self.device_controls.values():
            # Set up both global defaults and charger devices.
            await control.controller.async_setup(self.device_controls)

        # Global default entities MUST be created first before running the coordinator.setup().
        # Otherwise cannot get entity config values here.

        # Update weather sensor now because the one in periodic maintenance is delayed by 60 sec.
        global_defaults_control = self.device_controls[
            self._global_defaults_subentry.subentry_id
        ]
        global_defaults_control.controller.check_weather_provider()

        self._start_periodic_maintenance()

        # Enable system config flow callbacks after completing local setup.
        self._track_config_options_update()

    # ----------------------------------------------------------------------------
    # Unload
    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the coordinator and its managed components."""

        for control in self.device_controls.values():
            # Unload both global defaults and charger devices.
            await control.controller.async_unload()

        for unsub_method in self._unsub:
            unsub_method()
        self._unsub.clear()
