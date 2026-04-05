"""Solar charger coordinator."""

from datetime import datetime, time, timedelta
import inspect
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .config_utils import get_saved_option_value, get_subentry_id
from .const import (
    CONFIG_NET_POWER,
    CONFIG_WAIT_NET_POWER_UPDATE,
    DEFAULT_CHARGE_LIMIT_MAP,
    DOMAIN,
    ERROR_DEFAULT_CHARGE_LIMIT,
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT,
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR_LAST_CHECK,
    SENSOR_SHARE_ALLOCATION,
    WEEKLY_CHARGE_ENDTIMES,
)
from .helpers.general import async_set_allocated_power
from .model_allocation import PowerAllocation
from .model_charge_control import ChargeControl
from .model_device_control import DeviceControl
from .sc_option_state import ScOptionState
from .utils import log_is_event_loop

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# TODO: Think about running multiple coordinators if multiple chargers are defined.
# See Tesla Custom integration for reference.


class SolarChargerCoordinator(ScOptionState):
    """Coordinator for the Solar Charger."""

    # MODIFIED: Store as datetime object or None
    _last_check_timestamp: datetime | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        global_defaults_subentry: ConfigSubentry,
    ):
        """Initialize the coordinator."""
        self.device_controls: dict[str, DeviceControl] = {}
        self._unsub: list[CALLBACK_TYPE] = []

        ScOptionState.__init__(
            self,
            hass,
            entry,
            global_defaults_subentry,
            caller="SolarChargerCoordinator",
        )

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
    # Setup
    # ----------------------------------------------------------------------------
    def _track_config_options_update(self) -> None:
        """Track options update."""

        subscription = self._entry.add_update_listener(
            self._async_handle_options_update
        )
        self._unsub.append(subscription)

    # ----------------------------------------------------------------------------
    def _track_net_power_update(self) -> None:
        """Track net power update."""

        wait_net_power_update = self.config_get_number_or_abort(
            CONFIG_WAIT_NET_POWER_UPDATE
        )
        _LOGGER.info("wait_net_power_update=%s", wait_net_power_update)

        subscription = async_track_time_interval(
            self._hass,
            self._async_execute_update_cycle,
            timedelta(seconds=wait_net_power_update),
        )

        self._unsub.append(subscription)

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Set up the coordinator and its managed components."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        for control in self.device_controls.values():
            if control.config_name != OPTION_GLOBAL_DEFAULTS_ID:
                # Only setup real chargers with controller
                await control.controller.async_setup()

        # Global default entities MUST be created first before running the coordinator.setup().
        # Otherwise cannot get entity config values here.
        self._track_net_power_update()
        self._track_config_options_update()

    # ----------------------------------------------------------------------------
    # Unload
    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Unload the coordinator and its managed components."""

        for control in self.device_controls.values():
            if control.config_name != OPTION_GLOBAL_DEFAULTS_ID:
                await control.controller.async_unload()

        for unsub_method in self._unsub:
            unsub_method()
        self._unsub.clear()

    # ----------------------------------------------------------------------------
    # Config flow functions
    # ----------------------------------------------------------------------------
    def validate_default_charge_limits(
        self, control: DeviceControl, data: dict[str, Any]
    ) -> bool:
        """Validate default charge limits."""
        ok = True

        min_charge_limit = control.controller.option_get_entity_number_or_abort(
            NUMBER_CHARGEE_MIN_CHARGE_LIMIT
        )
        max_charge_limit = control.controller.option_get_entity_number_or_abort(
            NUMBER_CHARGEE_MAX_CHARGE_LIMIT
        )

        # Check default charge limits
        for day_limit_default in DEFAULT_CHARGE_LIMIT_MAP:
            default_val = data.get(day_limit_default)
            if default_val is None:
                continue

            if not (min_charge_limit <= default_val <= max_charge_limit):
                _LOGGER.error(
                    "%s: Invalid default charge limit %s for %s, min_charge_limit=%s, max_charge_limit=%s",
                    self.caller,
                    default_val,
                    day_limit_default,
                    min_charge_limit,
                    max_charge_limit,
                )
                ok = False
                break

                # Do no raise exception inside the coordinator as it breaks the coordinator loop.
                # Raise exception at source of call instead.
                # raise ValidationExceptionError("base", "invalid_default_charge_limit")

        return ok

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
    # Periodic functions
    # ----------------------------------------------------------------------------
    def _get_net_power(self) -> float | None:
        """Get household net power."""

        # SolarChargerCoordinator: Failed to parse state 'unavailable' for entity 'sensor.main_power_net':
        # could not convert string to float: 'unavailable'

        return self.config_get_entity_number(CONFIG_NET_POWER)

    # ----------------------------------------------------------------------------
    def _get_total_allocation_pool(
        self,
    ) -> tuple[int, float, float, dict[str, PowerAllocation]]:
        """Get allocation pool from options. Note allocation weight entity can be overriden."""

        total_instance = 0
        plan_total_weight = 0
        final_total_weight = 0
        allocations: dict[str, PowerAllocation] = {}

        for control in self.device_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            # Power allocation weight user configurable and can be overridden, so use indirection.
            allocation_weight = control.controller.option_get_entity_number_or_abort(
                NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT
            )

            # Participate in power allocation.
            assert control.controller.charge_control.entities.sensors is not None
            share_allocation = int(
                control.controller.charge_control.entities.sensors[
                    SENSOR_SHARE_ALLOCATION
                ].state
            )

            allocation = PowerAllocation(
                subentry_id=control.subentry_id,
                consumed_power=0,
                max_power=0,
                allocation_weight=allocation_weight,
                share_allocation=share_allocation,
            )

            allocation.plan_weight = (
                allocation_weight * control.controller.charge_control.instance_count
            )
            plan_total_weight += allocation.plan_weight

            allocation.final_weight = allocation.plan_weight * share_allocation
            final_total_weight += allocation.final_weight

            allocations[control.subentry_id] = allocation

            total_instance += control.controller.charge_control.instance_count

        return (total_instance, plan_total_weight, final_total_weight, allocations)

    # ----------------------------------------------------------------------------
    # TODO: Need to take into consideration already allocated power and max power of chargers.

    async def _async_allocate_net_power(self) -> None:
        """Calculate power allocation. Power allocation weight can be 0."""

        net_power = self._get_net_power()
        if net_power is None:
            _LOGGER.warning("Failed to get net power update. Try again next cycle.")
            return

        (total_instance, plan_total_weight, final_total_weight, allocations) = (
            self._get_total_allocation_pool()
        )

        if total_instance > 0:
            for control in self.device_controls.values():
                # Information only. Global default variable shows net power available for allocation.
                if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                    await async_set_allocated_power(
                        control.controller.charge_control, net_power
                    )
                    continue

                allocation = allocations[control.subentry_id]
                if final_total_weight > 0:
                    allocation.final_power = (
                        net_power * allocation.final_weight / final_total_weight
                    )
                else:
                    allocation.final_power = 0

                if plan_total_weight > 0:
                    allocation.plan_power = (
                        net_power * allocation.plan_weight / plan_total_weight
                    )
                else:
                    allocation.plan_power = 0

                # Writer will set entity value directly. Reader will get value via entity ID in options which can be overridden.
                # Paticipants in power sharing will use final_power, non-participants will use plan_power as indication of possible available power.
                await async_set_allocated_power(
                    control.controller.charge_control,
                    allocation.final_power
                    if allocation.share_allocation > 0
                    else allocation.plan_power,
                )

                _LOGGER.debug(
                    "%s: plan_total_weight=%s, final_total_weight=%s, allocation=%s",
                    control.config_name,
                    plan_total_weight,
                    final_total_weight,
                    allocation,
                )
        else:
            _LOGGER.debug(
                "No running charger for net power allocation. Try again next cycle."
            )

    # ----------------------------------------------------------------------------
    # @callback
    async def _async_execute_update_cycle(self, now: datetime) -> None:
        """Execute an update cycle."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # Get datetime in local time zone. HA OS running in UTC timezone.
        # local_timezone=ZoneInfo(hass.config.time_zone)
        self._last_check_timestamp = datetime.now().astimezone()

        #####################################
        # Power allocation
        #####################################
        await self._async_allocate_net_power()

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
                    default_val = get_saved_option_value(
                        self._entry, subentry, day_limit_default, True
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
