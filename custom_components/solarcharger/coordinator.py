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

from .config_utils import get_subentry_id
from .const import (
    CONFIG_NET_POWER,
    CONFIG_WAIT_NET_POWER_UPDATE,
    DEFAULT_CHARGE_LIMIT_MAP,
    DOMAIN,
    ERROR_DEFAULT_CHARGE_LIMIT,
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR_CONSUMED_POWER,
    SENSOR_LAST_CHECK,
    SENSOR_SHARE_ALLOCATION,
    WEEKLY_CHARGE_ENDTIMES,
)
from .helpers.general import async_set_allocated_power
from .model_allocation import PowerAllocation, PriorityAllocation
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
    # Periodic functions
    # ----------------------------------------------------------------------------
    def _get_net_power(self) -> float | None:
        """Get household net power."""

        # SolarChargerCoordinator: Failed to parse state 'unavailable' for entity 'sensor.main_power_net':
        # could not convert string to float: 'unavailable'

        return self.config_get_entity_number(CONFIG_NET_POWER)

    # ----------------------------------------------------------------------------
    # def _get_total_allocation_pool(
    #     self,
    # ) -> tuple[int, float, float, int | None, dict[str, PowerAllocation]]:
    #     """Get allocation pool from options. Note allocation weight entity can be overriden."""

    #     total_instance = 0
    #     plan_total_weight = 0
    #     final_total_weight = 0
    #     highest_priority = None
    #     allocations: dict[str, PowerAllocation] = {}

    #     for control in self.device_controls.values():
    #         if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
    #             continue

    #         priority = control.controller.option_get_entity_integer_or_abort(
    #             NUMBER_CHARGER_PRIORITY
    #         )

    #         # Power allocation weight user configurable and can be overridden, so use indirection.
    #         allocation_weight = control.controller.option_get_entity_number_or_abort(
    #             NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT
    #         )

    #         # Participate in power allocation.
    #         assert control.controller.charge_control.entities.sensors is not None
    #         share_allocation = int(
    #             control.controller.charge_control.entities.sensors[
    #                 SENSOR_SHARE_ALLOCATION
    #             ].state
    #         )
    #         consumed_power = float(
    #             control.controller.charge_control.entities.sensors[
    #                 SENSOR_CONSUMED_POWER
    #             ].state
    #         )

    #         allocation = PowerAllocation(
    #             subentry_id=control.subentry_id,
    #             consumed_power=consumed_power,
    #             max_power=0,
    #             priority=priority,
    #             allocation_weight=allocation_weight,
    #             share_allocation=share_allocation,
    #         )

    #         allocation.plan_weight = (
    #             allocation_weight * control.controller.charge_control.instance_count
    #         )
    #         allocation.final_weight = allocation.plan_weight * share_allocation

    #         # Find the highest priority level among running chargers. 0=highest priority.
    #         if allocation.plan_weight > 0:
    #             # Charger is running and has allocation weight > 0
    #             if highest_priority is None or allocation.priority < highest_priority:
    #                 highest_priority = allocation.priority

    #         allocations[control.subentry_id] = allocation
    #         total_instance += control.controller.charge_control.instance_count

    #     # TODO: When higher priority charger is paused with no other charger on same priority,
    #     # then allocate power to lower priority chargers.
    #     # Should have data structure to store plan_total_weight and final_total_weight for
    #     # each priority level to facilitate power allocation to lower priority chargers.

    #     # Chargers with lower priority will not be allocated any power.
    #     if highest_priority is not None:
    #         for allocation in allocations.values():
    #             if allocation.priority == highest_priority:
    #                 plan_total_weight += allocation.plan_weight
    #                 final_total_weight += allocation.final_weight
    #             else:
    #                 allocation.plan_weight = 0
    #                 allocation.final_weight = 0

    #     _LOGGER.debug(
    #         "total_instance=%s, plan_total_weight=%s, final_total_weight=%s, highest_priority=%s",
    #         total_instance,
    #         plan_total_weight,
    #         final_total_weight,
    #         highest_priority,
    #     )

    #     return (
    #         total_instance,
    #         plan_total_weight,
    #         final_total_weight,
    #         highest_priority,
    #         allocations,
    #     )

    # # ----------------------------------------------------------------------------
    # # TODO: Need to take into consideration already allocated power and max power of chargers.

    # async def _async_allocate_net_power(self) -> None:
    #     """Calculate power allocation. Power allocation weight can be 0."""

    #     net_power = self._get_net_power()
    #     if net_power is None:
    #         _LOGGER.warning("Failed to get net power update. Try again next cycle.")
    #         return

    #     (
    #         total_instance,
    #         plan_total_weight,
    #         final_total_weight,
    #         highest_priority,
    #         allocations,
    #     ) = self._get_total_allocation_pool()

    #     if total_instance > 0:
    #         for control in self.device_controls.values():
    #             # Information only. Global default variable shows net power available for allocation.
    #             if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
    #                 await async_set_allocated_power(
    #                     control.controller.charge_control, net_power
    #                 )
    #                 continue

    #             allocation = allocations[control.subentry_id]
    #             if highest_priority == allocation.priority:
    #                 # Only allocate power to running chargers with the highest priority.
    #                 if final_total_weight > 0:
    #                     allocation.final_power = (
    #                         net_power * allocation.final_weight / final_total_weight
    #                     )
    #                 else:
    #                     allocation.final_power = 0

    #                 if plan_total_weight > 0:
    #                     allocation.plan_power = (
    #                         net_power * allocation.plan_weight / plan_total_weight
    #                     )
    #                 else:
    #                     allocation.plan_power = 0
    #             else:
    #                 # Try to get power back from lower priority chargers.
    #                 # Not possible if charger is on charge schedule.
    #                 allocation.plan_power = allocation.consumed_power
    #                 allocation.final_power = allocation.consumed_power

    #             # Writer will set entity value directly. Reader will get value via entity ID in options which can be overridden.
    #             # Paticipants in power sharing will use final_power, non-participants will use plan_power as indication of possible available power.
    #             await async_set_allocated_power(
    #                 control.controller.charge_control,
    #                 allocation.final_power
    #                 if allocation.share_allocation > 0
    #                 else allocation.plan_power,
    #             )

    #             _LOGGER.debug(
    #                 "%s: allocation=%s",
    #                 control.config_name,
    #                 allocation,
    #             )
    #     else:
    #         _LOGGER.debug(
    #             "No running charger for net power allocation. Try again next cycle."
    #         )

    # ----------------------------------------------------------------------------
    def _get_total_allocation_pool(
        self,
    ) -> tuple[int, dict[int, PriorityAllocation]]:
        """Get allocation pool from options. Note allocation weight entity can be overriden."""

        total_instance = 0
        allocation_map: dict[int, PriorityAllocation] = {}

        for control in self.device_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            if control.controller.charge_control.instance_count == 0:
                continue

            # The following are user configurable and can be overridden, so use indirection.
            priority = control.controller.solar_charge.get_charger_priority()
            allocation_weight = (
                control.controller.solar_charge.get_charger_power_allocation_weight()
            )
            max_current = control.controller.solar_charge.get_charger_max_current()
            voltage = control.controller.solar_charge.get_charger_effective_voltage()
            max_power = max_current * voltage

            # Participate in power allocation.
            assert control.controller.charge_control.entities.sensors is not None
            share_allocation = int(
                control.controller.charge_control.entities.sensors[
                    SENSOR_SHARE_ALLOCATION
                ].state
            )
            consumed_power = float(
                control.controller.charge_control.entities.sensors[
                    SENSOR_CONSUMED_POWER
                ].state
            )

            allocation = PowerAllocation(
                subentry_id=control.subentry_id,
                max_power=max_power,
                consumed_power=consumed_power,
                priority=priority,
                allocation_weight=allocation_weight,
                share_allocation=share_allocation,
            )

            allocation.plan_weight = (
                allocation_weight * control.controller.charge_control.instance_count
            )
            allocation.final_weight = allocation.plan_weight * share_allocation

            if allocation.final_weight > 0:
                if consumed_power < max_power:
                    allocation.need_power = consumed_power - max_power

            rung = allocation_map.get(allocation.priority)
            if rung is None:
                rung = PriorityAllocation(priority=allocation.priority, allocations=[])
                allocation_map[allocation.priority] = rung

            rung.allocations.append(allocation)
            rung.total_max_power += allocation.max_power
            rung.total_consumed_power += allocation.consumed_power
            rung.total_need_power += allocation.need_power
            rung.total_plan_weight += allocation.plan_weight
            rung.total_final_weight += allocation.final_weight
            rung.total_instance += control.controller.charge_control.instance_count

            total_instance += control.controller.charge_control.instance_count

        return (
            total_instance,
            allocation_map,
        )

    # ----------------------------------------------------------------------------
    def _sorted_list_of_priority_level(
        self, allocation_ladder: dict[int, PriorityAllocation]
    ) -> list[PriorityAllocation]:
        """Get sorted list of priority level from allocation ladder."""

        return [
            allocation_ladder[priority] for priority in sorted(allocation_ladder.keys())
        ]

    # ----------------------------------------------------------------------------
    def _allocate_power(self, rung: PriorityAllocation, net_power: float) -> float:
        """Allocate power to priority level.

        net_power: -ve means have excess power to allocate, +ve means power to free up.
        """

        remain_power = net_power

        for allocation in rung.allocations:
            # The following are updated:
            #   allocation.final_power
            #   allocation.lack_power
            if rung.total_final_weight > 0:
                allocated_power = (
                    net_power * allocation.final_weight / rung.total_final_weight
                )

                # allocated_power can be -ve or +ve.
                # allocation.need_power can be -ve or 0, but not +ve.
                if allocated_power <= allocation.need_power:
                    # Enough power.
                    allocation.final_power = allocation.need_power
                    allocation.lack_power = 0
                else:
                    # Not enough power.
                    if allocated_power < 0:
                        # Allocate power, ie. -ve
                        allocation.final_power = max(
                            allocated_power, allocation.need_power
                        )
                    else:
                        # Give back power, ie. +ve
                        allocation.final_power = min(
                            allocated_power, allocation.consumed_power
                        )

                    allocation.lack_power = max(
                        allocation.need_power - allocation.final_power,
                        -allocation.max_power,
                    )

                remain_power = remain_power - allocation.final_power
            else:
                allocation.final_power = 0
                allocation.lack_power = 0

            rung.total_lack_power += allocation.lack_power

            # The following are updated:
            #   allocation.plan_power
            if rung.total_plan_weight > 0:
                allocation.plan_power = (
                    net_power * allocation.plan_weight / rung.total_plan_weight
                )
            else:
                allocation.plan_power = 0

        return remain_power

    # ----------------------------------------------------------------------------
    def _bottom_up_release_power(
        self,
        allocation_ladder: list[PriorityAllocation],
        net_power: float,  # ie. net_power is positive to free up power.
        end_rung: int = -1,  # inclusive, -1 means all the way to the top priority level.
    ) -> float:
        """Release power from chargers with priority level lower than or equal to the given priority level."""

        freeup_power = net_power

        # Excludes end_rung
        for idx in range(len(allocation_ladder) - 1, end_rung, -1):
            rung = allocation_ladder[idx]

            freeup_power = self._allocate_power(rung, freeup_power)

            if freeup_power <= 0:
                break

        return freeup_power

    # ----------------------------------------------------------------------------
    def _top_down_allocate_power(
        self,
        allocation_ladder: list[PriorityAllocation],
        net_power: float,  # ie. net_power is negative for allocation.
    ) -> float:
        """Allocate power to higher priority chargers first when there is excess power.

        When higher priority charger is paused with no other charger on same priority,
        then allocate power to lower priority chargers.
        """

        surplus_power = net_power

        # Includes start_rung
        for idx in range(len(allocation_ladder)):
            rung = allocation_ladder[idx]

            surplus_power = self._allocate_power(rung, surplus_power)

            if rung.total_lack_power < 0:
                # If allocating power, remain_power has been depleted because total_lack_power<0.
                power_to_free_up = rung.total_lack_power * -1
                self._bottom_up_release_power(allocation_ladder, power_to_free_up, idx)
                break

        return surplus_power

    # ----------------------------------------------------------------------------
    # TODO: Need to take into consideration already allocated power and max power of chargers.

    async def _async_allocate_net_power(self) -> None:
        """Calculate power allocation. Power allocation weight can be 0."""

        net_power = self._get_net_power()
        if net_power is None:
            _LOGGER.warning("Failed to get net power update. Try again next cycle.")
            return

        (
            total_instance,
            allocation_map,
        ) = self._get_total_allocation_pool()

        if total_instance > 0:
            allocation_ladder = self._sorted_list_of_priority_level(allocation_map)

            if net_power < 0:
                remain_power = self._top_down_allocate_power(
                    allocation_ladder, net_power
                )
            else:
                remain_power = self._bottom_up_release_power(
                    allocation_ladder, net_power
                )

            _LOGGER.warning(
                "After allocation: total_instance=%s, net_power=%s, remain_power=%s",
                total_instance,
                net_power,
                remain_power,
            )

            # Information only. Global default variable shows net power available for allocation.
            global_defaults_subentry = self._subentry
            control = self.device_controls.get(global_defaults_subentry.subentry_id)
            assert control is not None
            await async_set_allocated_power(
                control.controller.charge_control, net_power
            )

            for rung in allocation_ladder:
                _LOGGER.warning(
                    "priority=%s, total_max_power=%s, total_consumed_power=%s, "
                    "total_need_power=%s, total_lack_power=%s, total_plan_weight=%s, "
                    "total_final_weight=%s, total_instance=%s",
                    rung.priority,
                    rung.total_max_power,
                    rung.total_consumed_power,
                    rung.total_need_power,
                    rung.total_lack_power,
                    rung.total_plan_weight,
                    rung.total_final_weight,
                    rung.total_instance,
                )

                for allocation in rung.allocations:
                    control = self.device_controls.get(allocation.subentry_id)
                    assert control is not None

                    # Writer will set entity value directly. Reader will get value via entity ID in options which can be overridden.
                    # Paticipants in power sharing will use final_power, non-participants will use plan_power as indication of possible available power.
                    await async_set_allocated_power(
                        control.controller.charge_control,
                        allocation.final_power
                        if allocation.share_allocation > 0
                        else allocation.plan_power,
                    )

                    _LOGGER.warning(
                        "%s: allocation=%s",
                        control.config_name,
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
