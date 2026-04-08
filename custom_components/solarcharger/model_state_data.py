"""State data models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .const import ChargeStatus, RunState
from .model_charge_stats import ChargeStats
from .sc_option_state import ScheduleData


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class StateData:
    """Charger state data."""

    # Inputs
    state: RunState
    goal: ScheduleData
    max_allocation_count: int
    power_allocations: list[float]
    stats: ChargeStats

    # Outputs
    is_continue_state: bool = False
    next_step: ChargeStatus = ChargeStatus.CHARGE_END
    is_enough_power: bool | None = None
    average_allocated_power: float = 0
    data_points: int = 0

    # Environment data
    is_connected: bool = False
    is_below_charge_limit: bool = False
    is_charging: bool = False
    charging_status: Any = ""
    is_sun_trigger: bool = False
    is_sun_above_start_end_elevations: bool = False
    elevation: float = 0
    is_use_secondary_power_source: bool = False
    is_calibrate_max_charge_speed: bool = False

    # Goal
    current_time_with_grace: datetime = datetime.min
    is_immediate_start_with_grace: bool = False

    def __repr__(self) -> str:
        """Return string representation of charger state data."""
        return (
            f"state={self.state.value}, "
            f"is_continue_state={self.is_continue_state}, "
            f"next_step={self.next_step.value} ("
            f"is_enough_power={self.is_enough_power}, "
            f"average_allocated_power={self.average_allocated_power}, "
            f"data_points={self.data_points}), "
            f"is_connected={self.is_connected}, "
            f"is_below_charge_limit={self.is_below_charge_limit}, "
            f"is_charging={self.is_charging} ("
            f"{self.charging_status}), "
            f"is_sun_trigger={self.is_sun_trigger}, "
            f"is_sun_above_start_end_elevations={self.is_sun_above_start_end_elevations}, "
            f"elevation={self.elevation}, "
            f"is_use_secondary_power_source={self.is_use_secondary_power_source}, "
            f"is_calibrate_max_charge_speed={self.is_calibrate_max_charge_speed}, "
            f"has_charge_endtime={self.goal.has_charge_endtime}, "
            f"is_immediate_start={self.goal.is_immediate_start}, "
            f"current_time_with_grace={self.current_time_with_grace}, "
            f"is_immediate_start_with_grace={self.is_immediate_start_with_grace}, "
            f"{self.stats}"
        )
