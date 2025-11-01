"""Solar charger coordinator."""

from asyncio import Task
from datetime import datetime, timedelta
import inspect
import logging
from time import time

# from functools import cached_property
from propcache.api import cached_property
from regex import W

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import ATTR_DEVICE_ID
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
    async_track_state_change,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)

from .const import (
    CONF_NET_POWER,
    CONTROL_CHARGER_ALLOCATED_POWER,
    COORDINATOR_STATE_CHARGING,
    COORDINATOR_STATE_STOPPED,
    DOMAIN,
    ENTITY_KEY_CHARGE_SWITCH,
    ENTITY_KEY_LAST_CHECK_SENSOR,
    ENTITY_KEY_RUN_STATE_SENSOR,
    EVENT_ACTION_NEW_CHARGER_LIMITS,
    EVENT_ATTR_ACTION,
    EVENT_ATTR_NEW_LIMITS,
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
    SOLAR_CHARGER_COORDINATOR_EVENT,
)
from .models import ChargeControl
from .sc_option_state import ScOptionState
from .utils import log_is_event_loop

_LOGGER = logging.getLogger(__name__)

# Number of seconds between each check cycle
# EXECUTION_CYCLE_DELAY: int = 1
# EXECUTION_CYCLE_DELAY: int = 3
EXECUTION_CYCLE_DELAY: int = 60

