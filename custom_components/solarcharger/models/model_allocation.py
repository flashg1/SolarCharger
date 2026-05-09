"""Power allocation data model."""

from dataclasses import dataclass


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class DeltaPowerAllocation:
    """Delta power allocation result."""

    subentry_id: str
    name: str

    # Environment data:
    # Maximum power the charger can consume.
    max_power: float
    # Power currently consumed by the charger.
    consumed_power: float

    # Inputs:
    # Charger priority (0 = highest priority)
    priority: int
    # Allocation weight set by user (for both allocation and deallocation).
    allocation_weight: float
    # Set to 0 when charger is in paused state to stop charger from participating in real power allocation.
    # Paused charger will still participate in planned power allocation.
    # 1=Participate in real power allocation, 0=Do not participate in real power allocation
    share_allocation: int

    # Outputs:
    # -ve value means device needs power, +ve value means device has excess power.

    # need_power and lack_power can be -ve or 0, but not +ve.
    # Paused devices will have 0 need_power and 0 lack_power, as they are not participating in real power allocation.
    # Power requirement before allocation.
    need_power: float = 0
    # Resulting lack power after allocation.
    lack_power: float = 0

    # Planned allocation as if all chargers are not paused.
    # plan_power is used by paused chargers to determine when to exit paused state.
    plan_weight: float = 0
    plan_power: float = 0

    # Final allocation with 0 share for paused chargers.
    # final_power is used by running chargers to adjust current.
    allocation_final_weight: float = 0  # Use this weight for allocation.
    deallocation_final_weight: float = 0  # Use this weight for deallocation.
    final_power: float = 0

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of DeltaPowerAllocation."""
        return (
            f"name={self.name}, "
            f"max_power={self.max_power}, "
            f"consumed_power={self.consumed_power}, "
            f"priority={self.priority}, "
            f"allocation_weight={self.allocation_weight}, "
            f"share_allocation={self.share_allocation}, "
            f"need_power={self.need_power}, "
            f"lack_power={self.lack_power}, "
            f"plan_weight={self.plan_weight}, "
            f"plan_power={self.plan_power}, "
            f"allocation_final_weight={self.allocation_final_weight}, "
            f"deallocation_final_weight={self.deallocation_final_weight}, "
            f"final_power={self.final_power}"
        )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class AllocationGroup:
    """Power allocation data for a priority level."""

    priority: int
    delta_allocations: list[DeltaPowerAllocation]

    # +ve, total max power including paused chargers.
    total_max_power: float = 0
    # +ve
    total_consumed_power: float = 0

    # -ve/+ve, total need power before allocation.
    total_need_power: float = 0
    # -ve/+ve, total lack power after allocation.
    total_lack_power: float = 0

    total_plan_weight: float = 0
    # Total allocation weight excluding paused chargers and chargers at max power.
    total_allocation_final_weight: float = 0
    # Total deallocation weight excluding paused chargers and chargers at zero power.
    total_deallocation_final_weight: float = 0
    # Total running instances including paused chargers.
    total_instance: int = 0

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of AllocationGroup."""
        return (
            f"priority={self.priority}, "
            f"total_max_power={self.total_max_power}, "
            f"total_consumed_power={self.total_consumed_power}, "
            f"total_need_power={self.total_need_power}, "
            f"total_lack_power={self.total_lack_power}, "
            f"total_plan_weight={self.total_plan_weight}, "
            f"total_allocation_final_weight={self.total_allocation_final_weight}, "
            f"total_deallocation_final_weight={self.total_deallocation_final_weight}, "
            f"total_instance={self.total_instance}"
        )
