# ruff: noqa: TID252
"""Power allocator implementation."""

from copy import deepcopy
import logging

from homeassistant.config_entries import ConfigSubentry

from ..const import (
    MAX_SPEED_CHARGE_PRIORITY,
    MAX_SPEED_CHARGE_PRIORITY_WEIGHT,
    OPTION_GLOBAL_DEFAULTS_ID,
    RunState,
)
from ..helpers.general import async_set_delta_allocated_power
from ..models.model_allocation import AllocationBook, AllocationGroup, PowerAllocation
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
    def init_allocator(self) -> None:
        """Initialize the power allocator."""

        for control in self._device_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            # This is required to stop the allocator from sending allocation during boot.
            # Best not to reset here since it is managed elsewhere.
            # async_update_sensor_state(
            #     control.controller.charge_control, SENSOR_INSTANCE_COUNT, 0
            # )
            # control.controller.solar_charge.give_up_real_power_allocation()

            # Best to reset consumed power to 0 in case value is not 0 before reboot.
            control.controller.solar_charge.set_consumed_power(0.0)

    # ----------------------------------------------------------------------------
    def _is_zero_power(self, power: float) -> bool:

        return power > -20 and power < 20

    # ----------------------------------------------------------------------------
    def _create_group_member(
        self, control: DeviceControl, consumed_power: float
    ) -> PowerAllocation:
        """Create member from config. Note allocation weight entity can be overriden."""

        # The following are user configurable and can be overridden, so use indirection.
        priority = control.controller.solar_charge.get_charger_priority()
        allocation_weight = (
            control.controller.solar_charge.get_charger_power_allocation_weight()
        )
        max_current = control.controller.solar_charge.get_charger_max_current()
        voltage = control.controller.solar_charge.get_charger_effective_voltage()
        max_power = max_current * voltage

        # Participate in power allocation.
        instance = control.controller.charge_control.instance_count

        # Device pause state.
        can_set_current = control.controller.solar_charge.can_set_current
        share_allocation = control.controller.solar_charge.get_share_allocation()
        self_paused = control.controller.solar_charge.is_self_paused
        if (
            # not can_set_current
            # and share_allocation == 1
            # and self._is_zero_power(consumed_power)
            self_paused
        ):
            #####################################
            # Device in charging state but consumed 0 power,
            # and can read current but not set current, so no participation,
            # ie. device is in self-imposed paused state.
            # Setting share_allocation=0 to ensure device do not participate
            # in allocation/deallocation and receives planned allocations.
            #####################################
            share_allocation = 0
            consumed_power = 0

        adjusted_activation_power, activation_power = (
            control.controller.solar_charge.get_adjusted_activation_power(
                RunState.PAUSED if share_allocation == 0 else RunState.CHARGING
            )
        )
        max_speed_charge = control.controller.solar_charge.is_max_speed_charge()

        # Chargers that requires charging at max speed has system priority and equal weight.
        # This is to ensure they are allocated first over others even if others have higher priority set by user.
        # Otherwise others with higher priority set by user will get allocation and try to charge!
        if max_speed_charge:
            priority = MAX_SPEED_CHARGE_PRIORITY
            allocation_weight = MAX_SPEED_CHARGE_PRIORITY_WEIGHT

        member = PowerAllocation(
            subentry_id=control.subentry_id,
            name=control.config_name,
            max_power=max_power,
            activation_power=activation_power,
            adjusted_activation_power=adjusted_activation_power,
            priority=priority,
            allocation_weight=allocation_weight,
            instance=instance,
            share_allocation=share_allocation,
            can_set_current=can_set_current,
            max_speed_charge=max_speed_charge,
            self_paused=self_paused,
            voltage=voltage,
        )
        member.consumed_power = consumed_power

        return member

    # ----------------------------------------------------------------------------
    def _populate_member_and_group_data(
        self,
        group_map: dict[int, AllocationGroup],
        member: PowerAllocation,
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
        #   can get a bigger share. This is not perfect since device might just be at below max
        #   power and get allocated more than required. So both remain power and total weight will
        #   also be adjusted for subsequent allocations to fully utilize the power.
        # - Ensure devices at zero power do not participate in deallocation, so that other devices
        #   can get a bigger share. Similar to allocation, remain power and total weight will
        #   also be adjusted for subsequent deallocations to fully utilize the power.
        #######################################################
        if consumed_power < member.max_power:
            #####################################
            # Participate in allocation and possibly deallocation.
            #####################################
            member.allocation_final_weight = final_weight

            # Paused device has need_power = lack_power = consumed_power = 0.
            if member.allocation_final_weight > 0:
                member.need_power = consumed_power - member.max_power

            # Only participate in deallocation if consumed power > 0
            if consumed_power > 0:
                member.deallocation_final_weight = final_weight

        else:
            #####################################
            # Participate in deallocation only.
            #####################################
            member.deallocation_final_weight = final_weight

        group = group_map.get(member.priority)
        if group is None:
            group = AllocationGroup(priority=member.priority, member_map={})
            group_map[member.priority] = group

        group.member_map[member.subentry_id] = member
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
        rebalance_group_map: dict[int, AllocationGroup] = {}
        book: AllocationBook = AllocationBook(
            active_group_map=active_group_map,
            all_group_map=all_group_map,
            rebalance_group_map=rebalance_group_map,
        )

        for control in self._device_controls.values():
            if control.config_name == OPTION_GLOBAL_DEFAULTS_ID:
                continue

            # Exclude non-running chargers.
            if control.controller.charge_control.instance_count == 0:
                continue

            # Get final consumed power from member and then reset to 0.
            consumed_power = control.controller.solar_charge.get_consumed_power()
            all_member = self._create_group_member(control, consumed_power)
            consumed_power = all_member.consumed_power
            all_member.consumed_power = 0

            active_member = deepcopy(all_member)
            rebalance_member = deepcopy(all_member)

            #####################################
            # Populate all member group with both active and paused chargers.
            # For paused charger allocations.
            #####################################
            self._populate_member_and_group_data(
                all_group_map,
                all_member,
                0,
                exclude_paused=False,
            )

            if all_member.share_allocation == 0:
                book.total_paused_instance += 1
            else:
                book.total_active_instance += 1
            book.total_instance += 1
            book.total_max_power += all_member.max_power

            #####################################
            # Populate active member group with active chargers only.
            # For source of rebalance allocation.
            # Only this group can be used for direct deallocation. Not required since using rebalance.
            #####################################
            self._populate_member_and_group_data(
                active_group_map,
                active_member,
                consumed_power,
                exclude_paused=True,
            )

            book.total_consumed_power += active_member.consumed_power

            #####################################
            # Populate rebalance member group with active chargers only.
            # For target of rebalance allocation.
            #####################################
            self._populate_member_and_group_data(
                rebalance_group_map,
                rebalance_member,
                0,
                exclude_paused=True,
            )

        book.net_power = net_power
        book.gross_power = net_power - book.total_consumed_power

        return book

    # ----------------------------------------------------------------------------
    def _sorted_list_of_priority_level(
        self, group_map: dict[int, AllocationGroup]
    ) -> list[AllocationGroup]:
        """Get sorted list of priority level from allocation map."""

        return [group_map[priority] for priority in sorted(group_map.keys())]

    # ----------------------------------------------------------------------------
    def _allocate_power_to_device(
        self,
        rung: AllocationGroup,
        member: PowerAllocation,
        remain_power: float,
        weight: float,
        total_weight: float,
    ) -> float:

        # The following are updated:
        member.final_power = 0
        member.lack_power = 0

        if total_weight > 0:
            allocated_power = remain_power * weight / total_weight

            # allocated_power can be -ve or +ve.
            # member.need_power can be -ve or 0, but not +ve.
            # For paused device, allocated_power = need_power = lack_power = 0.
            if allocated_power <= 0:
                #####################################
                # Allocate power, ie. -ve
                #####################################
                if member.max_speed_charge or member.consumed_power + abs(
                    allocated_power
                ) >= abs(member.adjusted_activation_power):
                    #####################################
                    # Only allocate if charge at max speed or above activation power.
                    #####################################
                    member.final_power = max(allocated_power, member.need_power)
                    member.lack_power = max(
                        member.need_power - member.final_power,
                        -member.max_power,
                    )
                else:
                    #####################################
                    # Less than min workable power, so take nothing.
                    #####################################
                    member.final_power = 0
                    propose_final_power = max(allocated_power, member.need_power)
                    member.lack_power = max(
                        member.need_power - propose_final_power,
                        -member.max_power,
                    )

            else:
                #####################################
                # Give back power, ie. +ve
                #####################################
                # Up to the charger to decide what to do if charger is below
                # min workable power after deallocation.
                # Should not try to take back all power here.
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
        member: PowerAllocation,
        remain_power: float,
        total_weight: float,
        original_power: float,
    ) -> tuple[float, float]:
        """Allocate real power to running devices.

        To ensure maximum utilization of net power, only take what power is required
        and remove member weight for next allocation.
        """

        if original_power <= 0:
            # Allocate power, ie. -ve
            member_weight = member.allocation_final_weight
            remain_power = self._allocate_power_to_device(
                rung,
                member,
                remain_power,
                member_weight,
                total_weight,
            )
        else:
            # Give back power, ie. +ve
            member_weight = member.deallocation_final_weight
            remain_power = self._allocate_power_to_device(
                rung,
                member,
                remain_power,
                member_weight,
                total_weight,
            )

        return remain_power, (total_weight - member_weight)

    # ----------------------------------------------------------------------------
    def _allocate_power_to_group(
        self, rung: AllocationGroup, original_power: float
    ) -> float:
        """Allocate power to priority level.

        net_power: -ve = power to allocate, +ve = power to free up.
        """

        remain_power = original_power
        if original_power <= 0:
            total_weight = rung.total_allocation_final_weight
        else:
            total_weight = rung.total_deallocation_final_weight

        for member in rung.member_map.values():
            remain_power, total_weight = self._allocate_power_to_group_member(
                rung, member, remain_power, total_weight, original_power
            )

            if original_power <= 0 and remain_power >= 0:
                # No more power to allocate.
                break

            if original_power > 0 and remain_power <= 0:
                # No more power to free up.
                break

        return remain_power

    # ----------------------------------------------------------------------------
    def _bottom_up_release_power(
        self,
        ladder: list[AllocationGroup],
        net_power: float,  # ie. net_power is positive to free up power.
        end_rung: int = -1,  # inclusive, -1 means all the way to the top priority level.
    ) -> float:
        """Release power from lower to higher priority chargers up to and not including the end_rung priority level."""

        freeup_power = net_power

        # Excludes end_rung
        for idx in range(len(ladder) - 1, end_rung, -1):
            rung = ladder[idx]

            freeup_power = self._allocate_power_to_group(rung, freeup_power)

            if freeup_power <= 0:
                break

        return freeup_power

    # ----------------------------------------------------------------------------
    def _top_down_allocate_power(
        self,
        ladder: list[AllocationGroup],
        net_power: float,  # ie. net_power is negative or zero to allocate power.
    ) -> float:
        """Allocate power from higher to lower priority chargers.

        Allocate power from higher to lower priority chargers when there is enough power.
        If higher priority chargers do not have enough power, free up power from lower to
        higher priority chargers for next allocation.
        """

        surplus_power = net_power

        # Includes start_rung
        for idx in range(len(ladder)):
            rung = ladder[idx]

            surplus_power = self._allocate_power_to_group(rung, surplus_power)

            #####################################
            # Do not try to get back lack power. Let rebalance do the work!
            #####################################
            # if rung.total_lack_power < 0:
            #     # If allocating power, remain_power has been depleted because total_lack_power<0.
            #     power_to_free_up = rung.total_lack_power * -1
            #     remain_lack_power = self._bottom_up_release_power(
            #         ladder, power_to_free_up, idx
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
    def _process_allocation_group(
        self,
        group_map: dict[int, AllocationGroup],
        net_power: float,
        allocation_type: str,
    ) -> list[AllocationGroup]:
        """Process allocation group to determine final allocation for each device."""

        ladder = self._sorted_list_of_priority_level(group_map)

        if net_power <= 0:
            unallocated_power = self._top_down_allocate_power(ladder, net_power)
        else:
            unallocated_power = self._bottom_up_release_power(ladder, net_power)

        _LOGGER.debug(
            "%s %s: net_power=%s, unallocated_power=%s",
            allocation_type,
            "allocation" if net_power <= 0 else "deallocation",
            net_power,
            unallocated_power,
        )

        return ladder

    # ----------------------------------------------------------------------------
    def _get_member_state(self, member: PowerAllocation) -> str:
        """Get member state string."""

        if member.share_allocation == 0:
            if member.self_paused:
                member_state = "Self-paused"
            else:
                member_state = "Paused"
        else:
            member_state = "Active"

        return member_state

    # ----------------------------------------------------------------------------
    async def _async_send_allocations(
        self, ladder: list[AllocationGroup], paused_only: bool, log: bool
    ) -> None:
        """Send allocated power to devices."""

        for rung in ladder:
            _LOGGER.debug("AllocationGroup: %s", rung)

            for member in rung.member_map.values():
                control = self._device_controls[member.subentry_id]

                if control.controller.solar_charge.machine_state.state in [
                    RunState.ENDING,
                    RunState.ENDED,
                ]:
                    continue

                if not paused_only or (paused_only and member.share_allocation == 0):
                    # Paticipants in power sharing will use final_power.
                    # Non-participants will use final_power as indication of possible available power.

                    # Writer will set entity value directly. Reader will get value via
                    # entity ID in options which can be overridden.
                    await async_set_delta_allocated_power(
                        control.controller.charge_control, member.final_power
                    )

                    if _LOGGER.isEnabledFor(logging.DEBUG):
                        _LOGGER.debug("PowerAllocation: %s", member)
                    elif log:
                        _LOGGER.info(
                            "%s: priority=%s, state=%s, consumed_power=%.2f, allocated_power=%.2f, adjusted_activation_power=%.2f (%.2f)",
                            member.name,
                            member.priority,
                            self._get_member_state(member),
                            member.consumed_power,
                            member.final_power,
                            member.adjusted_activation_power,
                            member.activation_power,
                        )

    # ----------------------------------------------------------------------------
    def _rebalance_allocation_among_active_chargers(
        self,
        book: AllocationBook,
        active_ladder: list[AllocationGroup],
    ) -> list[AllocationGroup]:
        """Rebalance allocation among active chargers only."""

        rebalance_active_ladder = deepcopy(active_ladder)

        for rung in range(len(active_ladder)):
            for active_member in active_ladder[rung].member_map.values():
                rebalance_active_member = rebalance_active_ladder[rung].member_map[
                    active_member.subentry_id
                ]
                rebalance_member = book.rebalance_group_map[
                    active_member.priority
                ].member_map[active_member.subentry_id]

                rebalance_active_member.final_power = rebalance_member.final_power - (
                    active_member.consumed_power * -1
                )

                _LOGGER.info(
                    "%s: priority=%s, state=%s, from=%.2f, to=%.2f, rebalance=%.2f, adjusted_activation_power=%.2f (%.2f)",
                    rebalance_active_member.name,
                    rebalance_active_member.priority,
                    self._get_member_state(rebalance_active_member),
                    rebalance_active_member.consumed_power * -1,  # From
                    rebalance_member.final_power,  # To
                    rebalance_active_member.final_power,  # Rebalance
                    rebalance_active_member.adjusted_activation_power,
                    rebalance_active_member.activation_power,
                )

        return rebalance_active_ladder

    # ----------------------------------------------------------------------------
    async def _async_process_allocation_book(self, book: AllocationBook) -> None:
        """Process allocation book."""

        _LOGGER.info("AllocationBook: %s", book)

        # Allocation for all running chargers including both active and paused chargers.
        all_ladder = self._process_allocation_group(
            book.all_group_map,
            book.gross_power,
            allocation_type="Plan",
        )

        # Gross power less than or equal to zero is considered an allocation.
        if book.gross_power <= 0:
            #####################################
            # Allocation - Rebalance
            #####################################
            active_ladder = self._sorted_list_of_priority_level(book.active_group_map)

            # Rebalance allocation for all active chargers.
            self._process_allocation_group(
                book.rebalance_group_map,
                book.gross_power,
                allocation_type="Rebalance",
            )
            rebalance_active_ladder = self._rebalance_allocation_among_active_chargers(
                book, active_ladder
            )

            await self._async_send_allocations(
                rebalance_active_ladder, paused_only=False, log=False
            )
            await self._async_send_allocations(all_ladder, paused_only=True, log=True)

        else:
            #####################################
            # Deallocation
            #####################################
            # Must deallocate using active group because it has consumed power info.
            # Do not rebalance since those groups do not have consumed power info.
            active_ladder = self._process_allocation_group(
                book.active_group_map,
                book.net_power,
                allocation_type="Delta",
            )

            await self._async_send_allocations(
                active_ladder, paused_only=False, log=True
            )
            await self._async_send_allocations(all_ladder, paused_only=True, log=True)

    # ----------------------------------------------------------------------------
    async def async_allocate_net_power(self) -> None:
        """Calculate power allocation. Power allocation weight can be 0."""
        ok: bool = False

        net_power = (
            self._global_defaults_control.controller.solar_charge.get_net_power()
        )

        if net_power is not None:
            allocation_book = self._get_allocation_pool(net_power)

            if allocation_book.total_instance > 0:
                # Information only. Global default variable shows net power available for allocation.
                await async_set_delta_allocated_power(
                    self._global_defaults_control.controller.charge_control, net_power
                )

                await self._async_process_allocation_book(allocation_book)
                ok = True

            else:
                _LOGGER.debug("No running charger for power allocation")
        else:
            _LOGGER.warning("Cannot get net power. Try next cycle.")

        return ok
