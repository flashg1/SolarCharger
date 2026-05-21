# ruff: noqa: TID252, PLR5501
"""Power allocator implementation."""

from copy import deepcopy
import logging

from jaraco import net

from homeassistant.config_entries import ConfigSubentry

from ..const import OPTION_GLOBAL_DEFAULTS_ID, SENSOR_CONSUMED_POWER, RunState
from ..helpers.general import async_set_delta_allocated_power, async_update_sensor_state
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
    def init_allocator(
        self,
    ) -> None:
        """Initialize the power allocator."""

        for control in self._device_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            # This is required to stop the allocator from sending allocation during boot.
            # Best not to reset here since it is managed elsewhere.
            # async_update_sensor_state(
            #     control.controller.charge_control, SENSOR_INSTANCE_COUNT, 0
            # )
            # async_update_sensor_state(
            #     control.controller.charge_control, SENSOR_SHARE_ALLOCATION, 0
            # )

            # Best to reset consumed power to 0 in case value is not 0 before reboot.
            async_update_sensor_state(
                control.controller.charge_control, SENSOR_CONSUMED_POWER, 0.0
            )

    # ----------------------------------------------------------------------------
    def _create_group_member(self, control: DeviceControl) -> DeltaPowerAllocation:
        """Create member from config. Note allocation weight entity can be overriden."""

        # The following are user configurable and can be overridden, so use indirection.
        priority = control.controller.solar_charge.get_charger_priority()
        allocation_weight = (
            control.controller.solar_charge.get_charger_power_allocation_weight()
        )
        max_current = control.controller.solar_charge.get_charger_max_current()
        min_workable_current = (
            control.controller.solar_charge.get_charger_min_workable_current()
        )
        voltage = control.controller.solar_charge.get_charger_effective_voltage()
        max_power = max_current * voltage
        min_workable_power = min_workable_current * voltage

        # Participate in power allocation.
        instance = control.controller.charge_control.instance_count
        share_allocation = control.controller.solar_charge.get_share_allocation()

        return DeltaPowerAllocation(
            subentry_id=control.subentry_id,
            name=control.config_name,
            max_power=max_power,
            min_workable_power=min_workable_power,
            priority=priority,
            allocation_weight=allocation_weight,
            instance=instance,
            share_allocation=share_allocation,
        )

    # ----------------------------------------------------------------------------
    def _populate_member_and_group_data(
        self,
        group_map: dict[int, AllocationGroup],
        member: DeltaPowerAllocation,
        consumed_power: float,
        exclude_paused: bool,
    ) -> None:
        """Populate member and group data."""

        # Exclude paused devices from allocation.
        if exclude_paused and member.share_allocation == 0:
            return

        member.consumed_power = consumed_power

        # member.instance can only be 1 since we have excluded all non-running devices.
        final_weight = member.instance * member.allocation_weight

        # Determine following variables:
        member.allocation_final_weight = 0
        member.deallocation_final_weight = 0
        member.need_power = 0

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
        if consumed_power < member.max_power:
            # Participate in allocation
            member.allocation_final_weight = final_weight

            # Paused device has need_power = lack_power = consumed_power = 0.
            if member.allocation_final_weight > 0:
                member.need_power = consumed_power - member.max_power

            # Only participate in deallocation if consumed power > 0
            if consumed_power > 0:
                member.deallocation_final_weight = final_weight
        else:
            # Participate in deallocation only.
            member.deallocation_final_weight = final_weight

        group = group_map.get(member.priority)
        if group is None:
            group = AllocationGroup(priority=member.priority, delta_allocations={})
            group_map[member.priority] = group

        group.delta_allocations[member.subentry_id] = member
        group.total_max_power += member.max_power
        group.total_consumed_power += member.consumed_power
        group.total_need_power += member.need_power
        group.total_allocation_final_weight += member.allocation_final_weight
        group.total_deallocation_final_weight += member.deallocation_final_weight
        group.total_instance += member.instance

    # ----------------------------------------------------------------------------
    def _get_allocation_pool(self, net_power: float = 0.0) -> AllocationBook:
        """Get allocation pool for active and paused devices."""

        active_group_map: dict[int, AllocationGroup] = {}
        all_group_map: dict[int, AllocationGroup] = {}
        balance_group_map: dict[int, AllocationGroup] = {}
        book: AllocationBook = AllocationBook(
            active_member_map=active_group_map,
            all_member_map=all_group_map,
            balance_member_map=balance_group_map,
        )

        for control in self._device_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            # Exclude non-running chargers.
            if control.controller.charge_control.instance_count == 0:
                continue

            all_member = self._create_group_member(control)
            active_member = deepcopy(all_member)
            balance_member = deepcopy(all_member)

            #####################################
            # Populate all member group with both active and paused chargers.
            # For paused charger allocations.
            #####################################
            self._populate_member_and_group_data(
                all_group_map, all_member, 0.0, exclude_paused=False
            )
            book.total_paused_instance += 1 if all_member.share_allocation == 0 else 0
            book.total_instance += all_member.instance
            book.total_max_power += all_member.max_power

            #####################################
            # Populate active member group with active chargers only.
            # For source of rebalance allocation.
            #####################################
            consumed_power = control.controller.solar_charge.get_consumed_power()
            self._populate_member_and_group_data(
                active_group_map, active_member, consumed_power, exclude_paused=True
            )
            book.total_active_instance += active_member.instance
            book.total_consumed_power += active_member.consumed_power

            #####################################
            # Populate balance member group with active chargers only.
            # For target of rebalance allocation.
            #####################################
            self._populate_member_and_group_data(
                balance_group_map, balance_member, 0.0, exclude_paused=True
            )

        book.net_power = net_power
        book.gross_power = net_power - book.total_consumed_power

        return book

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
        member: DeltaPowerAllocation,
        remain_power: float,
        weight: float,
        total_weight: float,
        net_power: float,
        is_delta_power: bool,
    ) -> float:

        # The following are updated:
        member.final_power = 0
        member.lack_power = 0

        if total_weight > 0:
            allocated_power = net_power * weight / total_weight

            # allocated_power can be -ve or +ve.
            # member.need_power can be -ve or 0, but not +ve.
            if allocated_power <= member.need_power:
                # Enough power: allocated_power = 0 or -ve
                # For paused device, allocated_power = need_power = lack_power = 0.
                member.final_power = member.need_power
                member.lack_power = 0
            else:
                # Not enough power: allocated_power is -ve or +ve
                if allocated_power < 0:
                    # Allocate power, ie. -ve
                    if (
                        member.consumed_power + abs(allocated_power)
                        >= member.min_workable_power
                    ):
                        # Available power must be above min workable power to be allocated,
                        # otherwise it is not workable.
                        # final_power = 0
                        # lack_power = 0 if gross allocation
                        # lack_power = x if delta allocation to get back from lower priority chargers.
                        member.final_power = max(allocated_power, member.need_power)
                        member.lack_power = max(
                            member.need_power - member.final_power,
                            -member.max_power,
                        )
                    else:
                        member.final_power = 0
                        if is_delta_power:
                            # Only try to get back lack power if performing delta power allocation.
                            propose_final_power = max(
                                allocated_power, member.need_power
                            )
                            member.lack_power = max(
                                member.need_power - propose_final_power,
                                -member.max_power,
                            )
                        else:
                            # Gross power allocation will get back nothing, so continue with allocation.
                            member.lack_power = 0

                else:
                    # Give back power, ie. +ve
                    member.final_power = min(allocated_power, member.consumed_power)
                    member.lack_power = max(
                        member.need_power - member.final_power,
                        -member.max_power,
                    )

            remain_power = remain_power - member.final_power

        rung.total_lack_power += member.lack_power

        return remain_power

    # ----------------------------------------------------------------------------
    def _allocate_power_to_group_member(
        self,
        rung: AllocationGroup,
        member: DeltaPowerAllocation,
        remain_power: float,
        net_power: float,
        is_delta_power: bool,
    ) -> float:
        """Allocate real power to running devices."""

        if net_power < 0:
            # Allocate power, ie. -ve
            remain_power = self._allocate_power_to_device(
                rung,
                member,
                remain_power,
                member.allocation_final_weight,
                rung.total_allocation_final_weight,
                net_power,
                is_delta_power,
            )
        else:
            # Give back power, ie. +ve
            remain_power = self._allocate_power_to_device(
                rung,
                member,
                remain_power,
                member.deallocation_final_weight,
                rung.total_deallocation_final_weight,
                net_power,
                is_delta_power,
            )

        return remain_power

    # ----------------------------------------------------------------------------
    def _allocate_power_to_group(
        self, rung: AllocationGroup, net_power: float, is_delta_power: bool
    ) -> float:
        """Allocate power to priority level.

        net_power: -ve = power to allocate, +ve = power to free up.
        """

        remain_power = net_power

        for member in rung.delta_allocations.values():
            remain_power = self._allocate_power_to_group_member(
                rung, member, remain_power, net_power, is_delta_power
            )

            if net_power < 0 and remain_power >= 0:
                # No more power to allocate.
                break

            if net_power >= 0 and remain_power <= 0:
                # No more power to free up.
                break

        return remain_power

    # ----------------------------------------------------------------------------
    def _bottom_up_release_power(
        self,
        allocation_ladder: list[AllocationGroup],
        net_power: float,  # ie. net_power is positive to free up power.
        is_delta_power: bool,
        end_rung: int = -1,  # inclusive, -1 means all the way to the top priority level.
    ) -> float:
        """Release power from lower to higher priority chargers up to and not including the end_rung priority level."""

        freeup_power = net_power

        # Excludes end_rung
        for idx in range(len(allocation_ladder) - 1, end_rung, -1):
            rung = allocation_ladder[idx]

            freeup_power = self._allocate_power_to_group(
                rung, freeup_power, is_delta_power
            )

            if freeup_power <= 0:
                break

        return freeup_power

    # ----------------------------------------------------------------------------
    def _top_down_allocate_power(
        self,
        allocation_ladder: list[AllocationGroup],
        net_power: float,  # ie. net_power is negative to allocate power.
        is_delta_power: bool,
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

            surplus_power = self._allocate_power_to_group(
                rung, surplus_power, is_delta_power
            )

            #####################################
            # Do not try to get back lack power. Let rebalance do the work!
            #####################################
            # if rung.total_lack_power < 0:
            #     # If allocating power, remain_power has been depleted because total_lack_power<0.
            #     power_to_free_up = rung.total_lack_power * -1
            #     remain_lack_power = self._bottom_up_release_power(
            #         allocation_ladder, power_to_free_up, is_delta_power, idx
            #     )
            #     freeup_power = power_to_free_up - remain_lack_power

            #     _LOGGER.debug(
            #         "Free up allocation: power_to_free_up=%s, remain_lack_power=%s, freeup_power=%s",
            #         power_to_free_up,
            #         remain_lack_power,
            #         freeup_power,
            #     )

            #     break

            if surplus_power >= 0:
                # No more power to allocate.
                break

        return surplus_power

    # ----------------------------------------------------------------------------
    def _process_allocation_map(
        self,
        allocation_map: dict[int, AllocationGroup],
        power: float,
        is_delta_power: bool,
        exclude_paused: bool,
    ) -> list[AllocationGroup]:
        """Process allocation group to determine final allocation for each device."""

        ladder = self._sorted_list_of_priority_level(allocation_map)

        if power < 0:
            unallocated_power = self._top_down_allocate_power(
                ladder, power, is_delta_power
            )
        else:
            unallocated_power = self._bottom_up_release_power(
                ladder, power, is_delta_power
            )

        _LOGGER.debug(
            "%s allocation: power=%s, unallocated_power=%s",
            "Active" if exclude_paused else "Plan",
            power,
            unallocated_power,
        )

        return ladder

    # ----------------------------------------------------------------------------
    async def _async_send_allocations(
        self,
        ladder: list[AllocationGroup],
        paused_only: bool,
    ) -> None:
        """Send allocated power to devices."""

        for rung in ladder:
            _LOGGER.debug("AllocationGroup: %s", rung)

            for member in rung.delta_allocations.values():
                control = self._device_controls[member.subentry_id]

                if control.controller.solar_charge.machine_state.state in [
                    RunState.ENDING,
                    RunState.ENDED,
                ]:
                    continue

                if not paused_only or (paused_only and member.share_allocation == 0):
                    # Paticipants in power sharing will use final_power.
                    # Non-participants will use plan_power as indication of possible available power.

                    # Writer will set entity value directly. Reader will get value via
                    # entity ID in options which can be overridden.
                    await async_set_delta_allocated_power(
                        control.controller.charge_control, member.final_power
                    )

                    if _LOGGER.isEnabledFor(logging.DEBUG):
                        _LOGGER.debug("PowerAllocation: %s", member)
                    else:
                        _LOGGER.warning(
                            "%s: final_power=%s, share_allocation=%s, consumed_power=%s, lack_power=%s",
                            member.name,
                            member.final_power,
                            member.share_allocation,
                            member.consumed_power,
                            member.lack_power,
                        )

    # ----------------------------------------------------------------------------
    def _rebalance_allocation_among_active_chargers(
        self,
        book: AllocationBook,
        active_ladder: list[AllocationGroup],
    ) -> list[AllocationGroup]:
        """Rebalance allocation among active chargers only."""

        rebalance_ladder = deepcopy(active_ladder)

        for rung in range(len(active_ladder)):
            for active_member in active_ladder[rung].delta_allocations.values():
                rebalance_member = rebalance_ladder[rung].delta_allocations[
                    active_member.subentry_id
                ]
                balance_member = book.balance_member_map[
                    active_member.priority
                ].delta_allocations[active_member.subentry_id]

                rebalance_member.final_power = balance_member.final_power - (
                    active_member.consumed_power * -1
                )

                _LOGGER.warning(
                    "%s: rebalance=%.2f, balance=%s, active=%s",
                    rebalance_member.name,
                    rebalance_member.final_power,
                    balance_member.final_power,
                    active_member.consumed_power * -1,
                )

        return rebalance_ladder

    # ----------------------------------------------------------------------------
    async def _async_process_allocation_book(self, book: AllocationBook) -> None:
        """Process allocation book."""

        _LOGGER.warning("AllocationBook: %s", book)

        # Allocation for active chargers.
        active_ladder = self._process_allocation_map(
            book.active_member_map,
            book.net_power,
            is_delta_power=True,
            exclude_paused=True,
        )

        # Rebalance allocation for all active chargers.
        self._process_allocation_map(
            book.balance_member_map,
            book.gross_power,
            is_delta_power=False,
            exclude_paused=True,
        )

        # Allocation for all running chargers including both active and paused chargers.
        all_ladder = self._process_allocation_map(
            book.all_member_map,
            book.gross_power,
            is_delta_power=False,
            exclude_paused=False,
        )

        rebalance_ladder = self._rebalance_allocation_among_active_chargers(
            book, active_ladder
        )

        await self._async_send_allocations(rebalance_ladder, paused_only=False)
        await self._async_send_allocations(all_ladder, paused_only=True)

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

        allocation_book = self._get_allocation_pool(net_power)

        if allocation_book.total_instance > 0:
            # Information only. Global default variable shows net power available for allocation.
            await async_set_delta_allocated_power(
                self._global_defaults_control.controller.charge_control, net_power
            )

            await self._async_process_allocation_book(allocation_book)

        else:
            _LOGGER.debug("No running charger for power allocation")
