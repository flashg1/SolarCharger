# ruff: noqa: TRY401, TID252
"""Solar charge state machine implementation to manage solar charging."""

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
import inspect
import logging
import threading
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import StateType

# Might be of help in the future.
# from homeassistant.helpers.sun import get_astral_event_next
from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..chargers.sc_option_state import ScOptionState
from ..const import (
    DOMAIN,
    ENTITY_CHARGEE_LOCATION_SENSOR,
    ENTITY_CHARGEE_SOC_SENSOR,
    ENTITY_CHARGEE_UPDATE_HA_BUTTON,
    ENTITY_CHARGEE_WAKE_UP_BUTTON,
    ENTITY_CHARGER_CHARGING_SENSOR,
    ENTITY_CHARGER_GET_CHARGE_CURRENT,
    ENTITY_CHARGER_ON_OFF_SWITCH,
    ENTITY_CHARGER_PLUGGED_IN_SENSOR,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    MAX_CONSECUTIVE_FAILURE_COUNT,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MIN_CURRENT,
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
    NUMBER_WAIT_CHARGEE_UPDATE_HA,
    NUMBER_WAIT_CHARGEE_WAKEUP,
    NUMBER_WAIT_CHARGER_OFF,
    NUMBER_WAIT_CHARGER_ON,
    SENSOR_AVERAGE_PAUSE_DURATION,
    SENSOR_CONSUMED_ENERGY_TODAY,
    SENSOR_CONSUMED_POWER,
    SENSOR_LAST_PAUSE_DURATION,
    SENSOR_MEDIAN_NET_ALLOCATED_POWER,
    SENSOR_MEDIAN_NET_ALLOCATED_POWER_PERIOD,
    SENSOR_NET_ALLOCATED_POWER,
    SENSOR_NET_ALLOCATED_POWER_DATA_SET,
    SENSOR_NET_ALLOCATED_POWER_SAMPLE_SIZE,
    SENSOR_PAUSE_COUNT,
    SENSOR_RUN_STATE,
    SENSOR_SELF_PAUSED_TODAY,
    SENSOR_SHARE_ALLOCATION,
    SENSOR_SMA_NET_ALLOCATED_POWER,
    ChargeStatus,
    MedianDataState,
    RunState,
)
from ..helpers.utils import log_is_event_loop
from ..models.model_charge_control import ControlEntities
from ..models.model_charge_stats import ChargeStats
from ..models.model_config import ConfigValueDict
from ..models.model_context_data import ContextData
from ..models.model_median_data import MedianData
from ..models.model_schedule_data import ScheduleData
from ..models.model_state_of_charge import StateOfCharge
from ..modules.tracker import Tracker
from .scheduler import ChargeScheduler
from .solar_charge_state import SolarChargeState
from .state_start import StateStart
from .state_tidyup import StateTidyUp

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarCharge(ScOptionState):
    """Class SolarCharge holds state machine context for solar charging."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        tracker: Tracker,
        entities: ControlEntities,
        charger: Charger,
        chargeable: Chargeable,
        # Used type Any to get around circular reference at one stage.
        # charger: Any,
        # chargeable: Any,
    ) -> None:
        """Initialize the SolarCharge state machine instance."""

        caller = subentry.unique_id
        if caller is None:
            caller = __name__
        ScOptionState.__init__(self, hass, entry, subentry, caller)

        self.tracker = tracker
        self.entities = entities
        self.charger = charger
        self.chargeable = chargeable
        self.scheduler = ChargeScheduler(hass, entry, subentry)

        self.session_start_time = datetime.max
        self.session_triggered_by_timer: bool = False
        self.starting_goal: ScheduleData | None = None
        self.running_goal: ScheduleData | None = None

        self.can_set_current: bool = False

        # self.update_timestamp: float = 0  # utcnow().timestamp()   # UTC time
        # Remember last current for energy calculation and for devices that cannot set current.
        self.last_charge_current: float = 0.0
        # Must reset time before setting current to avoid possible wrong energy calculation after pause period.
        # Specifically for devices with on/off switch and max current only, ie. cannot set 0 current.
        self.charge_current_updatetime: datetime = datetime.min

        self.soc_updates: list[StateOfCharge] = []
        self.started_calibrate_max_charge_speed: bool = False

        # Power monitor duration in seconds
        self.power_monitor_duration: float = 0.0
        # net allocation = new allocation - consumed power
        self.net_allocations: MedianData | None = None

        self.stats = ChargeStats()
        self.started_max_charge: int = 0

        # Use semaphore to ensure that only one thread can update update_ha_task_count and only one task running.
        self._semaphore_update_ha_task = threading.Semaphore(value=1)
        self._semaphore_update_ha_task_count: int = 0

        self.charge_current_update_period = self.get_charger_current_update_period()

        # Entity backed by variable for efficiency. Ok if re-direction is not required.
        self._share_allocation: int = 0
        self._consumed_power: float = 0.0
        self._self_paused: bool = False

        # Initialise state machine self._state variable.
        self.set_machine_state(StateStart())

    # ----------------------------------------------------------------------------
    @cached_property
    def _device(self) -> dr.DeviceEntry:
        """Get the device entry for the controller."""
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._subentry.subentry_id)}
        )
        if device is None:
            raise RuntimeError(f"{self.caller} device entry not found.")
        return device

    # ----------------------------------------------------------------------------
    @property
    def is_chargeable(self) -> bool:
        """Return True if the charger is chargeable."""
        return isinstance(self.charger, Chargeable)

    @property
    def get_chargee(self) -> Chargeable | None:
        """Return the chargeable device if applicable."""
        if self.is_chargeable:
            return self.charger  # type: ignore[return-value]
        return None

    @property
    def machine_state(self) -> SolarChargeState:
        """Return the current state of the machine."""
        return self._machine_state

    @property
    def is_self_paused(self) -> bool:
        """Return True if the charger is self-paused."""
        return self._self_paused

    # ----------------------------------------------------------------------------
    # State machine methods
    # ----------------------------------------------------------------------------
    def set_machine_state(self, state: SolarChargeState):
        """Method to change the state of the object."""

        self._machine_state = state
        self._machine_state.solarcharge = self

    # ----------------------------------------------------------------------------
    async def async_action_state(self):
        """Method for executing device functionality depending on current state of the object."""

        await self.machine_state.async_activate_state()

    # ----------------------------------------------------------------------------
    def get_state_classname(self) -> str:
        """Get current state name of object."""

        return type(self.machine_state).__name__

    # ----------------------------------------------------------------------------
    def set_run_state(self, state: RunState) -> None:
        """Set the run state of the object."""

        assert self.entities.sensors is not None
        self.entities.sensors[SENSOR_RUN_STATE].set_state(state.value)

    # ----------------------------------------------------------------------------
    def set_self_paused(self, self_paused: bool) -> None:
        """Set the self-paused state of the object."""

        self._self_paused = self_paused

    # ----------------------------------------------------------------------------
    # Global utils
    # ----------------------------------------------------------------------------
    def get_number_state(
        self, config_item: str
    ) -> StateType | date | datetime | Decimal:
        """Get number state."""

        assert self.entities.numbers is not None
        return self.entities.numbers[config_item].state

    # ----------------------------------------------------------------------------
    def get_sensor_state(
        self, config_item: str
    ) -> StateType | date | datetime | Decimal:
        """Get sensor state."""

        assert self.entities.sensors is not None

        # I think need to know the type and cast the type if using state.
        # return self.entities.sensors[config_item].state

        return self.entities.sensors[config_item].get_state()

    # ----------------------------------------------------------------------------
    def update_sensor(
        self,
        config_item: str,
        new_state: StateType | date | datetime | Decimal,
    ) -> None:
        """Update sensor."""

        assert self.entities.sensors is not None
        self.entities.sensors[config_item].set_state(new_state)

    # ----------------------------------------------------------------------------
    def set_median_data_not_ready(self, data: MedianData) -> None:
        """Set the median data set not ready."""

        data.data_set_ready = False
        self.update_sensor(
            SENSOR_NET_ALLOCATED_POWER_DATA_SET, MedianDataState.NOT_READY.value
        )

    # ----------------------------------------------------------------------------
    def set_median_data_ready(self, data: MedianData) -> None:
        """Set the median data set ready."""

        data.data_set_ready = True
        self.update_sensor(
            SENSOR_NET_ALLOCATED_POWER_DATA_SET, MedianDataState.READY.value
        )

    # ----------------------------------------------------------------------------
    def participate_in_real_power_allocation(self) -> None:
        """Participate in real power allocation."""

        self._share_allocation = 1
        self.update_sensor(SENSOR_SHARE_ALLOCATION, 1)

    # ----------------------------------------------------------------------------
    def give_up_real_power_allocation(self) -> None:
        """Participate in real power allocation."""

        self._share_allocation = 0
        self.update_sensor(SENSOR_SHARE_ALLOCATION, 0)

    # ----------------------------------------------------------------------------
    def get_share_allocation(self) -> int:
        """Get share allocation."""

        return self._share_allocation

    # ----------------------------------------------------------------------------
    def set_net_allocated_power(self, val: float) -> None:
        """Set net allocated power."""

        self.update_sensor(SENSOR_NET_ALLOCATED_POWER, val)

    # ----------------------------------------------------------------------------
    def set_net_allocated_power_sample_size(self, val: int) -> None:
        """Set net allocated power sample size."""

        self.update_sensor(SENSOR_NET_ALLOCATED_POWER_SAMPLE_SIZE, val)

    # ----------------------------------------------------------------------------
    def set_median_net_allocated_power(self, val: float) -> None:
        """Set median net allocated power."""

        self.update_sensor(SENSOR_MEDIAN_NET_ALLOCATED_POWER, val)

    # ----------------------------------------------------------------------------
    def set_median_net_allocated_power_period(self, val: float) -> None:
        """Set median net allocated power period."""

        self.update_sensor(SENSOR_MEDIAN_NET_ALLOCATED_POWER_PERIOD, val)

    # ----------------------------------------------------------------------------
    def set_sma_net_allocated_power(self, val: float) -> None:
        """Set SMA net allocated power."""

        self.update_sensor(SENSOR_SMA_NET_ALLOCATED_POWER, val)

    # ----------------------------------------------------------------------------
    def set_consumed_power(self, val: float) -> None:
        """Set consumed power."""

        self._consumed_power = val
        self.update_sensor(SENSOR_CONSUMED_POWER, val)

    # ----------------------------------------------------------------------------
    # Commented out get_consumed_power() in sc_option_state.py.
    def get_consumed_power(self) -> float:
        """Get consumed power."""

        # return self.get_sensor_state(SENSOR_CONSUMED_POWER)
        return self._consumed_power

    # ----------------------------------------------------------------------------
    def set_consumed_energy_today(self, val: float) -> None:
        """Set consumed energy today."""

        self.update_sensor(SENSOR_CONSUMED_ENERGY_TODAY, val)

    # ----------------------------------------------------------------------------
    def set_self_paused_today(self, val: int) -> None:
        """Set self-paused today."""

        self.update_sensor(SENSOR_SELF_PAUSED_TODAY, val)

    # ----------------------------------------------------------------------------
    def set_pause_count(self, val: int) -> None:
        """Set pause count."""

        self.update_sensor(SENSOR_PAUSE_COUNT, val)

    # ----------------------------------------------------------------------------
    def set_last_pause_duration(self, val: timedelta) -> None:
        """Set last pause duration."""

        # native_unit_of_measurement=UnitOfTime.MINUTES
        self.update_sensor(SENSOR_LAST_PAUSE_DURATION, val.total_seconds() / 60)

    # ----------------------------------------------------------------------------
    def set_average_pause_duration(self, val: timedelta) -> None:
        """Set average pause duration."""

        # native_unit_of_measurement=UnitOfTime.MINUTES
        self.update_sensor(SENSOR_AVERAGE_PAUSE_DURATION, val.total_seconds() / 60)

    # ----------------------------------------------------------------------------
    def set_pause_stats(self, val: ChargeStats) -> None:
        """Set pause stats."""

        self.set_pause_count(val.pause_total_count)
        self.set_last_pause_duration(val.pause_last_duration)
        self.set_average_pause_duration(val.pause_average_duration)

    # ----------------------------------------------------------------------------
    async def async_charger_sleep(self) -> None:
        """Wait before looping again."""

        await asyncio.sleep(self.charge_current_update_period)

    # ----------------------------------------------------------------------------
    # Local utils
    # ----------------------------------------------------------------------------
    async def _async_wakeup_device(self, chargeable: Chargeable) -> None:
        config_item = ENTITY_CHARGEE_WAKE_UP_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_wake_up(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self.async_option_sleep(NUMBER_WAIT_CHARGEE_WAKEUP)

    # ----------------------------------------------------------------------------
    async def _async_poll_charger_update(self, wait_after_update: bool) -> None:
        """Poll charger for update using charger switch entity since every charger must have one."""

        charger_entity = self.option_get_id(ENTITY_CHARGER_ON_OFF_SWITCH)
        if charger_entity:
            await self.async_poll_entity_id(charger_entity)
            if wait_after_update:
                await self.async_option_sleep(NUMBER_WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    # Handle SOC update for calibrating max charge speed
    # ----------------------------------------------------------------------------
    async def async_stop_calibrate_max_charge_speed(self) -> None:
        """Stop tracking SOC and reset flag."""

        self.tracker.untrack_soc_sensor()
        self.started_calibrate_max_charge_speed = False

    # ----------------------------------------------------------------------------
    async def async_turn_off_calibrate_max_charge_speed_switch(self) -> None:
        """Turn off switch if on."""

        if self.is_calibrate_max_charge_speed():
            await self.async_stop_calibrate_max_charge_speed()
            await self.async_turn_switch(
                self.calibrate_max_charge_speed_switch_entity_id, turn_on=False
            )

    # ----------------------------------------------------------------------------
    # Common code
    # ----------------------------------------------------------------------------
    async def async_update_ha(
        self, chargeable: Chargeable, wait_after_update: bool = True
    ) -> None:
        """Get third party integration to update HA with latest data."""

        try:
            if self.is_poll_charger_update():
                await self._async_poll_charger_update(wait_after_update)
            else:
                config_item = ENTITY_CHARGEE_UPDATE_HA_BUTTON
                val_dict = ConfigValueDict(config_item, {})

                await chargeable.async_update_ha(val_dict)
                if val_dict.config_values[config_item].entity_id is not None:
                    if wait_after_update:
                        await self.async_option_sleep(NUMBER_WAIT_CHARGEE_UPDATE_HA)

        except Exception as e:
            _LOGGER.exception("%s: Error updating HA: %s", self.caller, e)

    # ----------------------------------------------------------------------------
    def is_at_location(self, chargeable: Chargeable) -> bool:
        """Is chargeable device at charger location? Always return true if sensor not defined."""

        config_item = ENTITY_CHARGEE_LOCATION_SENSOR
        val_dict = ConfigValueDict(config_item, {})

        is_at_location = chargeable.is_at_location(val_dict)
        if val_dict.config_values[config_item].entity_id is None:
            is_at_location = True

        return is_at_location

    # ----------------------------------------------------------------------------
    def is_really_connected(self, charger: Charger) -> bool:
        """Is charger connected to chargeable device? Returns false if sensor is not defined."""

        return charger.is_connected()

    # ----------------------------------------------------------------------------
    def is_connected(self, charger: Charger) -> bool:
        """Is charger connected to chargeable device? Returns true if sensor is not defined."""

        config_item = ENTITY_CHARGER_PLUGGED_IN_SENSOR
        val_dict = ConfigValueDict(config_item, {})

        is_connected = charger.is_connected(val_dict)
        if val_dict.config_values[config_item].entity_id is None:
            is_connected = True

        return is_connected

    # ----------------------------------------------------------------------------
    async def async_wake_up_and_update_ha(self, chargeable: Chargeable) -> None:
        """Wake up device and update HA."""

        await self._async_wakeup_device(chargeable)
        await self.async_update_ha(chargeable)

    # ----------------------------------------------------------------------------
    async def async_turn_charger_switch(self, charger: Charger, turn_on: bool) -> None:
        """Turn charger switch on or off."""

        if turn_on:
            switched_on = charger.is_charger_switch_on()
            if not switched_on:
                await charger.async_turn_charger_switch(turn_on)
                await self.async_option_sleep(NUMBER_WAIT_CHARGER_ON)
        else:
            await charger.async_turn_charger_switch(turn_on)
            await self.async_option_sleep(NUMBER_WAIT_CHARGER_OFF)

    # ----------------------------------------------------------------------------
    def can_set_charge_current(self) -> bool:
        """Check if charger has ability to set charge current."""

        return self.charger.can_set_charge_current()

    # ----------------------------------------------------------------------------
    def get_charger_max_current(self) -> float:
        """Get charger max current."""

        max_current = self.charger.get_max_charge_current()
        if max_current is None or max_current <= 0:
            raise ValueError("Failed to get charger max current")

        return max_current

    # ----------------------------------------------------------------------------
    def validate_current(
        self, current: float, max_current: float | None = None
    ) -> float:
        """Validate charge current is within charger supported range."""

        if max_current is None:
            max_current = self.get_charger_max_current()

        if current < 0:
            current = 0
        elif current > max_current:
            current = max_current

        return current

    # ----------------------------------------------------------------------------
    def get_charger_min_current(
        self, max_current: float | None = None, direct: bool = False
    ) -> float:
        """Get charger min current."""

        if direct:
            config_min_current = self.get_number_state(NUMBER_CHARGER_MIN_CURRENT)
        else:
            config_min_current = self.option_get_entity_number_or_abort(
                NUMBER_CHARGER_MIN_CURRENT
            )

        return self.validate_current(config_min_current, max_current)

    # ----------------------------------------------------------------------------
    def get_charger_effective_voltage(self) -> float:
        """Get charger effective voltage."""

        charger_effective_voltage = self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_EFFECTIVE_VOLTAGE
        )
        if charger_effective_voltage <= 0:
            raise ValueError(
                f"Invalid charger effective voltage {charger_effective_voltage}"
            )

        return charger_effective_voltage

    # ----------------------------------------------------------------------------
    def get_charge_current(
        self, charger: Charger, val_dict: ConfigValueDict | None = None
    ) -> float:
        """Get charge current. Return max current if device do not support reading current."""

        config_item = ENTITY_CHARGER_GET_CHARGE_CURRENT
        if val_dict is None:
            val_dict = ConfigValueDict(config_item, {})

        charge_current = charger.get_charge_current(val_dict)
        if val_dict.config_values[config_item].entity_id is None:
            # Device do not support reading current, eg. a resistive load.
            # So just return charger_max_current.
            # All devices must have max charge current configured.
            charge_current = self.get_charger_max_current()

        if charge_current is None:
            raise ValueError("Failed to get device charge current")

        return charge_current

    # ----------------------------------------------------------------------------
    async def async_set_charge_current(
        self, charger: Charger, new_current: float, old_current: float | None = None
    ) -> None:
        """Set charge current."""

        try:
            #####################################
            # Get old charge current
            #####################################
            if old_current is None:
                old_charge_current = self.last_charge_current
            else:
                old_charge_current = old_current

            # How do we know the status of charger on/off switch is up-to-date?
            # We can't unless do another poll. So just to set the current.
            # Set current=0 if charger is switched off.
            # eg. automatically switched off by car after reaching charge limit.
            # switched_on = charger.is_charger_switch_on()
            # if not switched_on:
            #     current = 0

            #####################################
            # Set new charge current
            #####################################
            if self.can_set_current:
                if new_current != old_charge_current:
                    # Only set current if different from old.
                    _LOGGER.info(
                        "%s: Update current from %s to %s",
                        self.caller,
                        old_charge_current,
                        new_current,
                    )
                    new_charge_current = await charger.async_set_charge_current(
                        new_current
                    )
                    self.emit_solarcharger_event(
                        self._device.id,
                        EVENT_ACTION_NEW_CHARGE_CURRENT,
                        new_charge_current,
                        old_charge_current,
                    )

                else:
                    new_charge_current = new_current

            # Device do not support setting current.
            # So new current is either 0 or max current.
            else:
                new_charge_current = new_current

            # Can lose a bit for energy calculation if device set current=0 by itself, so save new current.
            self.last_charge_current = new_charge_current

            #####################################
            # Set current update time
            #####################################
            now_time = self.get_local_datetime()
            old_charge_current_duration = (
                timedelta.min
                if self.charge_current_updatetime == datetime.min
                else now_time - self.charge_current_updatetime
            )
            self.charge_current_updatetime = now_time

            #####################################
            # Set energy consumed since last current update
            #####################################
            old_consumed_power = self.get_consumed_power()
            if old_consumed_power > 0 and old_charge_current_duration != timedelta.min:
                # Energy in kWh = Power in kW * time in hours
                consumed_energy_last_period = (old_consumed_power / 1000) * (
                    old_charge_current_duration.total_seconds() / 3600
                )
                consumed_energy_today = self.get_consumed_energy_today()
                consumed_energy_today += consumed_energy_last_period
                self.set_consumed_energy_today(consumed_energy_today)

            #####################################
            # Set consumed power
            #####################################
            effective_voltage = self.get_charger_effective_voltage()
            self.set_consumed_power(new_charge_current * effective_voltage)

            # Do not hold up callback
            # if self.can_set_current:
            #     await self.async_option_sleep(NUMBER_WAIT_CHARGER_AMP_CHANGE)

        except Exception as e:
            _LOGGER.exception(
                "%s: Error setting charge current %s A: %s", self.caller, new_current, e
            )

    # ----------------------------------------------------------------------------
    async def async_turn_off_charger(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Turn off charger."""

        switched_on = charger.is_charger_switch_on()
        if switched_on:
            await self.async_set_charge_current(charger, 0)
            await self.async_turn_charger_switch(charger, turn_on=False)
            await self.async_update_ha(chargeable)

        # Must reset time here to avoid possible wrong energy calculation if pausing.
        self.charge_current_updatetime = datetime.min
        self.set_self_paused(False)

    # ----------------------------------------------------------------------------
    async def async_set_charge_limit(
        self, chargeable: Chargeable, charge_limit: float
    ) -> None:
        """Set charge limit."""

        await chargeable.async_set_charge_limit(charge_limit)
        await self.async_option_sleep(NUMBER_WAIT_CHARGEE_LIMIT_CHANGE)

    # ----------------------------------------------------------------------------
    async def async_set_charge_limit_if_required(
        self, chargeable: Chargeable, goal: ScheduleData
    ) -> bool:
        """Set new charge limit if changed, otherwise use existing charge limit."""

        if charge_limit_changed := (goal.old_charge_limit != goal.new_charge_limit):
            _LOGGER.warning(
                "%s: Changing charge limit from %.1f %% to %.1f %% for %s",
                self.caller,
                goal.old_charge_limit,
                goal.new_charge_limit,
                # now_time.strftime("%A"),
                goal.weekly_schedule[goal.day_index].charge_day,
            )
            await self.async_set_charge_limit(chargeable, goal.new_charge_limit)

        return charge_limit_changed

    # ----------------------------------------------------------------------------
    def is_below_charge_limit(self, chargeable: Chargeable) -> bool:
        """Is device SOC below charge limit? Always return true if SOC entity ID is not defined."""

        is_below_limit = True

        try:
            charge_limit = chargeable.get_charge_limit()

            config_item = ENTITY_CHARGEE_SOC_SENSOR
            val_dict = ConfigValueDict(config_item, {})
            soc = chargeable.get_state_of_charge(val_dict)
            if val_dict.config_values[config_item].entity_id is None:
                return True

            if soc is not None and charge_limit is not None:
                is_below_limit = soc < charge_limit

        except TimeoutError as e:
            _LOGGER.warning(
                "%s: Timeout getting SOC or charge limit: %s",
                self.caller,
                e,
            )
        except Exception as e:
            _LOGGER.exception(
                "%s: Error getting SOC or charge limit: %s",
                self.caller,
                e,
            )

        return is_below_limit

    # ----------------------------------------------------------------------------
    def is_charging(
        self, charger: Charger, val_dict: ConfigValueDict | None = None
    ) -> bool:
        """Is charger currently charging? Always return false in case of error."""

        config_item = ENTITY_CHARGER_CHARGING_SENSOR
        val_dict = ConfigValueDict(config_item, {}) if val_dict is None else val_dict
        is_charging = charger.is_charging(val_dict=val_dict)

        # If there is no charging sensor defined, then use the next best thing,
        # ie. use charger switch state to determine whether charger is charging or not.
        if val_dict.config_values[config_item].entity_id is None:
            is_charging = charger.is_charger_switch_on()

        return is_charging

    # ----------------------------------------------------------------------------
    def is_max_speed_charge(self) -> bool:
        """Check if charge at max speed?"""
        max_speed_charge = False

        max_current = self.get_charger_max_current()
        min_current = self.get_charger_min_current(max_current)

        if (
            # If device cannot set current, then ignore this condition.
            # (min_current == max_current and self.can_set_current)
            # Time-based min current using template helper.
            (min_current == max_current)
            # Note running goal is updated in both charging and paused states.
            or (
                # Running goal is not ready to the allocator for a brief period.
                self.running_goal is not None
                and self.running_goal.has_charge_endtime
                and self.running_goal.max_charge_now
            )
            or self.is_fast_charge_mode()
            or self.is_calibrate_max_charge_speed()
        ):
            max_speed_charge = True

        return max_speed_charge

    # ----------------------------------------------------------------------------
    def _is_allow_pause_state(self) -> bool:
        """Check if charger is allowed to go into pause state."""
        allow_pause_state = False

        if self.power_monitor_duration > 0:
            # Yes, monitor config switched on.
            allow_pause_state = True

            if self.is_max_speed_charge():
                allow_pause_state = False

        return allow_pause_state

    # ----------------------------------------------------------------------------
    # Machine state functions
    # ----------------------------------------------------------------------------
    def log_context(self, context: ContextData) -> None:
        """Log context data."""

        _LOGGER.warning("%s: ContextData: %s", self.caller, context)

    # ----------------------------------------------------------------------------
    def _log_power_allocations(self, context: ContextData) -> None:
        """Log power allocations."""

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "%s: Net allocated power median data: %s",
                self.caller,
                context.net_allocations,
            )

    # ----------------------------------------------------------------------------
    def _get_context(
        self,
        charger: Charger,
        chargeable: Chargeable,
        state: RunState,
        goal: ScheduleData,
        net_allocations: MedianData,
        stats: ChargeStats,
    ) -> ContextData:
        """Get charging information context."""

        # Init variables
        context = ContextData(charger, chargeable, state, goal, net_allocations, stats)

        context.connected = self.is_connected(charger)

        # Device charge limit must have already been set before this check.
        context.below_charge_limit = self.is_below_charge_limit(chargeable)

        val_dict = ConfigValueDict(ENTITY_CHARGER_CHARGING_SENSOR, {})
        context.charging = self.is_charging(charger, val_dict=val_dict)
        context.charging_status = val_dict.config_values[
            ENTITY_CHARGER_CHARGING_SENSOR
        ].entity_value

        context.fast_charge = self.is_fast_charge_mode()
        context.calibrate_max_charge_speed = self.is_calibrate_max_charge_speed()

        self._log_power_allocations(context)

        return context

    # ----------------------------------------------------------------------------
    def get_adjusted_activation_power(self, run_state: RunState) -> tuple[float, float]:
        """Get adjusted activation power based on min workable current."""

        charger_min_workable_current = self.get_charger_min_workable_current()
        charger_effective_voltage = self.get_charger_effective_voltage()

        # Note surplus power is negative.
        activation_power = charger_min_workable_current * charger_effective_voltage * -1

        #######################################################
        # Raise the bar by extra percentage to avoid borderline cases where the charger might keep switching on and off.
        #######################################################
        # If device cannot set current, do not raise the requirement for enter/exit pause state because
        # net allocated power is already at max power.
        # In fact, lower the activation power to allow for power variation caused by voltage variation.
        # Min workable current enter pause percent = -10% (ie. hard to change from charging to pause state)
        # Min workable current exit pause percent = -5% (ie. harder to change from paused to charging state)
        #
        # If device can set current, make it harder to exit pause state by raising the requirement to exit pause state.
        # Min workable current enter pause percent = 0%
        # Min workable current exit pause percent = 10% (ie. harder to change from paused to charging state)
        if run_state == RunState.PAUSED:
            #####################################
            # For exiting out of paused state.
            #####################################
            # Device is currently paused.
            extra_percent = self.get_charger_min_workable_current_exit_pause_percent()
            adjusted_activation_power = activation_power * (100 + extra_percent) / 100

        else:
            #####################################
            # For entering pause state.
            #####################################
            # Device is currently charging.
            extra_percent = self.get_charger_min_workable_current_enter_pause_percent()
            adjusted_activation_power = activation_power * (100 + extra_percent) / 100

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "%s: run_state=%s, adjusted_activation_power=%s (%s), extra_percent=%s",
                self.caller,
                run_state,
                adjusted_activation_power,
                activation_power,
                extra_percent,
            )

        return (adjusted_activation_power, activation_power)

    # ----------------------------------------------------------------------------
    def _is_median_net_allocated_power_more_than_min_workable_power(
        self,
        net_allocations: MedianData,
        run_state: RunState,
    ) -> bool:
        """Is median net allocated power more than minimum workable power? None=not enough data."""
        is_enough_power = None

        if net_allocations.window_seconds > 0 and net_allocations.data_set_ready:
            net_allocated_power = net_allocations.last_data_point.value
            median_net_allocated_power = net_allocations.median_value
            adjusted_activation_power, _ = self.get_adjusted_activation_power(run_state)

            if run_state == RunState.PAUSED:
                #####################################
                # For exiting out of paused state.
                #####################################
                # Device is currently paused.
                # Note surplus power is negative.
                is_enough_power = (
                    median_net_allocated_power <= adjusted_activation_power
                )
            else:
                #####################################
                # For entering pause state.
                #####################################
                # Device is currently charging.
                # Note surplus power is negative.
                is_enough_power = (
                    median_net_allocated_power <= adjusted_activation_power
                    # Make it harder to go into pause state if near realtime net_allocated_power has enough power.
                    or net_allocated_power <= adjusted_activation_power
                )

        return is_enough_power

    # ----------------------------------------------------------------------------
    def _set_is_continue_charge_state(self, context: ContextData) -> None:
        """Is continue charge state?"""

        context.next_step = ChargeStatus.CHARGE_CONTINUE
        context.continue_state = True

        # Charge just-in-time feature:
        # If end time is set, charge can still stop at end elevation trigger,
        # and then start again closer to end time to complete charge.
        continue_charge = (
            context.connected
            and context.below_charge_limit
            and (
                not context.goal.end_on_max_consumed_energy
                or context.goal.below_max_consumed_energy
            )
            and (context.stats.loop_success_count == 0 or context.charging)
            and (
                not context.goal.sun_trigger  # Sun trigger off, continue.
                or context.goal.sun_above_start_end_elevations  # Sun trigger on, continue if between start and end elevations.
                or context.fast_charge
                or context.calibrate_max_charge_speed
                or (context.goal.has_charge_endtime and context.goal.max_charge_now)
            )
        )

        if continue_charge:
            if self._is_allow_pause_state():
                context.enough_power = (
                    self._is_median_net_allocated_power_more_than_min_workable_power(
                        context.net_allocations, context.state
                    )
                )

                if context.enough_power is not None and not context.enough_power:
                    context.next_step = ChargeStatus.CHARGE_PAUSE
                    context.continue_state = False
        else:
            context.next_step = ChargeStatus.CHARGE_END
            context.continue_state = False

    # ----------------------------------------------------------------------------
    def _set_is_continue_pause_state(self, context: ContextData) -> None:
        """Is continue pause state?"""

        context.next_step = ChargeStatus.CHARGE_CONTINUE
        context.continue_state = False

        continue_pause = (
            context.connected
            and (
                not context.goal.end_on_max_consumed_energy
                or context.goal.below_max_consumed_energy
            )
            and (
                not context.goal.sun_trigger
                or context.goal.sun_above_start_end_elevations
            )
            and not context.fast_charge
            and not context.calibrate_max_charge_speed
            and not (context.goal.has_charge_endtime and context.goal.max_charge_now)
        )

        if continue_pause:
            if self._is_allow_pause_state():
                context.enough_power = (
                    self._is_median_net_allocated_power_more_than_min_workable_power(
                        context.net_allocations, context.state
                    )
                )

                if context.enough_power is None or not context.enough_power:
                    context.next_step = ChargeStatus.CHARGE_PAUSE
                    context.continue_state = True

    # ----------------------------------------------------------------------------
    def _set_is_continue_state(
        self,
        context: ContextData,
    ) -> None:
        """Check if to continue state."""

        if context.state == RunState.CHARGING:
            self._set_is_continue_charge_state(context)
        elif context.state == RunState.PAUSED:
            self._set_is_continue_pause_state(context)

    # ----------------------------------------------------------------------------
    async def async_set_charge_status(
        self,
        charger: Charger,
        chargeable: Chargeable,
        state: RunState,
        stats: ChargeStats,
    ) -> ContextData:
        """Get latest context and determine next step."""

        # Get schedule data at start of each loop since schedule might change while charging.
        self.running_goal = await self.scheduler.async_get_schedule_data(
            chargeable,
            timer_session=self.session_triggered_by_timer,
            include_tomorrow=self.session_triggered_by_timer,
            started_calibration=self.started_calibrate_max_charge_speed,
            started_max_charge=self.started_max_charge,
            msg=state.value,
        )

        if self.running_goal.max_charge_now and self.started_max_charge == 0:
            self.started_max_charge = 1

        # Only set charge limit when in charging state because it can turn on the charger.
        # Once set, the latest and correct state can be requested without calling _async_update_ha() first.
        if state == RunState.CHARGING:
            await self.async_set_charge_limit_if_required(chargeable, self.running_goal)

        context = self._get_context(
            charger,
            chargeable,
            state,
            self.running_goal,
            self.net_allocations,
            stats,
        )

        # Check if continue charging or exit loop. Must run after setting charge limit.
        self._set_is_continue_state(context)

        return context

    # ----------------------------------------------------------------------------
    def abort_if_exceed_max_consecutive_failure(self) -> None:
        """Abort state if exceeds MAX_CONSECUTIVE_FAILURE_COUNT."""

        if self.stats.loop_consecutive_fail_count > MAX_CONSECUTIVE_FAILURE_COUNT:
            raise RuntimeError(
                f"Exceeded max number of allowable consecutive failures ({MAX_CONSECUTIVE_FAILURE_COUNT}) in {self.machine_state.state} loop"
            )

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    async def async_get_current_schedule_data(self) -> ScheduleData:
        """Get current schedule data."""

        return await self.scheduler.async_get_schedule_data(
            self.chargeable,
            timer_session=False,
            include_tomorrow=True,
            started_calibration=False,
            started_max_charge=0,
            msg="Schedule",
            log_it=False,
        )

    # ----------------------------------------------------------------------------
    def is_device_at_location_and_connected(self) -> bool:
        """Is device at location and charger connected?"""

        is_at_location = self.is_at_location(self.chargeable)
        is_connected = self.is_connected(self.charger)

        return is_at_location and is_connected

    # ----------------------------------------------------------------------------
    async def async_retry_15_times_to_update_ha_until_charger_on(self) -> None:
        """Wake up device and retry 15 times to update HA until charger is on."""

        _LOGGER.warning(
            "%s: Device presence detected: Waiting for charger connection",
            self.caller,
        )

        await self._async_wakeup_device(self.chargeable)

        loop = 0
        charger_connected = False
        while loop < 15:
            await self.async_update_ha(self.chargeable)
            if (
                # Plug-in sensor might not be defined, so also check charger switch.
                self.is_really_connected(self.charger)
                or self.charger.is_charger_switch_on()
            ):
                charger_connected = True
                break
            await asyncio.sleep(60)
            loop += 1

        _LOGGER.warning(
            "%s: Device presence detected: charger_connected=%s, loop=%s",
            self.caller,
            charger_connected,
            loop,
        )

    # ----------------------------------------------------------------------------
    async def async_semaphore_wakeup_and_update_ha(self) -> None:
        """Task created in semphore on device presence detection to wake up device and update HA."""

        try:
            await self.async_retry_15_times_to_update_ha_until_charger_on()

        except Exception as e:
            _LOGGER.exception(
                "%s: Error updating HA triggered by presence detection: %s",
                self.caller,
                e,
            )

        # This is the only place where update_ha_task_count is set to 0.
        self._semaphore_update_ha_task_count = 0

    # ----------------------------------------------------------------------------
    def start_check_charger_connection_task(self) -> None:
        """Use semaphore to ensure that only one thread can update task count and only one task running."""

        _LOGGER.info("%s: Device presence detected.", self.caller)

        # Use semaphore to create only one async_semaphore_wakeup_and_update_ha() task.
        if self._semaphore_update_ha_task_count == 0:
            with self._semaphore_update_ha_task:
                # This is the only place where update_ha_task_count is set to 1.
                # Count is reset on task completion.
                self._semaphore_update_ha_task_count = 1

                self._hass.loop.create_task(self.async_semaphore_wakeup_and_update_ha())
        else:
            _LOGGER.warning(
                "%s: Update HA task triggered by presence detection already running.",
                self.caller,
            )

    # ----------------------------------------------------------------------------
    async def async_start_state_machine(self, machine_state: SolarChargeState) -> None:
        """Async state machine."""

        # Reference
        # https://auth0.com/blog/state-pattern-in-python/
        self.set_machine_state(machine_state)
        while True:
            _LOGGER.warning(
                "%s: Action state: %s", self.caller, self.get_state_classname()
            )

            current_state = self.machine_state.state
            await self.async_action_state()
            next_state = self.machine_state.state

            if next_state == current_state and current_state == RunState.ENDED:
                # Completed "Ended" state. No more states to run.
                break

    # ----------------------------------------------------------------------------
    # TODO: Look at where to handle exceptions.

    async def async_tidy_up(self) -> None:
        """Tidy up."""

        await self.async_start_state_machine(StateTidyUp())

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
            await self.async_start_state_machine(StateStart())

        except Exception as e:
            _LOGGER.exception("%s: Abort charge: %s", self.caller, e)
            await self.async_tidy_up()
