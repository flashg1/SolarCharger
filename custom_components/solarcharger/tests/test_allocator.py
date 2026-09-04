# ruff: noqa: SLF001
"""Unit tests for PowerAllocator (modules/allocator.py).

Tier 1 exercises the allocation ladder and pool-building logic in isolation,
using hand-built PowerAllocation/AllocationGroup fixtures.

Tier 2 exercises async_allocate_net_power end-to-end, including the
rebalance/loan-power path used for chargers that cannot adjust current.
The loan-power tests are characterization tests: the expected numbers were
obtained by running the current implementation rather than hand-derived, since
the rebalance/loan arithmetic is genuinely intricate (see the large blocks of
commented-out alternate implementations in allocator.py). They pin today's
behavior as a regression net; if the underlying algorithm is intentionally
reworked, these expected values will need to be recomputed, not just patched.
"""

from custom_components.solarcharger.const import (
    MAX_SPEED_CHARGE_PRIORITY,
    MAX_SPEED_CHARGE_PRIORITY_WEIGHT,
)
from custom_components.solarcharger.models.model_allocation import AllocationGroup
from custom_components.solarcharger.modules.allocator import PowerAllocator
import pytest

from .conftest import (
    GLOBAL_DEFAULTS_SUBENTRY_ID,
    make_allocator,
    make_device_control,
    make_group,
    make_power_allocation,
)


# ----------------------------------------------------------------------------
# Tier 1: _is_zero_power
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("power", "expected"),
    [
        pytest.param(0.0, True, id="zero"),
        pytest.param(9.99, True, id="just_inside_positive"),
        pytest.param(-9.99, True, id="just_inside_negative"),
        pytest.param(10.0, False, id="boundary_positive_is_exclusive"),
        pytest.param(-10.0, False, id="boundary_negative_is_exclusive"),
        pytest.param(15.0, False, id="outside_positive"),
    ],
)
def test_is_zero_power(power: float, expected: bool) -> None:
    """Power counts as zero only strictly within +/- the allowed variation."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._is_zero_power(10.0, power) is expected


# ----------------------------------------------------------------------------
# Tier 1: _allocate_power_to_device
# ----------------------------------------------------------------------------
def test_allocate_power_to_device_above_activation_power_takes_full_share() -> None:
    """A device with plenty of room takes its full proportional share."""
    allocator: PowerAllocator = make_allocator()
    rung: AllocationGroup = make_group()
    member = make_power_allocation(
        consumed_power=0,
        need_power=-2000,
        max_power=2000,
        adjusted_activation_power=-100,
    )

    remain_power = allocator._allocate_power_to_device(rung, member, -1000, 1, 1)

    assert member.final_power == -1000
    assert member.lack_power == -1000
    assert remain_power == 0
    assert rung.total_lack_power == -1000


def test_allocate_power_to_device_below_activation_power_takes_nothing() -> None:
    """A share too small to reach the activation power is declined outright, not partially taken."""
    allocator: PowerAllocator = make_allocator()
    rung: AllocationGroup = make_group()
    member = make_power_allocation(
        consumed_power=0,
        need_power=-2000,
        max_power=2000,
        adjusted_activation_power=-100,
    )

    remain_power = allocator._allocate_power_to_device(rung, member, -50, 1, 1)

    assert member.final_power == 0
    assert member.lack_power == -1950
    assert (
        remain_power == -50
    )  # Untouched, so the next device in the ladder can use it.


def test_allocate_power_to_device_max_speed_charge_bypasses_activation_gate() -> None:
    """max_speed_charge devices take their share even below their own activation power."""
    allocator: PowerAllocator = make_allocator()
    rung: AllocationGroup = make_group()
    member = make_power_allocation(
        consumed_power=0,
        need_power=-2000,
        max_power=2000,
        adjusted_activation_power=-1000,
        max_speed_charge=True,
    )

    remain_power = allocator._allocate_power_to_device(rung, member, -50, 1, 1)

    assert member.final_power == -50
    assert remain_power == 0


def test_allocate_power_to_device_give_back_capped_at_consumed_power() -> None:
    """Deallocation never asks a device to give back more than it is currently consuming."""
    allocator: PowerAllocator = make_allocator()
    rung: AllocationGroup = make_group()
    member = make_power_allocation(
        consumed_power=300, need_power=0, max_power=300, adjusted_activation_power=-100
    )

    remain_power = allocator._allocate_power_to_device(rung, member, 500, 1, 1)

    assert member.final_power == 300
    assert remain_power == 200


def test_allocate_power_to_device_zero_total_weight_is_a_noop() -> None:
    """With no allocation weight in play, the device's fields reset and remain_power is untouched."""
    allocator: PowerAllocator = make_allocator()
    rung: AllocationGroup = make_group()
    member = make_power_allocation(final_power=999, lack_power=999)

    remain_power = allocator._allocate_power_to_device(rung, member, -500, 0, 0)

    assert member.final_power == 0
    assert member.lack_power == 0
    assert remain_power == -500


