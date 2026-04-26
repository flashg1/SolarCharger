"""Schedule data model."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ChargeSchedule:
    """Daily charge schedule."""

    charge_day: str
    charge_limit: float
    charge_end_time: time

    def __repr__(self) -> str:
        """Return string representation of ChargeSchedule."""
        return f"({self.charge_day}: {self.charge_limit}, {self.charge_end_time})"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ScheduleData:
    """Charge limit schedule data."""

    weekly_schedule: list[ChargeSchedule]
    use_charge_schedule: bool = False
    has_charge_endtime: bool = False
    day_index: int = -1

    # Timestamp of current data
    data_timestamp: datetime = datetime.min

    # Sun elevation
    sun_above_start_end_elevations: bool = False
    sun_elevation: float = 0

    # Current device charge limit
    old_charge_limit: float = -1

    # New charge limit or from schedule
    new_charge_limit: float = -1

    # Charge limit for max charge speed calibration, which is set once on start of calibration, otherwise None.
    calibrate_max_charge_limit: float = -1

    charge_endtime = datetime.min

    battery_soc: float | None = None

    # Requires battery_soc to calculate
    need_charge_duration: timedelta = timedelta.min

    # Must check has_charge_endtime and propose_charge_starttime before use.
    propose_charge_starttime: datetime = datetime.min

    # Is session started by timer?
    timer_session: bool = False

    # Include tomorrow for scheduling?
    include_tomorrow: bool = False

    # Is charge to start immediately at max current?
    # If charge end time is set, immediate start is true if:
    # - there is not enough time to meet charge end time goal, or
    # - session is triggered by timer and it is night time.
    # This means charging can still pause during the day, but not at night.
    max_charge_now: bool = False

    def __repr__(self) -> str:
        """Return string representation of ScheduleData."""
        return (
            f"day_index={self.day_index}, "
            f"use_charge_schedule={self.use_charge_schedule}, "
            f"has_charge_endtime={self.has_charge_endtime}, charge_endtime={self.charge_endtime}, "
            f"propose_charge_starttime={self.propose_charge_starttime}, need_charge_duration={self.need_charge_duration}, "
            f"timer_session={self.timer_session}, include_tomorrow={self.include_tomorrow}, max_charge_now={self.max_charge_now}, "
            f"battery_soc={self.battery_soc}, "
            f"old_charge_limit={self.old_charge_limit}, new_charge_limit={self.new_charge_limit}, "
            f"calibrate_max_charge_limit={self.calibrate_max_charge_limit}, "
            f"sun_elevation={self.sun_elevation}, sun_above_start_end_elevations={self.sun_above_start_end_elevations}, "
            f"data_timestamp={self.data_timestamp}, "
            f"{self.weekly_schedule}"
        )
