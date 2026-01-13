"""Solar charger coordinator."""

from asyncio import Task
from datetime import datetime, time, timedelta
import inspect
import logging

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .config_utils import get_device_config_default_value
from .const import (
    CONF_NET_POWER,
    CONF_WAIT_NET_POWER_UPDATE,
    COORDINATOR_STATE_CHARGING,
    COORDINATOR_STATE_STOPPED,
    DOMAIN,
    NUMBER_CHARGE_LIMIT_FRIDAY,
    NUMBER_CHARGE_LIMIT_MONDAY,
    NUMBER_CHARGE_LIMIT_SATURDAY,
    NUMBER_CHARGE_LIMIT_SUNDAY,
    NUMBER_CHARGE_LIMIT_THURSDAY,
    NUMBER_CHARGE_LIMIT_TUESDAY,
    NUMBER_CHARGE_LIMIT_WEDNESDAY,
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT,
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR_LAST_CHECK,
    SENSOR_RUN_STATE,
    SWITCH_START_CHARGE,
    TIME_CHARGE_ENDTIME_FRIDAY,
    TIME_CHARGE_ENDTIME_MONDAY,
    TIME_CHARGE_ENDTIME_SATURDAY,
    TIME_CHARGE_ENDTIME_SUNDAY,
    TIME_CHARGE_ENDTIME_THURSDAY,
    TIME_CHARGE_ENDTIME_TUESDAY,
    TIME_CHARGE_ENDTIME_WEDNESDAY,
)
from .helpers.general import async_set_allocated_power
from .model_control import ChargeControl
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
        self.charge_controls: dict[str, ChargeControl] = {}
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

    # @property
    # def get_run_state(self, charger: ChargerData) -> str:
    #     """Get the current run state."""
    #     if charger.is_running:
    #         return COORDINATOR_STATE_CHARGING
    #     return COORDINATOR_STATE_STOPPED

    def get_run_state(self, control: ChargeControl) -> str:
        """Get charger run state."""
        if control.switch_charge:
            return COORDINATOR_STATE_CHARGING
        return COORDINATOR_STATE_STOPPED

    def is_charging(self, control: ChargeControl) -> bool | None:
        """Return if the charger is currently charging."""
        return control.switch_charge

    # ----------------------------------------------------------------------------
    async def _async_handle_options_update(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Handle options update by reloading the config entry."""

        await hass.config_entries.async_reload(entry.entry_id)

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
            CONF_WAIT_NET_POWER_UPDATE
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

        for control in self.charge_controls.values():
            if control.controller is not None:
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

        for control in self.charge_controls.values():
            if control.controller is not None:
                await control.controller.async_unload()

        for unsub_method in self._unsub:
            unsub_method()
        self._unsub.clear()

    # ----------------------------------------------------------------------------
    # Periodic functions
    # ----------------------------------------------------------------------------
    def _get_net_power(self) -> float | None:
        """Get household net power."""

        # SolarChargerCoordinator: Failed to parse state 'unavailable' for entity 'sensor.main_power_net':
        # could not convert string to float: 'unavailable'

        return self.config_get_entity_number(CONF_NET_POWER)

    # ----------------------------------------------------------------------------
    def _get_total_allocation_pool(self) -> dict[str, float]:
        allocation_pool: dict[str, float] = {}

        for control in self.charge_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            subentry = self._entry.subentries.get(control.subentry_id)
            if subentry:
                allocation_weight = self.option_get_entity_number(
                    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT, subentry
                )
                if allocation_weight is None:
                    raise RuntimeError(
                        f"Cannot get {NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT} for {subentry.unique_id}"
                    )
                allocation_pool[control.subentry_id] = (
                    allocation_weight * control.instance_count
                )
            else:
                # TODO: Need to remove stale control
                allocation_pool[control.subentry_id] = 0

        return allocation_pool

    # ----------------------------------------------------------------------------
    async def _async_allocate_net_power(self) -> None:
        net_power = self._get_net_power()
        if net_power is None:
            _LOGGER.warning("Failed to get net power update. Try again next cycle.")
            return

        pool = self._get_total_allocation_pool()
        total_weight = 0
        for weight in pool.values():
            total_weight = total_weight + weight

        if total_weight > 0:
            for control in self.charge_controls.values():
                # Information only. Global default variable shows net power available for allocation.
                if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                    await async_set_allocated_power(control, net_power)
                    continue

                allocation_weight = pool[control.subentry_id]
                allocated_power = net_power * allocation_weight / total_weight
                await async_set_allocated_power(control, allocated_power)

                _LOGGER.debug(
                    "%s: total_weight=%s, allocation_weight=%s, allocated_power=%s",
                    control.config_name,
                    total_weight,
                    allocation_weight,
                    allocated_power,
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

        # TODO: Should remove last check sensor and following code since not used.
        # Update last check sensor
        for control in self.charge_controls.values():
            if control.sensors:
                control.sensors[SENSOR_LAST_CHECK].set_state(
                    datetime.now().astimezone()
                )

    # ----------------------------------------------------------------------------
    # Coordinator functions
    # ----------------------------------------------------------------------------
    async def async_switch_dummy(self, control: ChargeControl, turn_on: bool) -> None:
        """Dummy switch."""

    # ----------------------------------------------------------------------------
    async def async_start_charger(self, control: ChargeControl) -> None:
        """Start the charger."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        if control and control.controller:
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
                    control.switches[SWITCH_START_CHARGE].turn_off()
                    control.switches[SWITCH_START_CHARGE].update_ha_state()

                if control.sensors:
                    control.sensors[SENSOR_RUN_STATE].set_state(
                        COORDINATOR_STATE_STOPPED
                    )

            if control.sensors:
                control.sensors[SENSOR_RUN_STATE].set_state(COORDINATOR_STATE_CHARGING)
            control.charge_task = await control.controller.async_start_charge()
            control.instance_count = 1
            control.charge_task.add_done_callback(_callback_on_charge_end)

    # ----------------------------------------------------------------------------
    async def async_stop_charger(self, control: ChargeControl) -> None:
        """Stop the charger."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        if control and control.controller:
            if control.charge_task:
                if not control.charge_task.done():
                    if control.end_charge_task:
                        if not control.end_charge_task.done():
                            _LOGGER.debug(
                                "Task %s already running",
                                control.end_charge_task.get_name(),
                            )
                            return

                    control.end_charge_task = control.controller.stop_charge()

    # ----------------------------------------------------------------------------
    async def async_switch_charger(self, control: ChargeControl, start_charge: bool):
        """Called by switch entity to start or stop charge."""

        _LOGGER.debug("Charger %s start charge: %s", control.config_name, start_charge)

        if start_charge:
            if control.switch_charge:
                _LOGGER.error("Charger %s already running", control.config_name)
            else:
                control.switch_charge = True
                await self.async_start_charger(control)
        else:
            if control.switch_charge:
                control.switch_charge = False
                await self.async_stop_charger(control)
            else:
                _LOGGER.error("Charger %s already stopped", control.config_name)

    # ----------------------------------------------------------------------------
    async def async_switch_charger_on(self, control: ChargeControl):
        """Called by button entity to switch on charger."""

        await self.async_switch_charger(control, True)

    # ----------------------------------------------------------------------------
    async def async_switch_schedule_charge(
        self, control: ChargeControl, turn_on: bool
    ) -> None:
        """Schedule charge switch."""

        if control.controller is not None:
            await control.controller.async_switch_schedule_charge(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_plugin_trigger(
        self, control: ChargeControl, turn_on: bool
    ) -> None:
        """Plugin trigger switch."""

        if control.controller is not None:
            await control.controller.async_switch_plugin_trigger(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_sun_elevation_trigger(
        self, control: ChargeControl, turn_on: bool
    ) -> None:
        """Sun elevation trigger switch."""

        if control.controller is not None:
            await control.controller.async_switch_sun_elevation_trigger(turn_on)

    # ----------------------------------------------------------------------------
    async def async_switch_calibrate_max_charge_speed(
        self, control: ChargeControl, turn_on: bool
    ) -> None:
        """Calibrate max charge speed switch."""

        if control.controller is not None:
            await control.controller.async_switch_calibrate_max_charge_speed(turn_on)

    # ----------------------------------------------------------------------------
    async def async_reset_charge_limit_default(self, control: ChargeControl) -> None:
        """Reset charge limit defaults."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # No need for controller for this function.
        # Global defaults subentry has no controller.
        if control:
            subentry = self._entry.subentries.get(control.subentry_id)
            if control.numbers and control.times and subentry:
                _LOGGER.info(
                    "%s: Resetting charge limit and charge end time defaults",
                    control.config_name,
                )

                default_val = get_device_config_default_value(
                    subentry, NUMBER_CHARGE_LIMIT_MONDAY
                )
                await control.numbers[
                    NUMBER_CHARGE_LIMIT_MONDAY
                ].async_set_native_value(default_val)
                await control.times[TIME_CHARGE_ENDTIME_MONDAY].async_set_value(
                    time.min
                )

                default_val = get_device_config_default_value(
                    subentry, NUMBER_CHARGE_LIMIT_TUESDAY
                )
                await control.numbers[
                    NUMBER_CHARGE_LIMIT_TUESDAY
                ].async_set_native_value(default_val)
                await control.times[TIME_CHARGE_ENDTIME_TUESDAY].async_set_value(
                    time.min
                )

                default_val = get_device_config_default_value(
                    subentry, NUMBER_CHARGE_LIMIT_WEDNESDAY
                )
                await control.numbers[
                    NUMBER_CHARGE_LIMIT_WEDNESDAY
                ].async_set_native_value(default_val)
                await control.times[TIME_CHARGE_ENDTIME_WEDNESDAY].async_set_value(
                    time.min
                )

                default_val = get_device_config_default_value(
                    subentry, NUMBER_CHARGE_LIMIT_THURSDAY
                )
                await control.numbers[
                    NUMBER_CHARGE_LIMIT_THURSDAY
                ].async_set_native_value(default_val)
                await control.times[TIME_CHARGE_ENDTIME_THURSDAY].async_set_value(
                    time.min
                )

                default_val = get_device_config_default_value(
                    subentry, NUMBER_CHARGE_LIMIT_FRIDAY
                )
                await control.numbers[
                    NUMBER_CHARGE_LIMIT_FRIDAY
                ].async_set_native_value(default_val)
                await control.times[TIME_CHARGE_ENDTIME_FRIDAY].async_set_value(
                    time.min
                )

                default_val = get_device_config_default_value(
                    subentry, NUMBER_CHARGE_LIMIT_SATURDAY
                )
                await control.numbers[
                    NUMBER_CHARGE_LIMIT_SATURDAY
                ].async_set_native_value(default_val)
                await control.times[TIME_CHARGE_ENDTIME_SATURDAY].async_set_value(
                    time.min
                )

                default_val = get_device_config_default_value(
                    subentry, NUMBER_CHARGE_LIMIT_SUNDAY
                )
                await control.numbers[
                    NUMBER_CHARGE_LIMIT_SUNDAY
                ].async_set_native_value(default_val)
                await control.times[TIME_CHARGE_ENDTIME_SUNDAY].async_set_value(
                    time.min
                )