# Number of seconds between each charger update. This setting
# makes sure that the charger is not updated too frequently and
# allows a change of the charger's limit to actually take affect
MIN_CHARGER_UPDATE_DELAY: int = 30


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
        config_entry: ConfigEntry,
        global_defaults_subentry: ConfigSubentry,
    ):
        """Initialize the coordinator."""
        self.hass: HomeAssistant = hass
        self.config_entry: ConfigEntry = config_entry
        # self.global_defaults_subentry: ConfigSubentry = global_defaults_subentry
        self.listeners = []
        self.charge_controls: dict[str, ChargeControl] = {}

        self._unsub: list[CALLBACK_TYPE] = []
        # self._sensors: list[SensorEntity] = []
        # self._buttons: list[ButtonEntity] = []
        # self._switches: list[SwitchEntity] = []
        # self._numbers: list[NumberEntity] = []

        ScOptionState.__init__(
            self, hass, config_entry, global_defaults_subentry, __name__
        )

        # self.entity_id_net_power: str | None = get_parameter(
        #     self.config_entry, CONF_NET_POWER
        # )

        self.entity_id_net_power: str | None = self.config_get_data(CONF_NET_POWER)

    # ----------------------------------------------------------------------------
    @cached_property
    def _device(self) -> dr.DeviceEntry:
        """Get the device entry for the coordinator."""
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.config_entry.entry_id)}
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
    async def _handle_options_update(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Handle options update by reloading the config entry."""
        await hass.config_entries.async_reload(entry.entry_id)

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Set up the coordinator and its managed components."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        for control in self.charge_controls.values():
            if control.controller is not None:
                await control.controller.async_setup()

        self._unsub.append(
            async_track_time_interval(
                self.hass,
                self._execute_update_cycle,
                timedelta(seconds=EXECUTION_CYCLE_DELAY),
            )
        )

        self._unsub.append(
            self.config_entry.add_update_listener(self._handle_options_update)
        )

        # Use for Home Assistant 2024.6 or newer
        # if self.entity_id_net_power:
        #     self._unsub.append(
        #         async_track_state_change_event(
        #             self.hass,
        #             [self.entity_id_net_power],
        #             self.update_sensors_new,
        #         )
        #     )

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
    def _get_net_power(self) -> float | None:
        """Get household net power."""
        return self.config_get_number(CONF_NET_POWER)

    # ----------------------------------------------------------------------------
    def _get_total_allocation_pool(self) -> dict[str, float]:
        allocation_pool: dict[str, float] = {}
        pool = 0
        for control in self.charge_controls.values():
            pool = pool + control.instance_count

        for control in self.charge_controls.values():
            subentry = self.config_entry.subentries.get(control.subentry_id)
            if subentry:
                allocation_weight = self.option_get_number(
                    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT, subentry
                )
                if allocation_weight is None:
                    raise RuntimeError(
                        f"Cannot get {OPTION_CHARGER_POWER_ALLOCATION_WEIGHT} for {subentry.unique_id}"
                    )
                allocation_pool[control.subentry_id] = (
                    allocation_weight * control.instance_count
                )
            else:
                # TODO: Need to remove stale control
                allocation_pool[control.subentry_id] = 0

        return allocation_pool

    # ----------------------------------------------------------------------------
    def _allocate_net_power(self) -> None:
        net_power = self._get_net_power()
        if net_power is None:
            _LOGGER.warning("Failed to get net power data. Try again next cycle.")
            return

        pool = self._get_total_allocation_pool()
        total_weight = 0
        for weight in pool.values():
            total_weight = total_weight + weight

        if total_weight > 0:
            for control in self.charge_controls.values():
                allocation_weight = pool[control.subentry_id]
                allocated_power = net_power * allocation_weight / total_weight
                if control.numbers:
                    control.numbers[CONTROL_CHARGER_ALLOCATED_POWER].set_value(
                        allocated_power
                    )
                _LOGGER.debug(
                    "total_weight=%s, allocation_weight=%s, allocated_power=%s",
                    total_weight,
                    allocation_weight,
                    allocated_power,
                )
        else:
            _LOGGER.debug(
                "No running charger for net power allocation. Try again next cycle."
            )

    # ----------------------------------------------------------------------------
    @callback
    def _execute_update_cycle(self, now: datetime) -> None:
        """Execute an update cycle."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        self._last_check_timestamp = datetime.now().astimezone()
        self._allocate_net_power()

        # self._async_update_sensors()
        # self._async_update_numbers()
        # self._async_update_switches()

        # Run the actual charger update
        for control in self.charge_controls.values():
            if control.sensors:
                control.sensors[ENTITY_KEY_LAST_CHECK_SENSOR].set_state(
                    datetime.now().astimezone()
                )

        # if control.controller:
        #     control.sensor_last_check_timestamp = datetime.now().astimezone()
        #     if control.is_running:
        #         self.async_start_charger(control)
        #         # self._update_charger_if_needed(control, net_current)
        #     elif not control.is_running:
        #         self.async_stop_charger(control)

    # ----------------------------------------------------------------------------
    async def update_sensors_new(
        self,
        # event: Event,  # Event[EventStateChangedData]
        event: Event[EventStateChangedData],
        configuration_updated: bool = False,
    ):  # pylint: disable=unused-argument
        """Sensors have been updated. EventStateChangedData is supported from Home Assistant 2024.5.5."""

        # Allowed from HA 2024.4
        entity_id = event.data["entity_id"]
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]

        await self.update_sensors(
            entity_id=entity_id,
            old_state=old_state,
            new_state=new_state,
            configuration_updated=configuration_updated,
            default_charging_current_updated=False,
        )

    # ----------------------------------------------------------------------------
    async def update_sensors(
        self,
        entity_id: str | None = None,
        old_state: State | None = None,
        new_state: State | None = None,
        configuration_updated: bool = False,
        default_charging_current_updated: bool = False,
    ):  # pylint: disable=unused-argument
        """Sensors have been updated."""

        _LOGGER.debug("SolarChargerCoordinator.update_sensors()")
        _LOGGER.debug("entity_id = %s", entity_id)
        # _LOGGER.debug("old_state = %s", old_state)
        _LOGGER.debug("new_state = %s", new_state)

        # # Update schedule and reset keep_on if EV SOC Target is updated
        # if self.ev_target_soc_entity_id and (entity_id == self.ev_target_soc_entity_id):
        #     configuration_updated = True
        #     self.switch_keep_on_completion_time = None

        # if len(self.ev_target_soc_entity_id) > 0:
        #     ev_target_soc_state = self.hass.states.get(self.ev_target_soc_entity_id)
        #     if Validator.is_soc_state(ev_target_soc_state):
        #         self.ev_target_soc_valid = True
        #         self.sensor.ev_target_soc = ev_target_soc_state.state
        #         self.ev_target_soc = float(ev_target_soc_state.state)

        # time_now_local = dt.now()

        await self.update_state()

    # ----------------------------------------------------------------------------
    async def update_state(self, date_time: datetime | None = None):  # pylint: disable=unused-argument
        """Update the charging status."""
        _LOGGER.debug("SolarChargerCoordinator.update_state()")

        # _LOGGER.debug("turn_on_charging = %s", turn_on_charging)
        # _LOGGER.debug("current_value = %s", current_value)
        # if turn_on_charging and not current_value:
        #     # Turn on charging
        #     self.auto_charging_state = STATE_ON
        #     self.ev_soc_before_last_charging = self.ev_soc
        #     if self.scheduler.get_charging_is_planned():
        #         self.switch_keep_on_completion_time = (
        #             self.scheduler.get_charging_stop_time()
        #         )
        #     await self.turn_on_charging()
        # if not turn_on_charging and current_value:
        #     # Turn off charging
        #     self.auto_charging_state = STATE_OFF
        #     await self.turn_off_charging()

    # ----------------------------------------------------------------------------
    async def switch_charge_update(self, control: ChargeControl, start_charge: bool):
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

            def _callback_on_charge_end(task: Task) -> None:
                """Turn off switch on task exit."""
                if task.cancelled():
                    _LOGGER.warning("Task %s was cancelled", task.get_name())
                elif task.exception():
                    _LOGGER.error(
                        "Task %s failed: %s", task.get_name(), task.exception()
                    )
                else:
                    _LOGGER.info("Task %s completed", task.get_name())
                if control.switches:
                    control.switch_charge = False
                    control.switches[ENTITY_KEY_CHARGE_SWITCH].turn_off()
                    control.switches[ENTITY_KEY_CHARGE_SWITCH].update_ha_state()
                if control.sensors:
                    control.sensors[ENTITY_KEY_RUN_STATE_SENSOR].set_state(
                        COORDINATOR_STATE_STOPPED
                    )
                control.instance_count = 0

            if control.sensors:
                control.sensors[ENTITY_KEY_RUN_STATE_SENSOR].set_state(
                    COORDINATOR_STATE_CHARGING
                )
            control.charge_task = control.controller.start_charge()
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
    # def _update_charger_if_needed(
    #     self, control: ChargeControl, net_current: float
    # ) -> None:
    #     """Update the charger if needed based on net current."""

    #     if not control.switch_charge:
    #         _LOGGER.debug("Charger %s is not running", control.device_name)
    #         return

    #     now = int(time())
    #     if (
    #         control.last_charger_target_update is None
    #         or (now - control.last_charger_target_update[1]) >= MIN_CHARGER_UPDATE_DELAY
    #     ):
    #         self._update_charger_current(control, net_current)
    #     else:
    #         _LOGGER.debug(
    #             "Skipping %s charger update because last update was %s seconds ago",
    #             control.device_name,
    #             now - control.last_charger_target_update[1],
    #         )

    # ----------------------------------------------------------------------------
    # def _update_charger_current(
    #     self, control: ChargeControl, net_current: float
    # ) -> None:
    #     """Update the charger current based on net current."""
    #     now_current = control.charger.get_charge_current()
    #     max_current = control.charger.get_max_charge_current()
    #     new_current = 0.0
    #     if now_current is None or max_current is None:
    #         _LOGGER.warning(
    #             "Invalid current: now_current=%d, max current=%d",
    #             now_current,
    #             max_current,
    #         )
    #         return

    #     new_current = now_current - net_current
    #     if new_current >= max_current:
    #         new_current = max_current
    #     elif new_current < 0:
    #         new_current = 0.0
    #     _LOGGER.debug("New charger settings: %s", new_current)
    #     control.last_charger_target_update = (
    #         new_current,
    #         int(time()),
    #     )
    #     self._emit_charger_event(EVENT_ACTION_NEW_CHARGER_LIMITS, new_current)
    #     self.hass.async_create_task(control.charger.set_charge_current(new_current))

    # ----------------------------------------------------------------------------
    # eg. self._emit_charger_event(EVENT_ACTION_NEW_CHARGER_LIMITS, new_current)

    def _emit_charger_event(self, action: str, new_limits: float) -> None:
        """Emit an event to Home Assistant's device event log."""
        self.hass.bus.async_fire(
            SOLAR_CHARGER_COORDINATOR_EVENT,
            {
                ATTR_DEVICE_ID: self._device.id,
                EVENT_ATTR_ACTION: action,
                EVENT_ATTR_NEW_LIMITS: new_limits,
            },
        )
        _LOGGER.info(
            "Emitted charger event: action=%s, new_limits=%s", action, new_limits
        )

    # ----------------------------------------------------------------------------
    async def init_sensors(self, control: ChargeControl) -> None:
        """Init sensors."""
        return
