# ruff: noqa: TID252
"""Power allocator implementation."""

import logging

from homeassistant.config_entries import ConfigSubentry

from ..const import (
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR_CONSUMED_POWER,
    SENSOR_SHARE_ALLOCATION,
    RunState,
)
from ..helpers.general import async_set_delta_allocated_power
from ..models.model_allocation import (
    AllocationBook,
    AllocationGroup,
    DeltaPowerAllocation,
)
from ..models.model_device_control import DeviceControl

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class PowerAllocator:
    """Power allocator class."""

    def __init__(
        self,
        global_defaults_subentry: ConfigSubentry,
        device_controls: dict[str, DeviceControl],
    ):
        """Initialize the power allocator."""

        self._device_controls = device_controls
        self._global_defaults_subentry = global_defaults_subentry
        self._global_defaults_control = self._get_global_defaults_device_control()

    # ----------------------------------------------------------------------------
    # Utils
    # ----------------------------------------------------------------------------
    def _get_global_defaults_device_control(self) -> DeviceControl:
        """Get global default device control."""

        global_defaults_subentry = self._global_defaults_subentry
        control = self._device_controls.get(global_defaults_subentry.subentry_id)
        assert control is not None

        return control

    # ----------------------------------------------------------------------------
    # Power allocation code
    # ----------------------------------------------------------------------------
    def _populate_allocation_group(
        self,
        allocation_map: dict[int, AllocationGroup],
        control: DeviceControl,
        consumed_power: float,
        is_real: bool,
    ) -> DeltaPowerAllocation:
        """Populate allocation group with allocation."""

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

        allocation = DeltaPowerAllocation(
            subentry_id=control.subentry_id,
            name=control.config_name,
            max_power=max_power,
            consumed_power=consumed_power,
            priority=priority,
            allocation_weight=allocation_weight,
            share_allocation=share_allocation,
        )

        plan_weight = (
            allocation_weight * control.controller.charge_control.instance_count
        )

        if is_real:
            final_weight = plan_weight * share_allocation
        else:
            final_weight = plan_weight

        # Determine following variables:
        allocation.allocation_final_weight = 0
        allocation.deallocation_final_weight = 0
        allocation.need_power = 0

        #######################################################
        # If at less than max power but not zero, participate in both allocation and deallocation.
        # If at zero power, participate only in allocation.
        # If at max power, participate only in deallocation.
        # The objective is to:
        # - Ensure devices running at max power do not share in allocation, so that other devices
        #   can a get bigger share. This is not perfect since device might just be at below max
        #   power and get allocated more than required. This is ok since it won't participate in
        #   next allocation.
        # - Ensure devices at zero power do not participate in deallocation, so that other devices
        #   can get a bigger share. Similar for allocation, this is not perfect for the same reason.
        #######################################################
        if consumed_power < max_power:
            # Participate in allocation
            allocation.allocation_final_weight = final_weight

            # Paused device has need_power = lack_power = consumed_power = 0.
            if allocation.allocation_final_weight > 0:
                allocation.need_power = consumed_power - max_power

            # Only participate in deallocation if consumed power > 0
            if consumed_power > 0:
                allocation.deallocation_final_weight = final_weight
        else:
            # Participate in deallocation only.
            allocation.deallocation_final_weight = final_weight

        rung = allocation_map.get(allocation.priority)
        if rung is None:
            rung = AllocationGroup(priority=allocation.priority, delta_allocations=[])
            allocation_map[allocation.priority] = rung

        rung.delta_allocations.append(allocation)
        rung.total_max_power += allocation.max_power
        rung.total_consumed_power += allocation.consumed_power
        rung.total_need_power += allocation.need_power
        rung.total_allocation_final_weight += allocation.allocation_final_weight
        rung.total_deallocation_final_weight += allocation.deallocation_final_weight
        rung.total_instance += control.controller.charge_control.instance_count

        return allocation

    # ----------------------------------------------------------------------------
    def _get_total_allocation_pool(
        self,
    ) -> AllocationBook:
        """Get allocation pool from options. Note allocation weight entity can be overriden."""

        real_map: dict[int, AllocationGroup] = {}
        plan_map: dict[int, AllocationGroup] = {}
        allocation_book: AllocationBook = AllocationBook(
            real_allocation_map=real_map, plan_allocation_map=plan_map
        )

        for control in self._device_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            if control.controller.charge_control.instance_count == 0:
                continue

            consumed_power = float(
                control.controller.charge_control.entities.sensors[
                    SENSOR_CONSUMED_POWER
                ].state
            )

            real_allocation = self._populate_allocation_group(
                real_map, control, consumed_power, is_real=True
            )
            self._populate_allocation_group(plan_map, control, 0.0, is_real=False)

            allocation_book.total_instance += (
                control.controller.charge_control.instance_count
            )
            allocation_book.total_consumed_power += real_allocation.consumed_power

        return allocation_book

    # ----------------------------------------------------------------------------
    def _sorted_list_of_priority_level(
        self, allocation_map: dict[int, AllocationGroup]
    ) -> list[AllocationGroup]:
        """Get sorted list of priority level from allocation map."""

        return [allocation_map[priority] for priority in sorted(allocation_map.keys())]

    # ----------------------------------------------------------------------------
    def _allocate_power_to_device(
        self,
        rung: AllocationGroup,
        allocation: DeltaPowerAllocation,
        remain_power: float,
        weight: float,
        total_weight: float,
        net_power: float,
    ) -> float:

        # The following are updated:
        allocation.final_power = 0
        allocation.lack_power = 0

        if total_weight > 0:
            allocated_power = net_power * weight / total_weight

            # allocated_power can be -ve or +ve.
            # allocation.need_power can be -ve or 0, but not +ve.
            if allocated_power <= allocation.need_power:
                # Enough power: allocated_power = 0 or -ve
                # For paused device, allocated_power = need_power = lack_power = 0.
                allocation.final_power = allocation.need_power
                allocation.lack_power = 0
            else:
                # Not enough power: allocated_power is -ve or +ve
                if allocated_power < 0:
                    # Allocate power, ie. -ve
                    allocation.final_power = max(allocated_power, allocation.need_power)
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

        rung.total_lack_power += allocation.lack_power

        return remain_power

    # ----------------------------------------------------------------------------
    def _allocate_power_to_group_member(
        self,
        rung: AllocationGroup,
        allocation: DeltaPowerAllocation,
        remain_power: float,
        net_power: float,
    ) -> float:
        """Allocate real power to running devices."""

        if net_power < 0:
            # Allocate power, ie. -ve
            remain_power = self._allocate_power_to_device(
                rung,
                allocation,
                remain_power,
                allocation.allocation_final_weight,
                rung.total_allocation_final_weight,
                net_power,
            )
        else:
            # Give back power, ie. +ve
            remain_power = self._allocate_power_to_device(
                rung,
                allocation,
                remain_power,
                allocation.deallocation_final_weight,
                rung.total_deallocation_final_weight,
                net_power,
            )

        return remain_power

    # ----------------------------------------------------------------------------
    def _allocate_power_to_group(
        self, rung: AllocationGroup, net_power: float
    ) -> float:
        """Allocate power to priority level.

        net_power: -ve = power to allocate, +ve = power to free up.
        """

        remain_power = net_power

        for allocation in rung.delta_allocations:
            remain_power = self._allocate_power_to_group_member(
                rung,
                allocation,
                remain_power,
                net_power,
            )

        return remain_power

    # ----------------------------------------------------------------------------
    def _bottom_up_release_power(
        self,
        allocation_ladder: list[AllocationGroup],
        net_power: float,  # ie. net_power is positive to free up power.
        end_rung: int = -1,  # inclusive, -1 means all the way to the top priority level.
    ) -> float:
        """Release power from lower to higher priority chargers up to and not including the end_rung priority level."""

        freeup_power = net_power

        # Excludes end_rung
        for idx in range(len(allocation_ladder) - 1, end_rung, -1):
            rung = allocation_ladder[idx]

            freeup_power = self._allocate_power_to_group(rung, freeup_power)

            if freeup_power <= 0:
                break

        return freeup_power

    # ----------------------------------------------------------------------------
    def _top_down_allocate_power(
        self,
        allocation_ladder: list[AllocationGroup],
        net_power: float,  # ie. net_power is negative to allocate power.
    ) -> float:
        """Allocate power from higher to lower priority chargers.

        Allocate power from higher to lower priority chargers when there is enough power.
        If higher priority chargers do not have enough power, free up power from lower to
        higher priority chargers for next allocation.
        """

        surplus_power = net_power

        # Includes start_rung
        for idx in range(len(allocation_ladder)):
            rung = allocation_ladder[idx]

            surplus_power = self._allocate_power_to_group(rung, surplus_power)

            if rung.total_lack_power < 0:
                # If allocating power, remain_power has been depleted because total_lack_power<0.
                power_to_free_up = rung.total_lack_power * -1
                remain_lack_power = self._bottom_up_release_power(
                    allocation_ladder, power_to_free_up, idx
                )
                freeup_power = power_to_free_up - remain_lack_power

                _LOGGER.warning(
                    "Free up allocation: power_to_free_up=%s, remain_lack_power=%s, freeup_power=%s",
                    power_to_free_up,
                    remain_lack_power,
                    freeup_power,
                )

                break

        return surplus_power

    # ----------------------------------------------------------------------------
    async def _async_send_allocations(
        self,
        ladder: list[AllocationGroup],
        power: float,
        is_real: bool,
    ) -> None:
        """Send allocated power to devices."""

        if power < 0:
            remain_power = self._top_down_allocate_power(ladder, power)
        else:
            remain_power = self._bottom_up_release_power(ladder, power)

        _LOGGER.warning(
            "%s allocation: power=%s, remain_power=%s",
            "Real" if is_real else "Plan",
            power,
            remain_power,
        )

        for rung in ladder:
            _LOGGER.debug("AllocationGroup: %s", rung)

            for allocation in rung.delta_allocations:
                control = self._device_controls[allocation.subentry_id]

                send_allocation = False
                if (
                    control.controller.solar_charge.machine_state.state
                    == RunState.ENDING
                ):
                    # Charge session ending, so set delta_allocated_power=0.
                    delta_allocated_power = 0
                    send_allocation = True

                elif (is_real and allocation.share_allocation > 0) or (
                    not is_real and allocation.share_allocation == 0
                ):
                    # Paticipants in power sharing will use final_power.
                    # Non-participants will use plan_power as indication of possible available power.
                    delta_allocated_power = allocation.final_power
                    send_allocation = True

                # Writer will set entity value directly. Reader will get value via
                # entity ID in options which can be overridden.
                if send_allocation:
                    await async_set_delta_allocated_power(
                        control.controller.charge_control, delta_allocated_power
                    )

                    _LOGGER.debug("PowerAllocation: %s", allocation)

    # ----------------------------------------------------------------------------
    # TODO: Need to take into consideration already allocated power and max power of chargers
    # to evenly distribute power.

    async def async_allocate_net_power(self) -> None:
        """Calculate power allocation. Power allocation weight can be 0."""

        net_power = (
            self._global_defaults_control.controller.solar_charge.get_net_power()
        )
        if net_power is None:
            _LOGGER.warning("Cannot get net power. Try next cycle.")
            return

        allocation_book = self._get_total_allocation_pool()
        total_instance = allocation_book.total_instance

        if total_instance > 0:
            real_ladder = self._sorted_list_of_priority_level(
                allocation_book.real_allocation_map
            )
            plan_ladder = self._sorted_list_of_priority_level(
                allocation_book.plan_allocation_map
            )
            total_power = net_power - allocation_book.total_consumed_power
            allocation_book.net_power = net_power
            allocation_book.total_power = total_power
            _LOGGER.warning("AllocationBook: %s", allocation_book)

            # Information only. Global default variable shows net power available for allocation.
            await async_set_delta_allocated_power(
                self._global_defaults_control.controller.charge_control, net_power
            )

            await self._async_send_allocations(real_ladder, net_power, is_real=True)
            await self._async_send_allocations(plan_ladder, total_power, is_real=False)

        else:
            _LOGGER.debug("No running charger for power allocation")
