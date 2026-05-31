"""Power allocation data model."""

from dataclasses import dataclass


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class PowerAllocation:
    """Power allocation data."""

    subentry_id: str
    name: str

    # Environment data:
    # Maximum power the charger can consume.
    max_power: float
    # Minimum power required for the charger to operate. Must be -ve for surplus power.
    activation_power: float
    adjusted_activation_power: float

    # Inputs:
    # Charger priority (0 = highest priority)
    priority: int
    # Allocation weight set by user (for both allocation and deallocation).
    allocation_weight: float

    # 0=No running instance, 1=Running instance
    # If instance is 0, then member can be ignored.
    instance: int

    # Set to 0 when charger is in paused state to stop charger from participating in real power allocation.
    # Paused charger will still participate in planned power allocation.
    # 1=Participate in real power allocation, 0=Do not participate in real power allocation
    share_allocation: int

    # Device can set current?
    can_set_current: bool

    # Device allows pause state?
    max_speed_charge: bool = False
    # Device paused by itself, eg. themostat.
    self_paused: bool = False
    # Charger effective voltage.
    voltage: float = 0.0
    # Power currently consumed by the charger.
    consumed_power: float = 0.0

    # Outputs:
    # -ve value means device needs power, +ve value means device has excess power.

    # need_power and lack_power can be -ve or 0, but not +ve.
    # Paused devices will have 0 need_power and 0 lack_power, as they are not participating in real power allocation.
    # Power requirement before allocation.
    need_power: float = 0.0
    # Resulting lack power after allocation.
    lack_power: float = 0.0

    # final_power is used by running chargers to adjust current.
    # final_power is used by paused chargers to determine when to exit paused state.
    allocation_final_weight: float = 0.0  # Use this weight for allocation.
    deallocation_final_weight: float = 0.0  # Use this weight for deallocation.
    final_power: float = 0.0

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of PowerAllocation."""
        return (
            f"name={self.name}, "
            f"max_power={self.max_power}, "
            f"adjusted_activation_power={self.adjusted_activation_power} ("
            f"{self.activation_power}), "
            f"priority={self.priority}, "
            f"allocation_weight={self.allocation_weight}, "
            f"instance={self.instance}, "
            f"share_allocation={self.share_allocation}, "
            f"can_set_current={self.can_set_current}, "
            f"max_speed_charge={self.max_speed_charge}, "
            f"self_paused={self.self_paused}, "
            f"voltage={self.voltage}, "
            f"consumed_power={self.consumed_power}, "
            f"need_power={self.need_power}, "
            f"lack_power={self.lack_power}, "
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
    member_map: dict[str, PowerAllocation]

    # +ve, total max power including paused chargers.
    total_max_power: float = 0
    # +ve
    total_consumed_power: float = 0

    # -ve/+ve, total need power before allocation.
    total_need_power: float = 0
    # -ve/+ve, total lack power after allocation.
    total_lack_power: float = 0

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
            f"total_allocation_final_weight={self.total_allocation_final_weight}, "
            f"total_deallocation_final_weight={self.total_deallocation_final_weight}, "
            f"total_instance={self.total_instance}"
        )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class AllocationBook:
    """Power allocation book."""

    # Map has active chargers only, for allocation/deallocation of the chargers.
    # Active group assumes all chargers in group has real consumed power data.
    active_group_map: dict[int, AllocationGroup]

    # Map has both active and paused chargers, and all will get allocations.
    # Used by paused chargers to determine when to exit paused state.
    # All group assumes all chargers in group has 0 consumed power.
    # - Gross power < 0, allocation is done according to the configs for each charger.
    # - Gross power >= 0, deallocation is 0 since consumed_power=0, hence final_power=0.
    all_group_map: dict[int, AllocationGroup]

    # Map has active chargers only, for rebalance allocation among the chargers.
    # Rebalance group assumes all chargers in group has 0 consumed power.
    rebalance_group_map: dict[int, AllocationGroup]

    total_active_instance: int = 0
    total_paused_instance: int = 0

    # Sum of active and paused instances.
    total_instance: int = 0

    # Sum of max power from active and paused chargers.
    total_max_power: float = 0.0

    # Sum of consumed power by active chargers.
    total_consumed_power: float = 0.0

    # Latest net power update. -ve value means excess power, +ve value means power shortage.
    net_power: float = 0.0

    # Sum of total_consumed_power and new net power update. -ve/+ve.
    gross_power: float = 0.0

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of AllocationBook."""
        return (
            f"active_instance={self.total_active_instance}, "
            f"paused_instance={self.total_paused_instance}, "
            f"total_instance={self.total_instance}, "
            f"max_power={self.total_max_power}, "
            f"consumed_power={self.total_consumed_power}, "
            f"net_power={self.net_power}, "
            f"gross_power={self.gross_power}"
        )
