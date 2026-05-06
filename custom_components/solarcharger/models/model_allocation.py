"""Power allocation data model."""

from dataclasses import dataclass


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class PowerAllocation:
    """Power allocation result."""

    subentry_id: str

    # Environment data:
    # Maximum power the charger can consume.
    max_power: float
    # Power currently consumed by the charger.
    consumed_power: float

    # Inputs:
    # Charger priority (0 = highest priority)
    priority: int
    # Allocation weight set by user
    allocation_weight: float
    # Set to 0 when charger is in paused state to stop charger from participating in real power allocation.
    # Paused charger will still participate in planned power allocation.
    # 1=Participate in real power allocation, 0=Do not participate in real power allocation
    share_allocation: int

    # Outputs:
    # -ve value means device needs power, +ve value means device has excess power.

    # need_power and lack_power can be -ve or 0, but not +ve.
    # Paused devices will have 0 need_power and 0 lack_power, as they are not participating in real power allocation.
    need_power: float = 0
    # Resulting lack power after allocation.
    lack_power: float = 0

    # Planned allocation as if all chargers are not paused.
    # plan_power is used by paused chargers to determine when to exit paused state.
    plan_weight: float = 0
    plan_power: float = 0

    # Final allocation with 0 share for paused chargers.
    # final_power is used by running chargers to adjust current.
    allocation_final_weight: float = 0
    deallocation_final_weight: float = 0
    final_power: float = 0


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class AllocationGroup:
    """Power allocation data for a priority level."""

    priority: int
    allocations: list[PowerAllocation]

    # +ve
    total_max_power: float = 0
    # +ve
    total_consumed_power: float = 0

    # -ve/+ve, total need power before allocation.
    total_need_power: float = 0
    # -ve/+ve, total lack power after allocation.
    total_lack_power: float = 0

    total_plan_weight: float = 0
    total_allocation_final_weight: float = 0
    total_deallocation_final_weight: float = 0
    total_instance: int = 0
