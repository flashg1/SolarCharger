"""Module to manage charge scheduling."""

from datetime import date, datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from ..const import (  # noqa: TID252
    CALIBRATE_MAX_SOC,
    CALIBRATE_SOC_INCREASE,
    CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE,
    NUMBER_CHARGER_MAX_SPEED,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
)
from ..exceptions.entity_exception import EntityExceptionError  # noqa: TID252
from ..sc_option_state import (  # noqa: TID252
    ChargeSchedule,
    ScheduleData,
    ScOptionState,
)
from ..utils import (  # noqa: TID252
    get_next_sunrise_time,
    get_sec_per_degree_sun_elevation,
)
from .chargeable import Chargeable

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# Look ahead charge limit list including today.
# Use MAX_CHARGE_LIMIT_DIFF to calculate charge limit for all days except one day before maximum charge limit day.
# The day before maximum charge limit day will use MIN_CHARGE_LIMIT_DIFF to minimise charge limit difference for the next day.
MIN_CHARGE_LIMIT_DIFF = 5
MAX_CHARGE_LIMIT_DIFF = 10
LOOK_AHEAD_CHARGE_LIMIT_DAYS = 4


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ChargeScheduler(ScOptionState):
    """Class to manage the charge scheduling."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the Charge instance."""

        caller = subentry.unique_id
        if caller is None:
            caller = __name__
        ScOptionState.__init__(self, hass, entry, subentry, caller)

        self._history_date = datetime(2026, 1, 1, 0, 0, 0)
        self.calibrate_max_charge_limit: float = -1

    # ----------------------------------------------------------------------------
    # Check if enough time to complete charge
    # ----------------------------------------------------------------------------
    def is_not_enough_time_to_complete_charge(
        self,
        chargeable: Chargeable,
        old_charge_current: float,
        charger_max_current: float,
        goal: ScheduleData,
    ) -> bool:
        """Is there not enough time to complete charging before scheduled end time?"""
        is_not_enough_time = False

        if goal.has_charge_endtime:
            now_time = self.get_local_datetime()
            available_charge_duration = goal.charge_endtime - now_time

            battery_soc = chargeable.get_state_of_charge()
            if battery_soc is None:
                return False

            charge_limit = chargeable.get_charge_limit()
            if charge_limit is None:
                return False

            need_charge_duration = self._calculate_need_charge_duration(
                battery_soc, charge_limit
            )

            charger_max_charge_speed = self.option_get_entity_number_or_abort(
                NUMBER_CHARGER_MAX_SPEED
            )
            # Duration in seconds to increase battery level by 1%
            one_percent_charge_duration = timedelta(
                seconds=60 * 60 / charger_max_charge_speed
            )

            # Maximise minimum charge current if charge end time is set and it is night time or
            # there is not enough time to charge, but only before charge end time.
            # chargerMinCurrent might bounce between 0 and chargerMaxCurrent due to
            # battery level not up-to-date or decimal inaccuracy, so stablise it to chargerMaxCurrent
            # if current is already at chargerMaxCurrent and needChargeDuration is only
            # slightly less than availableChargeDuration.
            is_not_enough_time = available_charge_duration.total_seconds() > 0 and (
                not self.is_daytime()
                or need_charge_duration >= available_charge_duration
                or (
                    (need_charge_duration + one_percent_charge_duration)
                    >= available_charge_duration
                    and round(old_charge_current) == round(charger_max_current)
                )
            )

        return is_not_enough_time

    # ----------------------------------------------------------------------------
    # Get schedule data
    # ----------------------------------------------------------------------------
    def _get_charge_limit_or_abort(self, chargeable: Chargeable) -> float:
        """Get charge limit from chargeable device or abort."""

        charge_limit = chargeable.get_charge_limit()
        if charge_limit is None:
            raise EntityExceptionError(
                f"{self._caller}: Cannot get charge limit from chargeable device"
            )

        return charge_limit

    # ----------------------------------------------------------------------------
    def _look_ahead_to_reduce_charge_limit_difference(self, goal: ScheduleData) -> None:
        """Look ahead to reduce charge limit difference between days."""

        # Automatically charge more today if today has no charge end time and next 3 days have much higher charge limit.
        if not goal.has_charge_endtime:
            look_ahead_schedule: list[ChargeSchedule] = []
            today_index = goal.day_index

            for i in range(0, LOOK_AHEAD_CHARGE_LIMIT_DAYS, 1):
                day_index = (today_index + i) % 7
                look_ahead_schedule.append(goal.weekly_schedule[day_index])

            # Find first occurance of maximum charge limit
            look_ahead_max_charge_limit = -1
            look_ahead_max_charge_limit_index = -1
            for i in range(len(look_ahead_schedule)):
                if look_ahead_schedule[i].charge_limit > look_ahead_max_charge_limit:
                    look_ahead_max_charge_limit = look_ahead_schedule[i].charge_limit
                    look_ahead_max_charge_limit_index = i

            if look_ahead_max_charge_limit_index == 1:
                look_ahead_charge_limit = (
                    look_ahead_max_charge_limit - MIN_CHARGE_LIMIT_DIFF
                )
            else:
                look_ahead_charge_limit = look_ahead_max_charge_limit - (
                    look_ahead_max_charge_limit_index * MAX_CHARGE_LIMIT_DIFF
                )

            if look_ahead_charge_limit > goal.new_charge_limit:  # noqa: PLR1730
                goal.new_charge_limit = look_ahead_charge_limit

    # ----------------------------------------------------------------------------
    def _calculate_need_charge_duration(
        self, battery_soc: float, charge_limit: float
    ) -> timedelta:
        """Calculate needed charge duration to reach charge limit."""

        charger_max_charge_speed = self.option_get_entity_number_or_abort(
            NUMBER_CHARGER_MAX_SPEED
        )
        # Duration in seconds to increase battery level by 1%
        one_percent_charge_duration = 60 * 60 / charger_max_charge_speed

        # SOC can be incorrect by 6% (approx. 1 hour) if required to charge to 100%
        extra_seconds = 0
        if charge_limit >= 100:
            extra_seconds = 6 * one_percent_charge_duration

        # Sometimes charge can decrease by 1% during charging at the beginning, so add extra onePercentChargeDuration for good measure.
        need_charge_seconds = (
            (charge_limit - battery_soc) * one_percent_charge_duration
            + one_percent_charge_duration
            + extra_seconds
        )

        _LOGGER.info(
            "%s: charge_limit=%.1f %%, "
            "battery_soc=%.1f %%, "
            "charger_max_charge_speed=%.1f %%/hr, "
            "one_percent_charge_duration=%.2f sec, ",
            self._caller,
            charge_limit,
            battery_soc,
            charger_max_charge_speed,
            one_percent_charge_duration,
        )

        return timedelta(seconds=need_charge_seconds)

    # ----------------------------------------------------------------------------
    def _calc_charge_starttime(self, goal: ScheduleData) -> None:
        """Calculate charge start time required to reach charge limit at charge end time."""

        if goal.has_charge_endtime:
            if goal.battery_soc is None:
                _LOGGER.info(
                    "%s: Unable to get battery SOC, cannot schedule next charge session",
                    self._caller,
                )
                return

            if goal.battery_soc >= goal.new_charge_limit:
                _LOGGER.info(
                    "%s: Battery SOC %.1f %% is at or above charge limit %.1f %%, no need to schedule next charge session",
                    self._caller,
                    goal.battery_soc,
                    goal.new_charge_limit,
                )
                return

            # Must check propose_charge_starttime before use due to return above, otherwise will get following exception when comparing times:
            # tesla_custom_tesla23m3: Abort charge: can't compare offset-naive and offset-aware datetimes
            goal.need_charge_duration = self._calculate_need_charge_duration(
                goal.battery_soc, goal.new_charge_limit
            )

            goal.propose_charge_starttime = (
                goal.charge_endtime - goal.need_charge_duration
            )

            if goal.propose_charge_starttime <= goal.data_timestamp:
                goal.is_immediate_start = True

    # ----------------------------------------------------------------------------
    def _get_soc_for_max_charge_speed_calibration(
        self, chargeable: Chargeable
    ) -> float:
        """Check and get SOC required for max charge speed calibration."""

        battery_soc = chargeable.get_state_of_charge()
        if battery_soc is None:
            raise EntityExceptionError(
                f"{self._caller}: Cannot calibrate max charge speed due to missing SOC sensor"
            )
        if battery_soc > CALIBRATE_MAX_SOC:
            raise EntityExceptionError(
                f"{self._caller}: Cannot calibrate max charge speed due to SOC > {CALIBRATE_MAX_SOC} %"
            )

        return battery_soc

    # ----------------------------------------------------------------------------
    async def _async_set_charge_limit_goal_if_calibration(
        self, chargeable: Chargeable, goal: ScheduleData, started_calibration: bool
    ) -> None:
        """Set new charge limit for calibration if required."""

        if self.is_calibrate_max_charge_speed():
            try:
                # Save calibration charge limit only once at start of calibration.
                if not started_calibration:
                    battery_soc = self._get_soc_for_max_charge_speed_calibration(
                        chargeable
                    )
                    self.calibrate_max_charge_limit = (
                        battery_soc + CALIBRATE_SOC_INCREASE
                    )

                goal.calibrate_max_charge_limit = self.calibrate_max_charge_limit

                # Set new charge limit if required
                min_charge_limit = self.get_min_charge_limit()
                if (
                    goal.new_charge_limit < self.calibrate_max_charge_limit
                    and self.calibrate_max_charge_limit >= min_charge_limit
                ):
                    goal.new_charge_limit = self.calibrate_max_charge_limit

            except EntityExceptionError as e:
                _LOGGER.error(
                    "%s: Cannot calibrate max charge speed: %s", self._caller, e
                )

    # ----------------------------------------------------------------------------
    def log_goal(self, goal: ScheduleData, msg: str = "") -> None:
        """Log schedule data."""

        _LOGGER.warning("%s: %s: ScheduleData: %s", self._caller, msg, goal)

    # ----------------------------------------------------------------------------
    # use_charge_schedule and has_charge_endtime are always set and correct.
    # If use_charge_schedule is true, all other parameters are set.
    # If use_charge_schedule is false, only has_charge_endtime is set. All others are not set.
    #
    # Timer-triggered automation usually need to run at night to meet charge limit at charge end time.
    # Timer-triggered automation will try to reach charge limit at charge end time using solar and/or grid.
    # For charge limit with charge end time, today = 00:00 to sunset, tomorrow = sunset to 00:00.
    # For charge limit without charge end time, today = 00:00 to 23:59.  Reaching charge limit is best effort only and depends on solar.
    async def async_get_schedule_data(
        self,
        chargeable: Chargeable,
        include_tomorrow: bool,
        started_calibration: bool,
        msg: str = "",
        log_it: bool = False,
    ) -> ScheduleData:
        """Calculate charge schedule data for today or tomorrow if session is started by timer."""

        goal = ScheduleData(weekly_schedule=[])
        # Ensure time is in local timezone
        now_time = self.get_local_datetime()
        goal.data_timestamp = now_time
        goal.old_charge_limit = self._get_charge_limit_or_abort(chargeable)
        goal.new_charge_limit = goal.old_charge_limit

        # Normal schedule
        if self.is_schedule_charge():
            goal.use_charge_schedule = True
            goal.weekly_schedule = self.get_weekly_schedule()

            # 0 = Monday, 6 = Sunday
            today_index = now_time.weekday()
            today_charge_limit = goal.weekly_schedule[today_index].charge_limit
            goal.day_index = today_index
            goal.new_charge_limit = today_charge_limit

            # Get today's schedule
            today_endtime = goal.weekly_schedule[today_index].charge_end_time
            if today_endtime != time.min:
                goal.charge_endtime = self.combine_local_date_time(
                    now_time.date(), today_endtime
                )
                if goal.charge_endtime > now_time:
                    goal.has_charge_endtime = True

            goal.battery_soc = chargeable.get_state_of_charge()

            # If today has no schedule or passed schedule, or if include_tomorrow, then get tomorrow's schedule.
            if not goal.has_charge_endtime:
                tomorrow_index = (today_index + 1) % 7
                tomorrow_charge_limit = goal.weekly_schedule[
                    tomorrow_index
                ].charge_limit
                tomorrow_endtime = goal.weekly_schedule[tomorrow_index].charge_end_time

                # _get_schedule_data() behaves differently when called for normal session, timer session and ending session.
                # Normal session: Started by anything except timer, so include_tomorrow=False.
                # Timer session: Started by timer only, so include_tomorrow=True.
                # Ending session: Called to calculate next trigger time, so include_tomorrow=True
                if (
                    # Use tomorrow's charge limit if time is between end elevation trigger and midnight, or include_tomorrow is true.
                    include_tomorrow
                    # or self._is_sun_between_end_elevation_trigger_and_sunset()
                    # or self.is_time_between_sunset_and_midnight()
                ):
                    if tomorrow_endtime != time.min:
                        # Use tomorrow's goal
                        goal.has_charge_endtime = True
                        goal.day_index = tomorrow_index
                        goal.new_charge_limit = tomorrow_charge_limit
                        goal.charge_endtime = self.combine_local_date_time(
                            now_time.date() + timedelta(days=1),
                            tomorrow_endtime,
                        )

            # Look ahead to reduce charge limit difference between days.
            if self.is_reduce_charge_limit_difference_between_days():
                self._look_ahead_to_reduce_charge_limit_difference(goal)

        # Modify goal charge limit if required calibration.
        await self._async_set_charge_limit_goal_if_calibration(
            chargeable, goal, started_calibration
        )

        # Calculate charge start time required to reach charge limit at charge end time.
        self._calc_charge_starttime(goal)

        if log_it:
            self.log_goal(goal, msg)

        return goal

    # ----------------------------------------------------------------------------
    # Schedule next charge session
    # ----------------------------------------------------------------------------
    async def _async_set_next_charge_time(self, next_charge_time: datetime) -> None:
        """Set next charge time."""

        # Note: Cannot set next_charge_time = datetime.min
        await self.async_set_datetime(
            self.next_charge_time_trigger_entity_id,
            next_charge_time,
        )

    # ----------------------------------------------------------------------------
    async def _async_clear_next_charge_time(self) -> None:
        """Clear next charge time trigger."""

        await self._async_set_next_charge_time(self._history_date)

    # ----------------------------------------------------------------------------
    # This is an estimated time only and could have unexpected results for edge cases.
    def _get_next_start_elevation_trigger_time(self) -> datetime:
        """Get next start elevation trigger time."""

        sun_state = self.get_sun_state_or_abort()
        sec_per_degree_sunrise: float = get_sec_per_degree_sun_elevation(
            self._caller, sun_state
        )
        elevation_start_trigger = self.option_get_entity_number_or_abort(
            NUMBER_SUNRISE_ELEVATION_START_TRIGGER
        )
        sunrise_offset = timedelta(
            seconds=(
                elevation_start_trigger + CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE
            )
            * sec_per_degree_sunrise
        )

        now_time = self.get_local_datetime()
        next_sunrise = get_next_sunrise_time(self._caller, sun_state)

        # Get today sunrise time
        next_start_elevation_trigger_time = (
            self.combine_local_date_time(
                now_time.date(),
                next_sunrise.time(),
            )
            + sunrise_offset
        )

        # Check if today start elevation trigger time has passed
        if now_time > next_start_elevation_trigger_time:
            next_start_elevation_trigger_time = next_sunrise + sunrise_offset

        return next_start_elevation_trigger_time

    # ----------------------------------------------------------------------------
    async def async_schedule_next_charge_session(
        self, chargeable: Chargeable, started_calibration: bool
    ) -> None:
        """Schedule next charge session."""

        next_goal = await self.async_get_schedule_data(
            chargeable,
            include_tomorrow=True,
            started_calibration=started_calibration,
            msg="Next",
            log_it=True,
        )
        if next_goal.use_charge_schedule:
            await self._async_clear_next_charge_time()

            if next_goal.has_charge_endtime:
                if next_goal.propose_charge_starttime != datetime.min:
                    if next_goal.is_immediate_start:
                        now_time = self.get_local_datetime()
                        next_starttime = now_time + timedelta(minutes=2)
                    else:
                        next_starttime = next_goal.propose_charge_starttime

                    next_start_elevation_trigger_time = (
                        self._get_next_start_elevation_trigger_time()
                    )

                    set_next_charge_time = (
                        next_starttime < next_start_elevation_trigger_time
                        or not self.is_sun_trigger()
                    )
                    if set_next_charge_time:
                        await self._async_set_next_charge_time(next_starttime)

                    _LOGGER.warning(
                        "%s: set_next_charge_time=%s, next_starttime=%s, next_start_elevation_trigger_time=%s",
                        self._caller,
                        set_next_charge_time,
                        next_starttime,
                        next_start_elevation_trigger_time,
                    )
