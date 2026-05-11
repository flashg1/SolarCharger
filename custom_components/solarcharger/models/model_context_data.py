# ruff: noqa: TID252
"""State machine context data model."""

from dataclasses import dataclass

# from datetime import datetime
from typing import Any

from ..chargers.chargeable import Chargeable
from ..chargers.charger import Charger
from ..const import ChargeStatus, RunState
from .model_charge_stats import ChargeStats
from .model_median_data import MedianData
from .model_schedule_data import ScheduleData


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ContextData:
    """Charging process context data."""

    charger: Charger
    chargeable: Chargeable

    #####################################
    # Inputs
    #####################################
    state: RunState
    goal: ScheduleData
    net_allocations: MedianData
    stats: ChargeStats

    #####################################
    # Outputs
    #####################################
    is_continue_state: bool = False  # Continue current state
    next_step: ChargeStatus = ChargeStatus.CHARGE_END
    is_enough_power: bool | None = None  # None=not enough data points.

    #####################################
    # Environment data
    #####################################
    is_connected: bool = False
    is_below_charge_limit: bool = False
    is_charging: bool = False
    charging_status: Any = ""
    is_sun_trigger: bool = False
    is_use_secondary_power_source: bool = False
    is_calibrate_max_charge_speed: bool = False

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of charging process conext data."""

        return (
            f"state={self.state.value}, "
            f"is_continue_state={self.is_continue_state}, "
            f"next_step={self.next_step.value} ("
            f"is_enough_power={self.is_enough_power}, "
            f"median_net_allocated_power={self.net_allocations.median_value}, "
            f"sample_size={self.net_allocations.sample_size}), "
            f"net_allocated_power={0 if self.net_allocations.last_data_point is None else self.net_allocations.last_data_point.value}, "
            f"is_connected={self.is_connected}, "
            f"is_below_charge_limit={self.is_below_charge_limit}, "
            f"is_charging={self.is_charging} ("
            f"{self.charging_status}), "
            f"is_sun_trigger={self.is_sun_trigger}, "
            f"is_sun_above_start_end_elevations={self.goal.sun_above_start_end_elevations}, "
            f"elevation={self.goal.sun_elevation}, "
            f"is_use_secondary_power_source={self.is_use_secondary_power_source}, "
            f"is_calibrate_max_charge_speed={self.is_calibrate_max_charge_speed}, "
            f"timer_session={self.goal.timer_session}, "
            f"has_charge_endtime={self.goal.has_charge_endtime}, "
            f"started_max_charge={self.goal.started_max_charge}, "
            f"max_charge_now={self.goal.max_charge_now}, "
            f"{self.stats}"
        )
