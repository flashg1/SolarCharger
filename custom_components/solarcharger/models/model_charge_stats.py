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
    # Pause stats
    #####################################
    # Pause total count
    pause_total_count: int = 0

    # Pause total duration
    pause_total_duration: timedelta = timedelta(seconds=0)

    # Pause average duration
    pause_average_duration: timedelta = timedelta(seconds=0)

    # Pause last duration
    pause_last_duration: timedelta = timedelta(seconds=0)

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of ChargeStats."""
        return (
            f"loop_success_count={self.loop_success_count}, "
            f"loop_consecutive_fail_count={self.loop_consecutive_fail_count}, "
            f"loop_total_fail_count={self.loop_total_fail_count}, "
            f"loop_total_success_count={self.loop_total_count - self.loop_total_fail_count}, "
            f"loop_total_count={self.loop_total_count}, "
            f"pause_total_count={self.pause_total_count}, "
            f"pause_total_duration={self.pause_total_duration}, "
            f"pause_average_duration={self.pause_average_duration}, "
            f"pause_last_duration={self.pause_last_duration}"
        )
