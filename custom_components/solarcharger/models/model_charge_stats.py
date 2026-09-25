"""Charge statistics data model."""

from dataclasses import dataclass
from datetime import timedelta


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ChargeStats:
    """Data structure for charge stats. Persistent data across states."""

    #####################################
    # Loop stats
    #####################################
    # Loop success count. **MUST** start from 0 when starting state.
    loop_success_count: int = 0

    # Loop consecutive fail count. **MUST** start from 0 when starting state.
    loop_consecutive_fail_count: int = 0

    # Loop total fail count
    loop_total_fail_count: int = 0

    # Loop total count
    loop_total_count: int = 0

    #####################################
    # Stall stats
    #####################################
    # Stall total count
    stall_total_count: int = 0

    # Stall total duration
    stall_total_duration: timedelta = timedelta(seconds=0)

    # Stall average duration
    stall_average_duration: timedelta = timedelta(seconds=0)

    # Stall last duration
    stall_last_duration: timedelta = timedelta(seconds=0)

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of ChargeStats."""
        return (
            f"loop_success_count={self.loop_success_count}, "
            f"loop_consecutive_fail_count={self.loop_consecutive_fail_count}, "
            f"loop_total_fail_count={self.loop_total_fail_count}, "
            f"loop_total_success_count={self.loop_total_count - self.loop_total_fail_count}, "
            f"loop_total_count={self.loop_total_count}, "
            f"stall_total_count={self.stall_total_count}, "
            f"stall_total_duration={self.stall_total_duration}, "
            f"stall_average_duration={self.stall_average_duration}, "
            f"stall_last_duration={self.stall_last_duration}"
        )
