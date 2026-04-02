"""Power allocation data model."""

from dataclasses import dataclass


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class PowerAllocation:
    """Power allocation result."""

    subentry_id: str

    # Environment data
    consumed_power: float  # Power currently consumed by the charger
    max_power: float  # Maximum power the charger can consume

    # Inputs
    allocation_weight: float
    share_allocation: int  # 1=Participate in allocation, 0=Ignore

    # Outputs
    # Planned allocation as if all chargers are not paused.
    plan_weight: float = 0
    plan_power: float = 0

    # Final allocation with zero allocation to paused chargers.
    final_weight: float = 0
    final_power: float = 0