# ----------------------------------------------------------------------------
# Tier 1: step power snapping (_allocate_step_power / _release_step_power)
# ----------------------------------------------------------------------------
STEP_POWER_LIST = [0, 6, 9, 12, 15]


def test_allocate_step_power_snaps_down_to_nearest_covered_step() -> None:
    """Allocation snaps down to the closest step at or below the ideal magnitude."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._allocate_step_power(-10, STEP_POWER_LIST) == -9


def test_allocate_step_power_exact_match_returns_same_value() -> None:
    """A magnitude that exactly matches a step is returned unchanged."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._allocate_step_power(-12, STEP_POWER_LIST) == -12


def test_allocate_step_power_falls_back_to_zero_when_no_step_is_low_enough() -> None:
    """A magnitude below every step (no 0 floor configured) allocates nothing rather than crashing."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._allocate_step_power(-3, [6, 9, 12, 15]) == 0


def test_allocate_step_power_passthrough_when_no_steps_configured() -> None:
    """With no step list, the ideal power is used as-is."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._allocate_step_power(-1000, []) == -1000


def test_release_step_power_snaps_up_to_nearest_covered_step() -> None:
    """Release snaps up to the closest step at or above the ideal magnitude."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._release_step_power(10, STEP_POWER_LIST) == 12


def test_release_step_power_exact_match_returns_same_value() -> None:
    """A magnitude that exactly matches a step is returned unchanged."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._release_step_power(12, STEP_POWER_LIST) == 12


