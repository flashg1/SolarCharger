"""Power allocation data model."""

from dataclasses import dataclass


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class PowerAllocation:
    """Power allocation result."""

    subentry_id: str

    # Environment data:
    # Power currently consumed by the charger.
    consumed_power: float
    # Maximum power the charger can consume.
    max_power: float

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
    # Planned allocation as if all chargers are not paused.
    # plan_power is used by paused chargers to determine when to exit paused state.
    plan_weight: float = 0
    plan_power: float = 0

    # Final allocation with 0 share for paused chargers.
    # final_power is used by running chargers to adjust current.
    final_weight: float = 0
    final_power: float = 0
