"""Module to manage the charging process."""

import asyncio
from asyncio import Task, timeout
from collections.abc import Callable, Coroutine
from datetime import date, datetime, timedelta
import inspect
import logging
from time import time
from typing import Any
from zoneinfo import ZoneInfo

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
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

from ..const import (  # noqa: TID252
    CALLBACK_ALLOCATE_POWER,
    CALLBACK_CHANGE_SUNRISE_ELEVATION_TRIGGER,
    CALLBACK_PLUG_IN_CHARGER,
    CALLBACK_SUNRISE_START_CHARGE,
    CALLBACK_SUNSET_DAILY_MAINTENANCE,
    CONTROL_CHARGER_ALLOCATED_POWER,
    DOMAIN,
    ENTITY_KEY_CHARGE_SWITCH,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_EFFECTIVE_VOLTAGE,
    OPTION_CHARGER_MIN_CURRENT,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER,
    OPTION_SUNSET_ELEVATION_END_TRIGGER,
    OPTION_WAIT_CHARGEE_UPDATE_HA,
    OPTION_WAIT_CHARGEE_WAKEUP,
    OPTION_WAIT_CHARGER_AMP_CHANGE,
    OPTION_WAIT_CHARGER_OFF,
    OPTION_WAIT_CHARGER_ON,
    OPTION_WAIT_NET_POWER_UPDATE,
    SWITCH,
)
from ..entity import compose_entity_id  # noqa: TID252
from ..model_config import ConfigValueDict  # noqa: TID252
from ..sc_option_state import ScOptionState  # noqa: TID252
from ..utils import (  # noqa: TID252
    get_next_sunrise_time,
    get_sec_per_degree_sun_elevation,
    get_sun_attribute_or_abort,
    get_sun_attribute_time,
    log_is_event_loop,
    remove_all_callback_subscriptions,
    remove_callback_subscription,
    save_callback_subscription,
)
from .chargeable import Chargeable
from .charger import Charger

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