def test_release_step_power_falls_back_to_highest_step_when_target_exceeds_every_step() -> (
    None
):
    """A magnitude above every step releases the largest step rather than crashing."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._release_step_power(20, STEP_POWER_LIST) == 15


def test_release_step_power_passthrough_when_no_steps_configured() -> None:
    """With no step list, the ideal power is used as-is."""
    allocator: PowerAllocator = make_allocator()

    assert allocator._release_step_power(10, []) == 10


def test_allocate_power_to_device_snaps_allocation_to_a_lower_step() -> None:
    """A stepped charger takes power in whole steps, never more than what was allocated."""
    allocator: PowerAllocator = make_allocator()
    rung: AllocationGroup = make_group()
    member = make_power_allocation(
        consumed_power=0,
        need_power=-2000,
        max_power=2000,
        adjusted_activation_power=-100,
        step_power_list=STEP_POWER_LIST,
    )

    remain_power = allocator._allocate_power_to_device(rung, member, -1000, 1, 1)

    assert member.final_power == -15  # Largest step at or below the 1000W share.
    assert member.lack_power == -1985
    assert remain_power == -985


def test_allocate_power_to_device_snaps_give_back_to_a_higher_step() -> None:
    """A stepped charger gives back power in whole steps, at least as much as was asked."""
    allocator: PowerAllocator = make_allocator()
    rung: AllocationGroup = make_group()
    member = make_power_allocation(
        consumed_power=15,
        need_power=0,
        max_power=15,
        adjusted_activation_power=-100,
        step_power_list=STEP_POWER_LIST,
    )

    remain_power = allocator._allocate_power_to_device(rung, member, 10, 1, 1)

    assert member.final_power == 12  # Smallest step at or above the requested 10W.
    assert remain_power == -2  # Slightly over-released; steps can't hit 10W exactly.


# ----------------------------------------------------------------------------
# Tier 1: multi-priority ladder cascading
# ----------------------------------------------------------------------------
def test_top_down_allocate_power_cascades_past_a_group_with_no_weight() -> None:
    """Surplus power skips a group that cannot currently absorb it and reaches the next."""
    allocator: PowerAllocator = make_allocator()
    blocked = make_power_allocation(
        subentry_id="blocked",
        priority=0,
        need_power=-500,
        max_power=500,
        allocation_final_weight=0,
    )
    rung_blocked = make_group(
        priority=0, member_map={"blocked": blocked}, total_allocation_final_weight=0
    )
    receiver = make_power_allocation(
        subentry_id="receiver",
        priority=5,
        need_power=-1000,
        max_power=1000,
        adjusted_activation_power=-100,
        allocation_final_weight=1,
    )
    rung_receiver = make_group(
        priority=5, member_map={"receiver": receiver}, total_allocation_final_weight=1
    )

    unallocated = allocator._top_down_allocate_power(
        [rung_blocked, rung_receiver], -800
    )

    assert unallocated == 0
    assert blocked.final_power == 0
    assert receiver.final_power == -800


def test_bottom_up_release_power_takes_from_lowest_priority_first() -> None:
    """Give-back is drained from the lowest-priority group before higher ones are touched."""
    allocator: PowerAllocator = make_allocator()
    high = make_power_allocation(
        subentry_id="high",
        priority=0,
        consumed_power=300,
        need_power=0,
        max_power=300,
        deallocation_final_weight=1,
    )
    rung_high = make_group(
        priority=0, member_map={"high": high}, total_deallocation_final_weight=1
    )
    low = make_power_allocation(
        subentry_id="low",
        priority=10,
        consumed_power=500,
        need_power=0,
        max_power=500,
        deallocation_final_weight=1,
    )
    rung_low = make_group(
        priority=10, member_map={"low": low}, total_deallocation_final_weight=1
    )

    unallocated = allocator._bottom_up_release_power([rung_high, rung_low], 700)

    assert unallocated == 0
    assert low.final_power == 500  # Fully drained first.
    assert (
        high.final_power == 200
    )  # Only the remainder comes from the higher-priority device.


def test_sorted_list_of_priority_level_orders_ascending() -> None:
    """Priority 0 (highest) sorts before larger, lower-priority numbers."""
    allocator: PowerAllocator = make_allocator()
    group_map = {
        10: make_group(priority=10),
        0: make_group(priority=0),
        5: make_group(priority=5),
    }

    ladder = allocator._sorted_list_of_priority_level(group_map)

    assert [group.priority for group in ladder] == [0, 5, 10]


# ----------------------------------------------------------------------------
# Tier 1: _get_allocation_pool exclusion and special-casing rules
# ----------------------------------------------------------------------------
def test_get_allocation_pool_excludes_non_running_devices() -> None:
    """A configured device with no running instance never enters the pool."""
    running = make_device_control("a", "Running", instance_count=1, priority=10)
    off = make_device_control("b", "Off", instance_count=0, priority=10)
    allocator = make_allocator(running, off, net_power=-1000)

    book = allocator._get_allocation_pool(-1000)

    assert book.total_instance == 1
    assert set(book.all_group_map[10].member_map) == {"a"}


def test_get_allocation_pool_keeps_paused_device_out_of_active_and_rebalance_groups() -> (
    None
):
    """Paused devices still get a theoretical allocation but do not share real power."""
    paused = make_device_control(
        "c", "Paused", instance_count=1, priority=20, share_allocation=0
    )
    active = make_device_control(
        "d", "Active", instance_count=1, priority=20, share_allocation=1
    )
    allocator = make_allocator(paused, active, net_power=-1000)

    book = allocator._get_allocation_pool(-1000)

    assert set(book.all_group_map[20].member_map) == {"c", "d"}
    assert set(book.active_group_map[20].member_map) == {"d"}
    assert set(book.rebalance_group_map[20].member_map) == {"d"}
    assert book.total_active_instance == 1
    assert book.total_paused_instance == 1


def test_get_allocation_pool_floors_negative_consumed_power_for_fixed_current_device() -> (
    None
):
    """A device that cannot set current never reports negative consumed power, and self-depowers below activation."""
    device = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=10,
        can_set_current=False,
        share_allocation=1,
        consumed_power=-20,
        adjusted_activation_power=-100,
    )
    allocator = make_allocator(device, net_power=-1000)

    book = allocator._get_allocation_pool(-1000)

    member = book.all_group_map[10].member_map["a"]
    assert member.consumed_power == 0
    assert member.share_allocation == 0


def test_get_allocation_pool_pins_max_power_to_consumed_power_for_fixed_current_device() -> (
    None
):
    """An active fixed-current device's max_power tracks what it is actually drawing."""
    device = make_device_control(
        "b",
        "B",
        instance_count=1,
        priority=11,
        can_set_current=False,
        share_allocation=1,
        consumed_power=150,
        adjusted_activation_power=-100,
        max_current=16,
        voltage=230,
        power_factor=1,
    )
    allocator = make_allocator(device, net_power=-1000)

    book = allocator._get_allocation_pool(-1000)

    member = book.all_group_map[11].member_map["b"]
    assert member.share_allocation == 1
    assert member.max_power == 150
    assert member.max_current == pytest.approx(150 / 230)


