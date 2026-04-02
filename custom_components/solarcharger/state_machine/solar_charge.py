# ruff: noqa: TRY401, TID252
"""Solar charge state machine implementation to manage solar charging."""

import asyncio
import inspect
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

# Might be of help in the future.
# from homeassistant.helpers.sun import get_astral_event_next
from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..chargers.scheduler import ChargeScheduler
from ..chargers.tracker import Tracker
from ..const import (
    DOMAIN,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MIN_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
    NUMBER_WAIT_CHARGEE_UPDATE_HA,
    NUMBER_WAIT_CHARGEE_WAKEUP,
    NUMBER_WAIT_CHARGER_AMP_CHANGE,
    NUMBER_WAIT_CHARGER_OFF,
    NUMBER_WAIT_CHARGER_ON,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_GET_CHARGE_CURRENT,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    OPTION_CHARGER_SET_CHARGE_CURRENT,
    SENSOR_CONSUMED_POWER,
    SENSOR_RUN_STATE,
    RunState,
)
from ..model_charge_control import ControlEntities
from ..model_charge_stats import ChargeStats
from ..model_config import ConfigValueDict
from ..sc_option_state import ScheduleData, ScOptionState, StateOfCharge
from ..utils import log_is_event_loop
from .solar_charge_state import SolarChargeState
from .state_initialise import StateInitialise
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
        charger: Any,
        chargeable: Any,
        # charger: Charger,
        # chargeable: Chargeable,
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

        self.session_triggered_by_timer = False
        self.starting_goal: ScheduleData
        self.running_goal: ScheduleData

        self.wait_net_power_update: float = 60
        self.update_ha_task_count = 0
        self.started_calibrate_max_charge_speed = False
        self.charge_current_updatetime: float = 0
        self.soc_updates: list[StateOfCharge] = []
        self.power_allocations: list[float] = []
        self.max_allocation_count = 0
        self.stats = ChargeStats()

        # Initialise state machine self._state variable.
        self.set_machine_state(StateInitialise())

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
    def set_run_state(self, state: str) -> None:
        """Set the run state of the object."""

        assert self.entities.sensors is not None
        self.entities.sensors[SENSOR_RUN_STATE].set_state(state)

    # ----------------------------------------------------------------------------
    # Local utils
    # ----------------------------------------------------------------------------
    async def _async_wakeup_device(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_WAKE_UP_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_wake_up(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self.async_option_sleep(NUMBER_WAIT_CHARGEE_WAKEUP)

    # ----------------------------------------------------------------------------
    async def _async_poll_charger_update(self, wait_after_update: bool) -> None:
        """Poll charger for update using charger switch entity since every charger must have one."""

        charger_entity = self.option_get_id(OPTION_CHARGER_ON_OFF_SWITCH)
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
                config_item = OPTION_CHARGEE_UPDATE_HA_BUTTON
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

        config_item = OPTION_CHARGEE_LOCATION_SENSOR
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

        config_item = OPTION_CHARGER_PLUGGED_IN_SENSOR
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
    def validate_current(self, max_current: float, current: float) -> float:
        """Validate charge current is within charger supported range."""

        if current < 0:
            current = 0
        elif current > max_current:
            current = max_current

        return current

    # ----------------------------------------------------------------------------
    def get_charger_min_current(self, charger_max_current: float) -> float:
        """Get charger min current."""

        config_min_current = self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_MIN_CURRENT
        )
        return self.validate_current(charger_max_current, config_min_current)

    # ----------------------------------------------------------------------------
    def get_charger_max_current(self, charger: Charger) -> float:
        """Get charger max current."""

        charger_max_current = charger.get_max_charge_current()
        if charger_max_current is None or charger_max_current <= 0:
            raise ValueError("Failed to get charger max current")

        return charger_max_current

    # ----------------------------------------------------------------------------
    def get_charger_min_workable_current(self) -> float:
        """Get charger minimum workable current."""

        return self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_MIN_WORKABLE_CURRENT
        )

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
    def get_charge_current(self, charger: Charger, val_dict: ConfigValueDict) -> float:
        """Get device charge current."""

        charge_current = charger.get_charge_current(val_dict)
        if val_dict.config_values[OPTION_CHARGER_GET_CHARGE_CURRENT].entity_id is None:
            # So we can't get the current, ie. a resistive load.
            # All devices must have max charge current configured.
            charge_current = self.get_charger_max_current(charger)

        if charge_current is None:
            raise ValueError("Failed to get device charge current")

        return charge_current

    # ----------------------------------------------------------------------------
    async def async_set_charge_current(self, charger: Charger, current: float) -> None:
        """Set charge current."""

        config_item = OPTION_CHARGER_GET_CHARGE_CURRENT
        val_dict = ConfigValueDict(config_item, {})
        can_set_current = True

        try:
            # Get old charge current.
            old_charge_current = self.get_charge_current(charger, val_dict)

            # Set new charge current.
            config_item = OPTION_CHARGER_SET_CHARGE_CURRENT
            new_charge_current = await charger.async_set_charge_current(
                current, val_dict
            )
            if val_dict.config_values[config_item].entity_id is None:
                # So we can't set the current, ie. a resistive load.
                new_charge_current = old_charge_current
                can_set_current = False

            effective_voltage = self.get_charger_effective_voltage()
            if new_charge_current is not None:
                assert self.entities.sensors is not None
                self.entities.sensors[SENSOR_CONSUMED_POWER].set_state(
                    new_charge_current * effective_voltage
                )

                if can_set_current:
                    self.emit_solarcharger_event(
                        self._device.id,
                        EVENT_ACTION_NEW_CHARGE_CURRENT,
                        new_charge_current,
                        old_charge_current,
                    )
                    await self.async_option_sleep(NUMBER_WAIT_CHARGER_AMP_CHANGE)

        except Exception as e:
            _LOGGER.exception(
                "%s: Error setting charge current %s A: %s", self.caller, current, e
            )

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    async def async_get_current_schedule_data(self) -> ScheduleData:
        """Get current schedule data."""

        return await self.scheduler.async_get_schedule_data(
            self.chargeable,
            include_tomorrow=True,
            started_calibration=False,
            msg="Schedule",
            log_it=False,
        )

    # ----------------------------------------------------------------------------
    def device_at_location_and_connected(self) -> bool:
        """Is device at location and charger connected?"""

        is_at_location = self.is_at_location(self.chargeable)
        is_connected = self.is_connected(self.charger)

        return is_at_location and is_connected

    # ----------------------------------------------------------------------------
    async def async_retry_15_times_to_update_ha_until_charger_on(self) -> None:
        """Wake up device and retry 15 times to update HA until charger is on."""

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
    async def async_update_ha_with_latest_data(self) -> None:
        """Wake up device and retry 15 times to update HA until charger is on."""

        if self.update_ha_task_count == 0:
            self.update_ha_task_count = 1
            try:
                await self.async_retry_15_times_to_update_ha_until_charger_on()
            except Exception as e:
                _LOGGER.exception(
                    "%s: Error updating HA triggered by presence detection: %s",
                    self.caller,
                    e,
                )

            self.update_ha_task_count = 0

        else:
            # Should never be here.
            _LOGGER.error(
                "%s: Update HA task triggered by presence detection already running.",
                self.caller,
            )

    # ----------------------------------------------------------------------------
    def is_monitor_available_power(self) -> bool:
        """Is monitor available power option enabled?"""
        need_to_monitor = False

        if self.max_allocation_count > 0:
            # Yes, monitor config switched on.
            need_to_monitor = True

            max_current = self.get_charger_max_current(self.charger)
            min_current = self.get_charger_min_current(max_current)

            if (
                self.is_calibrate_max_charge_speed()
                or self.is_fast_charge_mode()
                # Time-based min current using template helper.
                or min_current == max_current
                # Note running goal is stale when state machine is in paused state.
                or self.running_goal.has_charge_endtime
            ):
                need_to_monitor = False

        return need_to_monitor

    # ----------------------------------------------------------------------------
    def is_average_allocated_power_more_than_min_workable_power(
        self,
        max_allocation_count: int,
        power_allocations: list[float],
        raise_the_bar: bool = False,
    ) -> tuple[bool | None, float, int]:
        """Is average allocated power more than minimum workable power? None=not enough data.

        raise_the_bar: Raise the bar to make it easier to get below the threshold, or harder to get above it.
        Should be used to make it harder to switch on the charger.
        """
        is_enough_power = None
        average_allocated_power = 0

        if max_allocation_count > 0 and len(power_allocations) >= max_allocation_count:
            average_allocated_power = sum(power_allocations) / len(power_allocations)

            charger_min_workable_current = self.get_charger_min_workable_current()
            charger_effective_voltage = self.get_charger_effective_voltage()
            min_workable_power = (
                charger_min_workable_current * charger_effective_voltage * -1
            )
            if raise_the_bar:
                # Raise the bar by 10% to avoid borderline cases where the charger might keep switching on and off.
                min_workable_power *= 1.10

            # Note surplus power is negative.
            is_enough_power = average_allocated_power <= min_workable_power

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "%s: average_allocated_power=%s W, min_workable_power=%s W, is_enough_power=%s, "
                    "max_allocation_count=%s, power_allocations_count=%s, power_allocations=%s",
                    self.caller,
                    average_allocated_power,
                    min_workable_power,
                    is_enough_power,
                    max_allocation_count,
                    len(power_allocations),
                    power_allocations,
                )

        return (is_enough_power, average_allocated_power, len(power_allocations))

    # ----------------------------------------------------------------------------
    async def async_start_state_machine(self, state: SolarChargeState) -> None:
        """Async state machine."""

        # Reference
        # https://auth0.com/blog/state-pattern-in-python/
        self.set_machine_state(state)
        while True:
            _LOGGER.warning(
                "%s: Action state: %s", self.caller, self.get_state_classname()
            )

            current_state = self.machine_state.state_name
            await self.async_action_state()
            next_state = self.machine_state.state_name

            if (
                next_state == current_state
                and current_state == RunState.STATE_ENDED.value
            ):
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
            await self.async_start_state_machine(StateInitialise())

        except Exception as e:
            _LOGGER.exception("%s: Abort charge: %s", self.caller, e)
            await self.async_tidy_up()
