"""Data models."""

from dataclasses import dataclass


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ChargeStats:
    """Data structure for charge stats."""

    # Loop total count
    loop_total: int = 0

    # Loop success count
    loop_success: int = 0

    # Loop failure count
    loop_failure: int = 0

    # Consecutive failure count
    consecutive_failure_count: int = 0
