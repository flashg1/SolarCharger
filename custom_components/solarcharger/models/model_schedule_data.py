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
    day_index: int = -1
    use_charge_schedule: bool = False
    has_charge_endtime: bool = False
    charge_endtime: datetime = datetime.min

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

    # Duration in seconds to increase battery level by 1%
    one_percent_charge_duration: float = 0

    battery_soc: float | None = None

    # Requires battery_soc to calculate
    need_charge_duration: timedelta = timedelta.min

    # Must check has_charge_endtime and propose_charge_starttime before use.
    propose_charge_starttime: datetime = datetime.min

    # Is session started by timer?
    timer_session: bool = False

    # Include tomorrow for scheduling?
    include_tomorrow: bool = False

    # Started charging at max current. 0=not started, 1=started
    started_max_charge: int = 0

    # Current charge session
    # ======================
    # Is charge at max current now to avoid drift?
    # If charge end time is set, then set this to true if:
    # - there is not enough time to meet charge end time goal, or
    # - session is triggered by timer and it is night time.
    # Once started charging at max current, it will add 30-minute grace period to
    # avoid time drift stopping charge while charging.
    # This means charging can still pause during the day, but not at night.
    max_charge_now: bool = False

    # Next charge session
    # ===================
    # Schedule next session to start immediately at max current?
    # Only used when scheduling next charge session on completion of current session.
    # Actual proposed charge start time is required.
    # If charge end time is set, then set this to true if:
    # - there is not enough time to meet charge end time goal.
    start_next_session_now: bool = False

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of ScheduleData."""
        return (
            f"day_index={self.day_index}, "
            f"use_charge_schedule={self.use_charge_schedule}, "
            f"has_charge_endtime={self.has_charge_endtime}, charge_endtime={self.charge_endtime}, "
            f"propose_charge_starttime={self.propose_charge_starttime}, need_charge_duration={self.need_charge_duration}, "
            f"timer_session={self.timer_session}, include_tomorrow={self.include_tomorrow}, "
            f"started_max_charge={self.started_max_charge}, max_charge_now={self.max_charge_now}, "
            f"start_next_session_now={self.start_next_session_now}, "
            f"one_percent_charge_duration={self.one_percent_charge_duration}, battery_soc={self.battery_soc}, "
            f"old_charge_limit={self.old_charge_limit}, new_charge_limit={self.new_charge_limit}, "
            f"calibrate_max_charge_limit={self.calibrate_max_charge_limit}, "
            f"sun_elevation={self.sun_elevation}, sun_above_start_end_elevations={self.sun_above_start_end_elevations}, "
            f"data_timestamp={self.data_timestamp}, "
            f"{self.weekly_schedule}"
        )
