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

    #####################################
    # Init
    #####################################
    # Sampling window in seconds.
    window_seconds: float
    # Sampling window duration.
    window_duration: timedelta
    # Sequence of data points.
    sequence: list[MedianDataPoint]

    #####################################
    # Variables
    #####################################
    # Last data point
    last_data_point: MedianDataPoint | None = None
    # Now time.
    now_time: datetime = datetime.min

    #####################################
    # Outputs
    #####################################
    # Data set is ready when window has full set of data.
    data_set_ready: bool = False
    # Sample size.
    sample_size: int = 0
    # Actual duration in samples.
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
            f"window_duration={self.window_duration}, "
            f"now_time={self.now_time}, "
            f"data_set_ready={self.data_set_ready}, "
            f"sample_size={self.sample_size}, "
            f"sample_duration={self.sample_duration}, "
            f"median_value={self.median_value}, "
            f"sma_value={self.sma_value}, "
            f"median_period={self.median_period}, "
            f"sequence={self.sequence}"
        )