def test_get_allocation_pool_propagates_need_rebalance_flag_to_the_book() -> None:
    """A device flagged for rebalance clears its own flag and marks the whole book."""
    device = make_device_control("a", "A", instance_count=1, priority=10)
    device.controller.solar_charge.rebalance_needed = True
    allocator = make_allocator(device, net_power=-1000)

    book = allocator._get_allocation_pool(-1000)

    assert book.need_rebalance is True
    assert device.controller.solar_charge.rebalance_needed is False


def test_get_allocation_pool_overrides_priority_and_weight_for_max_speed_charge() -> (
    None
):
    """A max_speed_charge device gets system priority and weight, ignoring its own config."""
    device = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=99,
        allocation_weight=5,
        max_speed_charge=True,
    )
    allocator = make_allocator(device, net_power=-1000)

    book = allocator._get_allocation_pool(-1000)

    member = book.all_group_map[MAX_SPEED_CHARGE_PRIORITY].member_map["a"]
    assert member.priority == MAX_SPEED_CHARGE_PRIORITY
    assert member.allocation_weight == MAX_SPEED_CHARGE_PRIORITY_WEIGHT


# ----------------------------------------------------------------------------
# Tier 1: init_allocator
# ----------------------------------------------------------------------------
def test_init_allocator_resets_consumed_power_except_for_global_defaults() -> None:
    """Startup clears stale consumed-power readings for every real device, not the defaults control."""
    device_a = make_device_control("a", "A", instance_count=1, consumed_power=500)
    device_b = make_device_control("b", "B", instance_count=0, consumed_power=300)
    allocator = make_allocator(device_a, device_b, net_power=0)
    global_solar_charge = allocator._device_controls[
        GLOBAL_DEFAULTS_SUBENTRY_ID
    ].controller.solar_charge
    global_solar_charge.consumed_power = 777

    allocator.init_allocator()

    assert device_a.controller.solar_charge.consumed_power == 0.0
    assert device_b.controller.solar_charge.consumed_power == 0.0
    assert global_solar_charge.consumed_power == 777


# ----------------------------------------------------------------------------
# Tier 2: async_allocate_net_power end-to-end
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_async_allocate_net_power_splits_surplus_by_weight(
    allocation_calls: dict[int, float],
) -> None:
    """Equal-weight, same-priority devices split available surplus evenly."""
    dev_a = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    dev_b = make_device_control(
        "b",
        "B",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    allocator = make_allocator(dev_a, dev_b, net_power=-1000)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(dev_a.controller.charge_control)] == -500
    assert allocation_calls[id(dev_b.controller.charge_control)] == -500


