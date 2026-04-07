"""Data models."""

from dataclasses import dataclass
from datetime import timedelta


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ChargeStats:
    """Data structure for charge stats. Spans multiple machine states."""

    #####################################
    # Charge stats
    #####################################
    # Charge loop success count. **MUST** start from 0 when starting charge state.
    charge_loop_success_count: int = 0

    # Charge loop consecutive fail count. **MUST** start from 0 when starting charge state.
    charge_loop_consecutive_fail_count: int = 0

    # Charge loop total fail count
    charge_loop_total_fail_count: int = 0

    # Charge loop total count
    charge_loop_total_count: int = 0

    #####################################
    # Pause stats
    #####################################
    # Pause total count
    pause_total_count: int = 0

    # Pause total duration
    pause_total_duration: timedelta = timedelta(seconds=0)

    # Pause average duration
    pause_average_duration: timedelta = timedelta(seconds=0)

    def __repr__(self) -> str:
        """Return string representation of ScheduleData."""
        return (
            f"charge_loop_success_count={self.charge_loop_success_count}, "
            f"charge_loop_consecutive_fail_count={self.charge_loop_consecutive_fail_count}, "
            f"charge_loop_total_fail_count={self.charge_loop_total_fail_count}, "
            f"charge_loop_total_success_count={self.charge_loop_total_count - self.charge_loop_total_fail_count}, "
            f"charge_loop_total_count={self.charge_loop_total_count}, "
            f"pause_total_count={self.pause_total_count}, "
            f"pause_total_duration={self.pause_total_duration}, "
            f"pause_average_duration={self.pause_average_duration}"
        )
