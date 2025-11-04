"""Module to manage the charging process."""

import asyncio
from asyncio import Task, timeout
from collections.abc import Callable, Coroutine
import inspect
import logging
from time import time

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event

from ..const import (  # noqa: TID252
    CONTROL_CHARGER_ALLOCATED_POWER,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_EFFECTIVE_VOLTAGE,
    OPTION_CHARGER_MIN_CURRENT,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT,
    OPTION_WAIT_CHARGEE_UPDATE_HA,
    OPTION_WAIT_CHARGEE_WAKEUP,
    OPTION_WAIT_CHARGER_AMP_CHANGE,
    OPTION_WAIT_CHARGER_OFF,
    OPTION_WAIT_CHARGER_ON,
    OPTION_WAIT_NET_POWER_UPDATE,
)
from ..model_config import ConfigValueDict  # noqa: TID252
from ..sc_option_state import ScOptionState  # noqa: TID252
from ..utils import log_is_event_loop  # noqa: TID252
from .chargeable import Chargeable
from .charger import Charger

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

INITIAL_CHARGE_CURRENT = 6
MIN_TIME_BETWEEN_UPDATE = 10  # 10 seconds

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# TODO: Need to clean up if removed subentry


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

        # self._unsub_list: list[Callable[[], Coroutine[Any, Any, None] | None]] = []
        self._unsub_list: list[CALLBACK_TYPE] = []

        caller = subentry.unique_id
        if caller is None:
            caller = __name__
        ScOptionState.__init__(self, hass, entry, subentry, caller)

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
    async def async_setup(self) -> None:
        """Async setup of the ChargeController."""
        await self._charger.async_setup()

    # ----------------------------------------------------------------------------
    async def async_unload(self) -> None:
        """Async unload of the ChargeController."""
        await self._charger.async_unload()

    # ----------------------------------------------------------------------------
    # Utils
    # ----------------------------------------------------------------------------
    def _get_must_have_entity_id(self, config_item: str) -> str:
        entity_id = self.option_get_id(config_item)
        if entity_id is None:
            raise SystemError(
                f"{self._caller}: Failed to get entity ID for {config_item}"
            )

        return entity_id

    # ----------------------------------------------------------------------------
    def _get_must_have_number(self, config_item: str) -> float:
        num = self.option_get_entity_number(config_item)
        if num is None:
            raise SystemError(f"{self._caller}: Failed to get number for {config_item}")

        return num

    # ----------------------------------------------------------------------------
    async def _async_sleep(self, config_item: str) -> None:
        """Wait sleep time."""

        duration = self._get_must_have_number(config_item)
        await asyncio.sleep(duration)

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    async def _async_wakeup_device(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_WAKE_UP_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_wake_up(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self._async_sleep(OPTION_WAIT_CHARGEE_WAKEUP)

    # ----------------------------------------------------------------------------
    async def _async_update_ha(self, chargeable: Chargeable) -> None:
        config_item = OPTION_CHARGEE_UPDATE_HA_BUTTON
        val_dict = ConfigValueDict(config_item, {})

        await chargeable.async_update_ha(val_dict)
        if val_dict.config_values[config_item].entity_id is not None:
            await self._async_sleep(OPTION_WAIT_CHARGEE_UPDATE_HA)

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
        return True

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
            await self._async_sleep(OPTION_WAIT_CHARGER_ON)

    # ----------------------------------------------------------------------------
    async def _async_turn_charger_switch_off(self, charger: Charger) -> None:
        await charger.async_turn_charger_switch_off()
        await self._async_sleep(OPTION_WAIT_CHARGER_OFF)

    # ----------------------------------------------------------------------------
    async def _async_set_charge_current(self, charger: Charger, current: int) -> None:
        await charger.async_set_charge_current(current)
        await self._async_sleep(OPTION_WAIT_CHARGER_AMP_CHANGE)

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

        config_min_current = self._get_must_have_number(OPTION_CHARGER_MIN_CURRENT)
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

        charger_effective_voltage = self._get_must_have_number(
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

        charger_min_workable_current = self._get_must_have_number(
            OPTION_CHARGER_MIN_WORKABLE_CURRENT
        )
        if propose_new_charge_current < charger_min_workable_current:
            new_charge_current = 0
        else:
            new_charge_current = propose_new_charge_current

        _LOGGER.debug(
            "%s: "
            "allocated_power=%s, "
            "charger_effective_voltage=%s, "
            "config_min_current=%s, "
            "charger_min_current=%s, "
            "charger_max_current=%s, "
            "old_charge_current=%s, "
            "all_power_net=%s "
            "all_current_net=%s "
            "propose_charge_current=%s "
            "propose_new_charge_current=%s "
            "charger_min_workable_current=%s "
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
        old_alloc_power = data["old_state"]
        new_alloc_power = data["new_state"]

        if new_alloc_power is not None:
            duration_since_last_change = (
                new_alloc_power.last_changed_timestamp - self._charge_current_updatetime
            )

            if old_alloc_power is not None:
                _LOGGER.debug(
                    "%s: entity_id=%s, old_state=%s, new_state=%s, duration_since_last_change=%s",
                    self._caller,
                    entity_id,
                    old_alloc_power.state,
                    new_alloc_power.state,
                    duration_since_last_change,
                )
            else:
                _LOGGER.debug(
                    "%s: entity_id=%s, new_state=%s, duration_since_last_change=%s",
                    self._caller,
                    entity_id,
                    new_alloc_power.state,
                    duration_since_last_change,
                )

            # Make sure we don't change the charge current too often
            if duration_since_last_change >= MIN_TIME_BETWEEN_UPDATE:
                await self._async_adjust_charge_current(
                    self._charger, self._chargeable, float(new_alloc_power.state)
                )

    # ----------------------------------------------------------------------------
    def _track_allocated_power_update(self) -> None:
        allocated_power_entity_id = self._get_must_have_entity_id(
            CONTROL_CHARGER_ALLOCATED_POWER
        )

        # Need both changed and unchanged events, eg. update1 at time1=-500W, update2 at time2=-500W
        # Need to handle both updates to make use of the spare power.
        # async_track_state_report_event - send unchanged events.
        # async_track_state_change_event - send changed events.
        # So need both to see all events?
        self._unsub_list.append(
            async_track_state_change_event(
                self._hass,
                allocated_power_entity_id,
                self._async_handle_allocated_power_update,
            )
        )

    # ----------------------------------------------------------------------------
    def _untrack_allocated_power_update(self) -> None:
        for unsub_func in self._unsub_list:
            unsub_func()
        self._unsub_list.clear()

    # ----------------------------------------------------------------------------
    async def _async_charge_device(
        self, charger: Charger, chargeable: Chargeable
    ) -> None:
        loop_count = 0

        while (
            not self._is_abort_charge()
            and charger.is_connected()
            and self._is_below_charge_limit(chargeable)
            and (loop_count == 0 or charger.is_charging())
            and (
                self._is_sun_above_start_end_elevations()
                or self._is_use_secondary_power_source()
                or self._is_on_charge_schedule()
            )
        ):
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
            await self._async_sleep(OPTION_WAIT_NET_POWER_UPDATE)

        self._untrack_allocated_power_update()

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
    def start_charge(self) -> Task:
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

                self._untrack_allocated_power_update()

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