INITIAL_CHARGE_CURRENT = 6
MIN_TIME_BETWEEN_UPDATE = 10  # 10 seconds


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ChargeController(ScOptionState):
    """Class to manage the charging process."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        charger: Charger,
        chargeable: Chargeable,
    ) -> None:
        """Initialize the Charge instance."""

        self._charger = charger
        self._chargeable = chargeable
        self._charge_task: Task | None = None
        self._end_charge_task: Task | None = None
        self._charge_current_updatetime: int = 0
        self._charger_switch_entity_id = compose_entity_id(
            SWITCH, subentry.unique_id, ENTITY_KEY_CHARGE_SWITCH
        )

        # self._unsub_callbacks: dict[
        #     str, Callable[[], Coroutine[Any, Any, None] | None]
        # ] = {}
        self._unsub_callbacks: dict[str, CALLBACK_TYPE] = {}

        caller = subentry.unique_id
        if caller is None:
            caller = __name__
        ScOptionState.__init__(self, hass, entry, subentry, caller)

    # ----------------------------------------------------------------------------
    @cached_property
    def _device(self) -> dr.DeviceEntry:
        """Get the device entry for the controller."""
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self._subentry.subentry_id)}
        )
        if device is None:
            raise RuntimeError(f"{self._caller} device entry not found.")
        return device

    # ----------------------------------------------------------------------------
    @property
    def is_chargeable(self) -> bool:
        """Return True if the charger is chargeable."""
        return isinstance(self._charger, Chargeable)

    @property
    def get_chargee(self) -> Chargeable | None:
        """Return the chargeable device if applicable."""
        if self.is_chargeable:
            return self._charger  # type: ignore[return-value]
        return None

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    def _log_state_change(self, event: Event[EventStateChangedData]) -> None:
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
    def _turn_on_charger_switch(self) -> None:
        # async_track_sunrise() does not directly support coroutine callback, so create coroutine in event loop.
        # self._hass.loop.create_task(self.async_start_charge())
        self._hass.loop.create_task(
            self.async_turn_switch_on(self._charger_switch_entity_id)
        )

    # ----------------------------------------------------------------------------
    async def _async_turn_on_charger_switch(self, now: datetime) -> None:
        await self.async_turn_switch_on(self._charger_switch_entity_id)

    # ----------------------------------------------------------------------------
    # Sunrise/sunset trigger code
    # ----------------------------------------------------------------------------
    def _setup_daily_maintenance_at_sunset(self) -> None:
        """Every day, set up next sunrise trigger at sunset."""
        _LOGGER.info("%s: Setup sunset daily maintenance", self._caller)
        # offset=timedelta(minutes=2)
        subscription = async_track_sunset(self._hass, self._setup_next_sunrise_trigger)
        save_callback_subscription(
            self._caller,
            self._unsub_callbacks,
            CALLBACK_SUNSET_DAILY_MAINTENANCE,
            subscription,
        )

    # ----------------------------------------------------------------------------
    def _start_charge_on_sunrise(self) -> None:
        # async_track_sunrise() does not directly support coroutine callback, so create coroutine in event loop.
        # self._hass.loop.create_task(self.async_start_charge())
        self._turn_on_charger_switch()

    # ----------------------------------------------------------------------------
    def _setup_next_sunrise_trigger(self) -> None:
        """Recalculate and setup next morning's sunrise trigger."""

        sun_state = self.get_sun_state_or_abort()
        sec_per_degree: float = get_sec_per_degree_sun_elevation(
            self._caller, sun_state
        )
        elevation_start_trigger = self.option_get_entity_number_or_abort(
            OPTION_SUNRISE_ELEVATION_START_TRIGGER
        )
        offset = timedelta(seconds=sec_per_degree * elevation_start_trigger)

        # today = date.today()
        # Combine the date with the minimum time (00:00:00)
        # midnight_datetime = datetime.combine(today, datetime.min.time())
        nowtime = datetime.now()
        next_sunrise_time: datetime = get_next_sunrise_time(self._caller, sun_state)

        # today_sunrise_time = next_sunrise_time - timedelta(days=1)
        # today_sunrise_trigger = today_sunrise_time + offset

        today_sunrise_time = nowtime.replace(
            hour=next_sunrise_time.hour,
            minute=next_sunrise_time.minute,
            second=next_sunrise_time.second,
            microsecond=next_sunrise_time.microsecond,
        )
        today_sunrise_trigger_time = today_sunrise_time + offset

        current_elevation: float = get_sun_attribute_or_abort(
            self._caller, sun_state, "elevation"
        )
        # if elevation_start_trigger > current_elevation:
        if nowtime > today_sunrise_trigger_time:
            # Passed trigger time, so set next sunrise
            _LOGGER.info(
                "%s: Setup next sunrise trigger offset at %s (current_elevation=%s)",
                self._caller,
                offset,
                current_elevation,
            )
            subscription = async_track_sunrise(
                self._hass, self._start_charge_on_sunrise, offset
            )
        else:
            time_diff = today_sunrise_trigger_time - nowtime
            sec_from_now = timedelta(seconds=time_diff.total_seconds())

            _LOGGER.info(
                "%s: Setup today sunrise trigger offset at %s (current_elevation=%s)",
                self._caller,
                sec_from_now,
                current_elevation,
            )
            subscription = async_call_later(
                self._hass, offset, self._async_turn_on_charger_switch
            )

        save_callback_subscription(
            self._caller,
            self._unsub_callbacks,
            CALLBACK_SUNRISE_START_CHARGE,
            subscription,
        )

    # ----------------------------------------------------------------------------
    def _set_up_sun_triggers(self) -> None:
        # Set up sunset daily maintenance
        self._setup_daily_maintenance_at_sunset()

        # Manually set up sunrise trigger if sun has already set when starting SolarCharger.
        sun_state: State = self.get_sun_state_or_abort()
        _LOGGER.debug("%s: Sun state: %s", self._caller, sun_state)

        # next_setting_utc = get_sun_attribute_time(
        #     self._caller, sun_state, "next_setting"
        # )
        # next_rising_utc = get_sun_attribute_time(self._caller, sun_state, "next_rising")

        # if next_setting_utc.timestamp() > next_rising_utc.timestamp():
        #     # Missed sunset, so need to manually set sunrise trigger.
        #     self._setup_next_sunrise_trigger()

        self._setup_next_sunrise_trigger()

    # ----------------------------------------------------------------------------
    # Monitored entities
    # ----------------------------------------------------------------------------
    async def _async_handle_sunrise_elevation_trigger_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        self._log_state_change(event)

        if new_state is not None:
            if old_state is not None:
                if (
                    new_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                    and old_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                    and new_state.state != old_state.state
                ):
                    self._setup_next_sunrise_trigger()

    # ----------------------------------------------------------------------------
    def _track_sunrise_elevation_trigger_change(self) -> None:
        sunrise_elevation_trigger = self.option_get_id_or_abort(
            OPTION_SUNRISE_ELEVATION_START_TRIGGER
        )
        _LOGGER.info(
            "%s: Tracking sunrise elevation trigger change: %s",
            self._caller,
            sunrise_elevation_trigger,
        )

        subscription = async_track_state_change_event(
            self._hass,
            sunrise_elevation_trigger,
            self._async_handle_sunrise_elevation_trigger_change,
        )

        save_callback_subscription(
            self._caller,
            self._unsub_callbacks,
            CALLBACK_CHANGE_SUNRISE_ELEVATION_TRIGGER,
            subscription,
        )

    # ----------------------------------------------------------------------------
    async def _async_handle_plug_in_charger_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        old_state: State | None = data["old_state"]
        new_state: State | None = data["new_state"]

        self._log_state_change(event)

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
                    if self._charger.is_connected():
                        self._turn_on_charger_switch()

    # ----------------------------------------------------------------------------
    def _track_charger_plugged_in_sensor(self) -> None:
        charger_plugged_in_sensor = self.option_get_id_or_abort(
            OPTION_CHARGER_PLUGGED_IN_SENSOR
        )
        _LOGGER.info(
            "%s: Tracking charger plugged-in sensor: %s",
            self._caller,
            charger_plugged_in_sensor,
        )

        subscription = async_track_state_change_event(
            self._hass,
            charger_plugged_in_sensor,
            self._async_handle_plug_in_charger_event,
        )

        save_callback_subscription(
            self._caller, self._unsub_callbacks, CALLBACK_PLUG_IN_CHARGER, subscription
        )

    # ----------------------------------------------------------------------------
    def _track_allocated_power_update(self) -> None:
        allocated_power_entity_id = self.option_get_id_or_abort(
            CONTROL_CHARGER_ALLOCATED_POWER
        )
        _LOGGER.info(
            "%s: Tracking allocated power update: %s",
            self._caller,
            allocated_power_entity_id,
        )

        # Need both changed and unchanged events, eg. update1 at time1=-500W, update2 at time2=-500W
        # Need to handle both updates to make use of the spare power.
        # async_track_state_report_event - send unchanged events.
        # async_track_state_change_event - send changed events.
        # So need both to see all events?
        subscription = async_track_state_change_event(
            self._hass,
            allocated_power_entity_id,
            self._async_handle_allocated_power_update,
        )

        save_callback_subscription(
            self._caller, self._unsub_callbacks, CALLBACK_ALLOCATE_POWER, subscription
        )

    # ----------------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Async setup of the ChargeController."""
        await self._charger.async_setup()
        self._set_up_sun_triggers()
        self._track_charger_plugged_in_sensor()
        self._track_sunrise_elevation_trigger_change()

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of the ChargeController."""
        remove_all_callback_subscriptions(self._unsub_callbacks)
        await self._charger.async_unload()

    # ----------------------------------------------------------------------------
    # Charger code
    # ----------------------------------------------------------------------------
    async def _async_wakeup_device(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_WAKE_UP_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_wake_up(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self._async_option_sleep(OPTION_WAIT_CHARGEE_WAKEUP)

    # ----------------------------------------------------------------------------
    async def _async_update_ha(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_UPDATE_HA_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_update_ha(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self._async_option_sleep(OPTION_WAIT_CHARGEE_UPDATE_HA)

    # ----------------------------------------------------------------------------
    def _check_is_at_location(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_LOCATION_SENSOR
        val_dict = ConfigValueDict(config_item, {})

        is_at_location = chargeable.is_at_location(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            if not is_at_location:
                raise SystemError(f"{self._caller}: Device not at charger location")

    # ----------------------------------------------------------------------------
    async def _async_init_device(self, chargeable: Chargeable) -> None:
        await self._async_wakeup_device(chargeable)
        await self._async_update_ha(chargeable)
        self._check_is_at_location(chargeable)

    # ----------------------------------------------------------------------------
    async def _async_init_charge_limit(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        pass

        # Moved status wait out of if statement to apply wait for all after charge limit change.
        # Tesla BLE need 25 seconds here.
        # ie. OPTION_WAIT_CHARGEE_UPDATE_HA = 25 seconds

    # ----------------------------------------------------------------------------
    def _is_abort_charge(self) -> bool:
        return False

    # ----------------------------------------------------------------------------
    def _is_below_charge_limit(self, chargeable: Chargeable) -> bool:
        """Is device SOC below charge limit?"""
        is_below_limit = True

        try:
            charge_limit = chargeable.get_charge_limit()

            config_item = OPTION_CHARGEE_SOC_SENSOR
            val_dict = ConfigValueDict(config_item, {})
            soc = chargeable.get_state_of_charge(val_dict)
            if val_dict.config_values[config_item].entity_id is None:
                return True

            if soc is not None and charge_limit is not None:
                is_below_limit = soc < charge_limit
                if is_below_limit:
                    _LOGGER.debug(
                        "SOC %s %% is below charge limit %s %%, continuing charger %s",
                        soc,
                        charge_limit,
                        self._caller,
                    )
                else:
                    _LOGGER.info(
                        "SOC %s %% is at or above charge limit %s %%, stopping charger %s",
                        soc,
                        charge_limit,
                        self._caller,
                    )
        except TimeoutError:
            _LOGGER.warning("Timeout while communicating with charger %s", self._caller)
        except Exception as e:
            _LOGGER.error("Error in charging task for charger %s: %s", self._caller, e)

        return is_below_limit

    # ----------------------------------------------------------------------------
    def _is_sun_above_start_end_elevations(self) -> bool:
        sun_above_start_end_elevations = False

        sun_state: State = self.get_sun_state_or_abort()
        sunrise_elevation_start_trigger: float = self.option_get_entity_number_or_abort(
            OPTION_SUNRISE_ELEVATION_START_TRIGGER
        )
        sunset_elevation_end_trigger: float = self.option_get_entity_number_or_abort(
            OPTION_SUNSET_ELEVATION_END_TRIGGER
        )
        sun_elevation: float = get_sun_attribute_or_abort(
            self._caller, sun_state, "elevation"
        )
        sun_is_rising: bool = get_sun_attribute_or_abort(
            self._caller, sun_state, "rising"
        )

        if (sun_is_rising and sun_elevation >= sunrise_elevation_start_trigger) or (
            not sun_is_rising and sun_elevation > sunset_elevation_end_trigger
        ):
            sun_above_start_end_elevations = True

        return sun_above_start_end_elevations

    # ----------------------------------------------------------------------------
    def _is_use_secondary_power_source(self) -> bool:
        return False

    # ----------------------------------------------------------------------------
    def _is_on_charge_schedule(self) -> bool:
        return False

    # ----------------------------------------------------------------------------
    def _is_not_enough_time(self) -> bool:
        return False

    # ----------------------------------------------------------------------------
    async def _async_turn_charger_switch_on(self, charger: Charger) -> None:
        switched_on = charger.is_charger_switch_on()
        if not switched_on:
            await charger.async_turn_charger_switch_on()
            await self._async_option_sleep(OPTION_WAIT_CHARGER_ON)

    # ----------------------------------------------------------------------------
    async def _async_turn_charger_switch_off(self, charger: Charger) -> None:
        await charger.async_turn_charger_switch_off()
        await self._async_option_sleep(OPTION_WAIT_CHARGER_OFF)

    # ----------------------------------------------------------------------------
    async def _async_set_charge_current(self, charger: Charger, current: int) -> None:
        await charger.async_set_charge_current(current)
        await self._async_option_sleep(OPTION_WAIT_CHARGER_AMP_CHANGE)

    # ----------------------------------------------------------------------------
    def _check_current(self, max_current: float, current: float) -> float:
        if current < 0:
            current = 0
        elif current > max_current:
            current = max_current

        return current

    # ----------------------------------------------------------------------------
    def _calc_current_change(
        self, charger: Charger, allocated_power: float
    ) -> tuple[float, float]:
        charger_max_current = charger.get_max_charge_current()
        if charger_max_current is None or charger_max_current <= 0:
            raise SystemError(f"{self._caller}: Failed to get charger max current")

        battery_charge_current = charger.get_charge_current()
        if battery_charge_current is None:
            raise SystemError(f"{self._caller}: Failed to get charge current")
        old_charge_current = self._check_current(
            charger_max_current, battery_charge_current
        )

        config_min_current = self.option_get_entity_number_or_abort(
            OPTION_CHARGER_MIN_CURRENT
        )
        config_min_current = self._check_current(
            charger_max_current, config_min_current
        )
        if self._is_on_charge_schedule() and self._is_not_enough_time():
            charger_min_current = charger_max_current
        else:
            charger_min_current = config_min_current

        #####################################
        # Get allocated power
        #####################################
        # allocated_power = self._get_number(CONTROL_CHARGER_ALLOCATED_POWER)

        charger_effective_voltage = self.option_get_entity_number_or_abort(
            OPTION_CHARGER_EFFECTIVE_VOLTAGE
        )
        if charger_effective_voltage <= 0:
            raise SystemError(f"{self._caller}: Charger effective voltage is 0")

        one_amp_watt_step = charger_effective_voltage * 1
        power_offset = 0
        all_power_net = allocated_power + (one_amp_watt_step * 0.3) + power_offset
        all_current_net = all_power_net / charger_effective_voltage

        if all_current_net > 0:
            propose_charge_current = round(
                max([charger_min_current, old_charge_current - all_current_net])
            )
        else:
            propose_charge_current = round(
                min([charger_max_current, old_charge_current - all_current_net])
            )
        propose_new_charge_current = max([charger_min_current, propose_charge_current])

        charger_min_workable_current = self.option_get_entity_number_or_abort(
            OPTION_CHARGER_MIN_WORKABLE_CURRENT
        )
        if propose_new_charge_current < charger_min_workable_current:
            new_charge_current = 0
        else:
            new_charge_current = propose_new_charge_current

        _LOGGER.debug(
            "%s: allocated_power=%s, charger_effective_voltage=%s, config_min_current=%s, "
            "charger_min_current=%s, charger_max_current=%s, old_charge_current=%s, "
            "all_power_net=%s, all_current_net=%s, propose_charge_current=%s, "
            "propose_new_charge_current=%s, charger_min_workable_current=%s, "
            "new_charge_current=%s ",
            self._caller,
            allocated_power,
            charger_effective_voltage,
            config_min_current,
            charger_min_current,
            charger_max_current,
            old_charge_current,
            all_power_net,
            all_current_net,
            propose_charge_current,
            propose_new_charge_current,
            charger_min_workable_current,
            new_charge_current,
        )

        return (new_charge_current, old_charge_current)

    # ----------------------------------------------------------------------------
    async def _async_adjust_charge_current(
        self, charger: Charger, chargeable: Chargeable, allocated_power: float
    ) -> None:
        new_charge_current, old_charge_current = self._calc_current_change(
            charger, allocated_power
        )
        if new_charge_current != old_charge_current:
            _LOGGER.info(
                "%s: Update current from %s to %s",
                self._caller,
                old_charge_current,
                new_charge_current,
            )
            await self._async_set_charge_current(charger, int(new_charge_current))
            self._charge_current_updatetime = int(time())
            self.emit_solarcharger_event(
                self._device.id, EVENT_ACTION_NEW_CHARGE_CURRENT, new_charge_current
            )
            await self._async_update_ha(chargeable)

    # ----------------------------------------------------------------------------
    # 2025-11-02 09:01:48.009 INFO (MainThread) [custom_components.solarcharger.chargers.controller] tesla_custom_tesla23m3:
    # entity_id=number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power,
    #
    # old_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-500.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:00:32.962356+11:00>,
    #
    # new_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-200.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:01:48.008211+11:00>

    async def _async_handle_allocated_power_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event."""
        data = event.data
        entity_id = data["entity_id"]
        old_state = data["old_state"]
        new_state = data["new_state"]

        if new_state is not None:
            duration_since_last_change = (
                new_state.last_changed_timestamp - self._charge_current_updatetime
            )

            if old_state is not None:
                _LOGGER.debug(
                    "%s: entity_id=%s, old_state=%s, new_state=%s, duration_since_last_change=%s",
                    self._caller,
                    entity_id,
                    old_state.state,
                    new_state.state,
                    duration_since_last_change,
                )
            else:
                _LOGGER.debug(
                    "%s: entity_id=%s, new_state=%s, duration_since_last_change=%s",
                    self._caller,
                    entity_id,
                    new_state.state,
                    duration_since_last_change,
                )

            # Make sure we don't change the charge current too often
            if duration_since_last_change >= MIN_TIME_BETWEEN_UPDATE:
                await self._async_adjust_charge_current(
                    self._charger, self._chargeable, float(new_state.state)
                )

    # ----------------------------------------------------------------------------
    def _is_continue_charge(
        self, charger: Charger, chargeable: Chargeable, loop_count: int
    ) -> bool:
        is_abort_charge = self._is_abort_charge()
        is_connected = charger.is_connected()
        is_below_charge_limit = self._is_below_charge_limit(chargeable)
        is_charging = charger.is_charging()
        is_sun_above_start_end_elevations = self._is_sun_above_start_end_elevations()
        is_use_secondary_power_source = self._is_use_secondary_power_source()
        is_on_charge_schedule = self._is_on_charge_schedule()

        continue_charge = (
            not is_abort_charge
            and is_connected
            and is_below_charge_limit
            and (loop_count == 0 or is_charging)
            and (
                is_sun_above_start_end_elevations
                or is_use_secondary_power_source
                or is_on_charge_schedule
            )
        )

        if not continue_charge:
            _LOGGER.warning(
                "%s: Stopping charge: is_abort_charge=%s, is_connected=%s, "
                "is_below_charge_limit=%s, loop_count=%s, is_charging=%s, "
                "is_sun_above_start_end_elevations=%s, is_use_secondary_power_source=%s, "
                "is_on_charge_schedule=%s",
                self._caller,
                is_abort_charge,
                is_connected,
                is_below_charge_limit,
                loop_count,
                is_charging,
                is_sun_above_start_end_elevations,
                is_use_secondary_power_source,
                is_on_charge_schedule,
            )

        return continue_charge

    # ----------------------------------------------------------------------------
    async def _async_charge_device(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        loop_count = 0

        while self._is_continue_charge(charger, chargeable, loop_count):
            try:
                # Turn on charger if looping for the first time
                if loop_count == 0:
                    await self._async_turn_charger_switch_on(charger)
                    await self._async_set_charge_current(
                        charger, INITIAL_CHARGE_CURRENT
                    )
                    await self._async_update_ha(chargeable)
                    self._track_allocated_power_update()

                # await self._async_adjust_charge_current(charger)
                # await self._async_update_ha(chargeable)

            except TimeoutError:
                _LOGGER.warning(
                    "Timeout while communicating with charger %s", self._caller
                )
            except Exception as e:
                _LOGGER.error(
                    "Error in charge task for charger %s: %s", self._caller, e
                )

            loop_count = loop_count + 1
            await self._async_option_sleep(OPTION_WAIT_NET_POWER_UPDATE)

        remove_callback_subscription(
            self._caller, self._unsub_callbacks, CALLBACK_ALLOCATE_POWER
        )

    # ----------------------------------------------------------------------------
    async def _async_tidy_up_on_exit(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        await self._async_update_ha(chargeable)

        switched_on = charger.is_charger_switch_on()
        if switched_on:
            await self._async_set_charge_current(charger, 0)
            await self._async_turn_charger_switch_off(charger)

    # ----------------------------------------------------------------------------
    async def _async_start_charge_task(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Async task to start the charging process."""
        log_is_event_loop(_LOGGER, self.__class__.__name__, inspect.currentframe())

        # chargeable: Chargeable | None = self.get_chargee
        await self._async_init_device(chargeable)
        await self._async_init_charge_limit(charger, chargeable)
        await self._async_charge_device(charger, chargeable)
        await self._async_tidy_up_on_exit(charger, chargeable)

    # ----------------------------------------------------------------------------
    async def _async_start_charge(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        """Async task to start the charger."""
        await self._async_start_charge_task(charger, chargeable)

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

        _LOGGER.info("Starting charge task for charger %s", self._caller)
        self._charge_task = self._hass.async_create_task(
            self._async_start_charge(self._charger, self._chargeable),
            f"{self._caller} charge",
        )
        return self._charge_task

    # ----------------------------------------------------------------------------
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
                    await self._async_tidy_up_on_exit(charger, chargeable)
                except Exception as e:
                    _LOGGER.error(
                        "Error stopping charge task for charger %s: %s",
                        self._caller,
                        e,
                    )

                remove_callback_subscription(
                    self._caller, self._unsub_callbacks, CALLBACK_ALLOCATE_POWER
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

                _LOGGER.info("Ending charge task for charger %s", self._caller)
                self._end_charge_task = self._hass.async_create_task(
                    self._async_stop_charge(self._charger, self._chargeable),
                    f"{self._caller} end charge",
                )
                return self._end_charge_task

            _LOGGER.info("Task %s already completed", self._charge_task.get_name())
        else:
            _LOGGER.info("No running charge task to stop for charger %s", self._caller)
        return None
