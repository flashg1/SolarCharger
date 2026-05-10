"""Median data model."""

from dataclasses import dataclass
from datetime import datetime, timedelta


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class MedianDataPoint:
    """Data point."""

    # Value.
    value: float
    # Update period in seconds.
    period: float
    # Update time in local time.
    time: datetime

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of DataPoint."""

        return f"(val={self.value}, period={self.period}, time={self.time})"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class MedianData:
    """Median data structure for median calculation."""

    # Constant
    # Sample window duration.
    window: timedelta

    # Variables
    # Sequence of data points.
    sequence: list[MedianDataPoint]
    # Now time.
    now_time: datetime = datetime.min

    # Outputs
    sample_size: int = 0
    sample_duration: timedelta = timedelta.min

    # Median of value.
    median_value: float = 0
    # Simple moving average of value.
    sma_value: float = 0
    # Median of period.
    median_period: float = 0

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of MedianData."""
        return (
            f"window={self.window}, "
            f"now_time={self.now_time}, "
            f"sample_size={self.sample_size}, "
            f"sample_duration={self.sample_duration}, "
            f"median_value={self.median_value}, "
            f"sma_value={self.sma_value}, "
            f"median_period={self.median_period}, "
            f"sequence={self.sequence}"
        )