@pytest.mark.asyncio
async def test_async_allocate_net_power_snaps_allocation_to_nearest_step(
    allocation_calls: dict[int, float],
) -> None:
    """A stepped charger's real allocated delta lands on a configured step, not a raw fraction."""
    device = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-1,
        activation_power=-1,
        step_power_list=STEP_POWER_LIST,
    )
    allocator = make_allocator(device, net_power=-10)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(device.controller.charge_control)] == -9


@pytest.mark.asyncio
async def test_async_allocate_net_power_higher_priority_is_filled_before_lower(
    allocation_calls: dict[int, float],
) -> None:
    """A higher-priority device takes what it can use; the rest cascades to lower priority."""
    dev_high = make_device_control(
        "high",
        "High",
        instance_count=1,
        priority=5,
        allocation_weight=1,
        max_current=400 / 230,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-50,
        activation_power=-50,
    )
    dev_low = make_device_control(
        "low",
        "Low",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-50,
        activation_power=-50,
    )
    allocator = make_allocator(dev_high, dev_low, net_power=-1000)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(dev_high.controller.charge_control)] == -400
    assert allocation_calls[id(dev_low.controller.charge_control)] == -600


# ----------------------------------------------------------------------------
# Tier 2: allocation with two current-settable devices
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_allocate_surplus_splits_evenly_between_two_settable_devices_of_equal_weight(
    allocation_calls: dict[int, float],
) -> None:
    """Two devices that can both adjust current split surplus in proportion to their weight."""
    dev_a = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    dev_b = make_device_control(
        "b",
        "B",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    allocator = make_allocator(dev_a, dev_b, net_power=-1200)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(dev_a.controller.charge_control)] == -600
    assert allocation_calls[id(dev_b.controller.charge_control)] == -600


@pytest.mark.asyncio
async def test_allocate_surplus_splits_proportionally_by_weight_between_two_settable_devices(
    allocation_calls: dict[int, float],
) -> None:
    """A device with twice the allocation weight takes twice the share of surplus."""
    dev_a = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=10,
        allocation_weight=2,
        can_set_current=True,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    dev_b = make_device_control(
        "b",
        "B",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    allocator = make_allocator(dev_a, dev_b, net_power=-900)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(dev_a.controller.charge_control)] == -600
    assert allocation_calls[id(dev_b.controller.charge_control)] == -300


# ----------------------------------------------------------------------------
# Tier 2: allocation with only one current-settable device
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_allocate_surplus_skips_fixed_current_device_at_same_priority(
    allocation_calls: dict[int, float],
) -> None:
    """A fixed-current device that is already running never receives *more* allocation.

    Its max_power is pinned to what it is already consuming (see
    _create_group_member's "cannot set current" handling), so its need_power is
    always 0 and it cannot absorb any of a surplus. The settable device gets the
    whole surplus, not just its nominal weighted share.
    """
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=500,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    settable_device = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-50,
        activation_power=-50,
    )
    allocator = make_allocator(fixed_current_device, settable_device, net_power=-1000)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 0
    assert allocation_calls[id(settable_device.controller.charge_control)] == -1000


@pytest.mark.asyncio
async def test_allocate_surplus_skips_fixed_current_device_regardless_of_its_priority(
    allocation_calls: dict[int, float],
) -> None:
    """The fixed-current device is skipped even when it has the higher priority.

    Unlike a device blocked by a zero allocation weight, this device is excluded
    by its need_power being pinned to 0, not by its priority rung being unable to
    absorb power -- so it does not matter which priority tier it sits in.
    """
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=5,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=500,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    settable_device = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-50,
        activation_power=-50,
    )
    allocator = make_allocator(fixed_current_device, settable_device, net_power=-1500)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 0
    assert allocation_calls[id(settable_device.controller.charge_control)] == -1500


@pytest.mark.asyncio
async def test_async_allocate_net_power_shortage_triggers_give_back(
    allocation_calls: dict[int, float],
) -> None:
    """A power shortage asks a running device to give back exactly the shortfall."""
    device = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-50,
        activation_power=-50,
        consumed_power=400,
    )
    allocator = make_allocator(device, net_power=300)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(device.controller.charge_control)] == 300


