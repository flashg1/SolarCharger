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
    continue_state: bool = False  # Continue current state
    next_step: ChargeStatus = ChargeStatus.CHARGE_END
    enough_power: bool | None = None  # None=not enough data points.

    #####################################
    # Environment data
    #####################################
    connected: bool = False
    below_charge_limit: bool = False
    charging: bool = False
    charging_status: Any = ""
    fast_charge: bool = False
    calibrate_max_charge_speed: bool = False

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of charging process conext data."""

        return (
            f"state={self.state.value}, "
            f"continue_state={self.continue_state}, "
            f"next_step={self.next_step.value} ("
            f"enough_power={self.enough_power}, "
            f"median_net_allocated_power={self.net_allocations.median_value}, "
            f"sample_size={self.net_allocations.sample_size}), "
            f"net_allocated_power={0 if self.net_allocations.last_data_point is None else self.net_allocations.last_data_point.value}, "
            f"connected={self.connected}, "
            f"below_charge_limit={self.below_charge_limit} ({self.goal.battery_soc}/{self.goal.new_charge_limit}), "
            f"end_on_max_consumed_energy={self.goal.end_on_max_consumed_energy}, "
            f"below_max_consumed_energy={self.goal.below_max_consumed_energy} ({self.goal.consumed_energy}/{self.goal.max_consumed_energy}), "
            f"charging={self.charging} ({self.charging_status}), "
            f"sun_trigger={self.goal.sun_trigger}, "
            f"sun_above_start_end_elevations={self.goal.sun_above_start_end_elevations} ({self.goal.sun_elevation}), "
            f"fast_charge={self.fast_charge}, "
            f"calibrate_max_charge_speed={self.calibrate_max_charge_speed}, "
            f"timer_session={self.goal.timer_session}, "
            f"has_charge_endtime={self.goal.has_charge_endtime}, "
            f"started_max_charge={self.goal.started_max_charge}, "
            f"max_charge_now={self.goal.max_charge_now}, "
            f"{self.stats}"
        )