@pytest.mark.asyncio
async def test_async_allocate_net_power_dispatches_bottom_up_when_gross_power_is_positive(
    allocation_calls: dict[int, float],
) -> None:
    """A shortage that exceeds current consumption is dispatched to _bottom_up_release_power.

    gross_power = net_power - total_consumed_power. Every other end-to-end test
    in this file keeps gross_power <= 0 (dispatched to _top_down_allocate_power),
    even the "shortage" test above, because its net_power is still less than the
    device's own consumption. Here net_power exceeds total consumption, so
    _process_allocation_group takes its net_power > 0 branch for real -- though
    with nothing currently consumed, there is nothing to give back either way.
    """
    device = make_device_control(
        "a",
        "A",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-50,
        activation_power=-50,
        consumed_power=0,
    )
    allocator = make_allocator(device, net_power=1000)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(device.controller.charge_control)] == 0


@pytest.mark.asyncio
async def test_async_allocate_net_power_sends_nothing_with_no_running_chargers(
    allocation_calls: dict[int, float],
) -> None:
    """With no running chargers there is nothing to allocate, and the call reports failure."""
    device = make_device_control("a", "A", instance_count=0)
    allocator = make_allocator(device, net_power=-1000)

    assert not await allocator.async_allocate_net_power()
    assert allocation_calls == {}


@pytest.mark.asyncio
async def test_async_allocate_net_power_returns_false_when_net_power_unavailable(
    allocation_calls: dict[int, float],
) -> None:
    """When net power cannot be read, nothing is sent and the call reports failure."""
    device = make_device_control("a", "A", instance_count=1)
    allocator = make_allocator(device, net_power=None)

    assert not await allocator.async_allocate_net_power()
    assert allocation_calls == {}


# ----------------------------------------------------------------------------
# Tier 2: rebalance loan-power for fixed-current devices (characterization)
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_loan_partially_covers_the_gap_when_lender_has_limited_headroom(
    allocation_calls: dict[int, float],
) -> None:
    """A lender with only a little spare headroom lends that much, not the full loan.

    The fixed-current device is gated off (its ideal target is above its own
    activation power), so it needs 400W "loaned" from somewhere so other devices
    absorb the gap while it winds down. The lender here only has 10W of headroom
    above its own activation power, so it gives back 10W more than its own ideal
    target would ask for -- covering a fraction of the 400W loan, not all of it.
    This was previously (and misleadingly) named as if no lending occurred here;
    lending happens in every one of these tests, just by different amounts.
    """
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=400,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    lender = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        consumed_power=800,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-10,
        activation_power=-10,
    )
    allocator = make_allocator(fixed_current_device, lender, net_power=1100)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 400
    assert allocation_calls[id(lender.controller.charge_control)] == 790


@pytest.mark.asyncio
async def test_loan_absorbed_by_lender_with_spare_headroom(
    allocation_calls: dict[int, float],
) -> None:
    """A smaller activation-power floor lets the lender give back correspondingly more.

    Identical to the previous test except the lender's activation power is -5
    instead of -10: a smaller minimum-power floor, so it can safely give back
    5W more (795 instead of 790) while still staying above its own floor.
    """
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=400,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    lender = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        consumed_power=800,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-5,
        activation_power=-5,
    )
    allocator = make_allocator(fixed_current_device, lender, net_power=1100)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 400
    assert allocation_calls[id(lender.controller.charge_control)] == 795


@pytest.mark.asyncio
async def test_loan_not_needed_when_lender_has_ample_headroom(
    allocation_calls: dict[int, float],
) -> None:
    """A lender whose own target already clears its activation power lends nothing.

    Unlike the previous two tests, this lender's activation power (-1000) is far
    below its ideal target, so _temporarily_lend_power_until_borrower_is_paused's
    "member_lend_power < 0" check is false for it -- it is left completely
    unmodified even though the fixed-current device still needed a 400W loan
    that nobody ends up providing.
    """
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=400,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    lender = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        consumed_power=800,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-10,
        activation_power=-1000,
    )
    allocator = make_allocator(fixed_current_device, lender, net_power=1100)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 400
    assert allocation_calls[id(lender.controller.charge_control)] == 700


@pytest.mark.asyncio
async def test_loan_fully_satisfied_by_a_single_lender(
    allocation_calls: dict[int, float],
) -> None:
    """A lender with enough headroom covers the entire loan in one go.

    activation_power=310 here is not a physically realistic value (it should
    normally be negative -- see PowerAllocation.activation_power's docstring),
    but it is the cleanest way to push this lender's spare headroom past the
    400W loan so _temporarily_lend_power_until_borrower_is_paused's
    "freeup_power <= 0" branch (the loan is fully covered before the lending
    loop runs out of members) actually executes; every other test in this file
    lands in the partial-coverage branch instead.
    """
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=400,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    lender = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=True,
        consumed_power=800,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-10,
        activation_power=310,
    )
    allocator = make_allocator(fixed_current_device, lender, net_power=1100)

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 400
    assert allocation_calls[id(lender.controller.charge_control)] == 1100


@pytest.mark.asyncio
async def test_loan_skips_a_lender_below_the_system_priority_threshold(
    allocation_calls: dict[int, float],
) -> None:
    """A would-be lender at system priority (e.g. max-speed-charge) is never tapped for a loan.

    Same setup as test_loan_partially_covers_the_gap_when_lender_has_limited_headroom,
    except the lender's priority (3) is below USER_DEVICE_PRIORITY_START (5).
    _temporarily_lend_power_until_borrower_is_paused refuses to lend from system
    priority devices, so the lender is left at its own ideal target (700) instead
    of the 790 it would give back if it were an ordinary user-priority device.
    """
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=400,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    system_priority_lender = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=3,
        allocation_weight=1,
        can_set_current=True,
        consumed_power=800,
        max_current=32,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-10,
        activation_power=-10,
    )
    allocator = make_allocator(
        fixed_current_device, system_priority_lender, net_power=1100
    )

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 400
    assert allocation_calls[id(system_priority_lender.controller.charge_control)] == 700


@pytest.mark.asyncio
async def test_loan_is_reduced_by_leftover_surplus_from_the_rebalance_pass(
    allocation_calls: dict[int, float],
) -> None:
    """Surplus left over after the rebalance pass shrinks the loan before it is distributed.

    Three devices: Z is a small, high-priority device that saturates at its own
    100W cap; Y is the lender, priority below Z but capacity far above what it
    needs, so its own ideal target is stable regardless of how much trickles
    past it; X is the fixed-current borrower, lowest priority, needing a 400W
    loan. With this net_power, 50W of surplus reaches X's priority tier and is
    rejected (X can only take whole steps of its own consumption, not a mid-size
    top-up), leaving _process_allocation_group's rebalance pass with 50W
    unallocated. _rebalance_allocation_among_active_chargers reduces the 400W
    loan by that leftover before lending it out, so Y only has to cover 350W
    instead of 400W -- 50W less than test_loan_fully_satisfied_by_a_single_lender's
    sibling scenario without this leftover would give it.
    """
    saturating_device = make_device_control(
        "z",
        "Z",
        instance_count=1,
        priority=6,
        allocation_weight=1,
        can_set_current=True,
        consumed_power=0,
        max_current=100 / 230,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-1,
        activation_power=-1,
    )
    lender = make_device_control(
        "y",
        "Y",
        instance_count=1,
        priority=7,
        allocation_weight=1,
        can_set_current=True,
        consumed_power=800,
        max_current=7360 / 230,
        voltage=230,
        power_factor=1,
        adjusted_activation_power=-10,
        activation_power=500,
    )
    fixed_current_device = make_device_control(
        "x",
        "X",
        instance_count=1,
        priority=10,
        allocation_weight=1,
        can_set_current=False,
        consumed_power=400,
        adjusted_activation_power=-100,
        activation_power=-100,
    )
    allocator = make_allocator(
        saturating_device, lender, fixed_current_device, net_power=-6310
    )

    assert await allocator.async_allocate_net_power()

    assert allocation_calls[id(saturating_device.controller.charge_control)] == -100
    assert allocation_calls[id(lender.controller.charge_control)] == -6210
    assert allocation_calls[id(fixed_current_device.controller.charge_control)] == 400
