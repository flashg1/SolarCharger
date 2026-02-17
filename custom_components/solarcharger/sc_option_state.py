"""SolarCharger entity state using config from config_entry.options and config_subentry."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import json
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, State

from .config_utils import get_saved_option_value
from .const import (
    DATETIME,
    DATETIME_NEXT_CHARGE_TIME,
    NUMBER_CHARGE_LIMIT_FRIDAY,
    NUMBER_CHARGE_LIMIT_MONDAY,
    NUMBER_CHARGE_LIMIT_SATURDAY,
    NUMBER_CHARGE_LIMIT_SUNDAY,
    NUMBER_CHARGE_LIMIT_THURSDAY,
    NUMBER_CHARGE_LIMIT_TUESDAY,
    NUMBER_CHARGE_LIMIT_WEDNESDAY,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
    NUMBER_SUNSET_ELEVATION_END_TRIGGER,
    SWITCH,
    SWITCH_CALIBRATE_MAX_CHARGE_SPEED,
    SWITCH_CHARGE,
    SWITCH_FAST_CHARGE_MODE,
    SWITCH_PLUGIN_TRIGGER,
    SWITCH_POLL_CHARGER_UPDATE,
    SWITCH_REDUCE_CHARGE_LIMIT_DIFFERENCE,
    SWITCH_SCHEDULE_CHARGE,
    SWITCH_SUN_TRIGGER,
    TIME_CHARGE_ENDTIME_FRIDAY,
    TIME_CHARGE_ENDTIME_MONDAY,
    TIME_CHARGE_ENDTIME_SATURDAY,
    TIME_CHARGE_ENDTIME_SUNDAY,
    TIME_CHARGE_ENDTIME_THURSDAY,
    TIME_CHARGE_ENDTIME_TUESDAY,
    TIME_CHARGE_ENDTIME_WEDNESDAY,
)
from .entity import compose_entity_id
from .model_config import ConfigValue, ConfigValueDict
from .sc_config_state import ScConfigState
from .utils import get_sun_attribute_or_abort


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
@dataclass
class ScheduleData:
    """Charge limit schedule data."""

    weekly_schedule: list[ChargeSchedule]
    use_charge_schedule: bool = False
    has_charge_endtime: bool = False
    day_index: int = -1

    # Timestamp of current data
    data_timestamp: datetime = datetime.min

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

    # Is charge to start immediately?
    is_immediate_start: bool = False

    def __repr__(self) -> str:
        """Return string representation of ScheduleData."""
        return (
            f"day_index={self.day_index}, "
            f"use_charge_schedule={self.use_charge_schedule}, "
            f"has_charge_endtime={self.has_charge_endtime}, charge_endtime={self.charge_endtime}, "
            f"propose_charge_starttime={self.propose_charge_starttime}, need_charge_duration={self.need_charge_duration}, "
            f"is_immediate_start={self.is_immediate_start}, "
            f"battery_soc={self.battery_soc}, "
            f"old_charge_limit={self.old_charge_limit}, new_charge_limit={self.new_charge_limit}, "
            f"calibrate_max_charge_limit={self.calibrate_max_charge_limit}, "
            f"data_timestamp={self.data_timestamp}, "
            f"{self.weekly_schedule}"
        )


# ----------------------------------------------------------------------------
@dataclass
class StateOfCharge:
    """State of charge data."""

    state_of_charge: float
    update_time: datetime

    def __repr__(self) -> str:
        """Return string representation of StateOfCharge."""
        return f"{self.update_time}: {self.state_of_charge}"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ScOptionState(ScConfigState):
    """SolarCharger entity state using config from config_entry.options and config_subentry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        caller: str,
    ) -> None:
        """Initialize the ScOptionState instance."""

        self._subentry = subentry
        ScConfigState.__init__(self, hass, entry, caller)

    # ----------------------------------------------------------------------------
    # Local device only entities.
    # Non-modifiable local device entities, ie.
    # not defined in config_options_flow _charger_control_entities_schema().
    # ----------------------------------------------------------------------------
    @cached_property
    def next_charge_time_trigger_entity_id(self) -> str:
        """Return the next charge time trigger entity ID."""
        return compose_entity_id(
            DATETIME, self._subentry.unique_id, DATETIME_NEXT_CHARGE_TIME
        )

    @cached_property
    def fast_charge_mode_switch_entity_id(self) -> str:
        """Return the fast charge mode switch entity ID."""
        return compose_entity_id(
            SWITCH, self._subentry.unique_id, SWITCH_FAST_CHARGE_MODE
        )

    @cached_property
    def poll_charger_update_switch_entity_id(self) -> str:
        """Return the poll charger update switch entity ID."""
        return compose_entity_id(
            SWITCH, self._subentry.unique_id, SWITCH_POLL_CHARGER_UPDATE
        )

    @cached_property
    def charge_switch_entity_id(self) -> str:
        """Return the charge switch entity ID."""
        return compose_entity_id(SWITCH, self._subentry.unique_id, SWITCH_CHARGE)

    @cached_property
    def schedule_charge_switch_entity_id(self) -> str:
        """Return the schedule charge switch entity ID."""
        return compose_entity_id(
            SWITCH, self._subentry.unique_id, SWITCH_SCHEDULE_CHARGE
        )

    @cached_property
    def plugin_trigger_switch_entity_id(self) -> str:
        """Return the plugin trigger switch entity ID."""
        return compose_entity_id(
            SWITCH, self._subentry.unique_id, SWITCH_PLUGIN_TRIGGER
        )

    @cached_property
    def sun_trigger_switch_entity_id(self) -> str:
        """Return the sun trigger switch entity ID."""
        return compose_entity_id(SWITCH, self._subentry.unique_id, SWITCH_SUN_TRIGGER)

    @cached_property
    def calibrate_max_charge_speed_switch_entity_id(self) -> str:
        """Return the calibrate max charge speed switch entity ID."""
        return compose_entity_id(
            SWITCH, self._subentry.unique_id, SWITCH_CALIBRATE_MAX_CHARGE_SPEED
        )

    # ----------------------------------------------------------------------------
    # Local or global device entities.
    # ----------------------------------------------------------------------------
    @cached_property
    def charge_limit_monday_entity_id(self) -> str:
        """Return Monday charge limit entity ID."""
        return self.option_get_id_or_abort(NUMBER_CHARGE_LIMIT_MONDAY)

    @cached_property
    def charge_limit_tuesday_entity_id(self) -> str:
        """Return Tuesday charge limit entity ID."""
        return self.option_get_id_or_abort(NUMBER_CHARGE_LIMIT_TUESDAY)

    @cached_property
    def charge_limit_wednesday_entity_id(self) -> str:
        """Return Wednesday charge limit entity ID."""
        return self.option_get_id_or_abort(NUMBER_CHARGE_LIMIT_WEDNESDAY)

    @cached_property
    def charge_limit_thursday_entity_id(self) -> str:
        """Return Thursday charge limit entity ID."""
        return self.option_get_id_or_abort(NUMBER_CHARGE_LIMIT_THURSDAY)

    @cached_property
    def charge_limit_friday_entity_id(self) -> str:
        """Return Friday charge limit entity ID."""
        return self.option_get_id_or_abort(NUMBER_CHARGE_LIMIT_FRIDAY)

    @cached_property
    def charge_limit_saturday_entity_id(self) -> str:
        """Return Saturday charge limit entity ID."""
        return self.option_get_id_or_abort(NUMBER_CHARGE_LIMIT_SATURDAY)

    @cached_property
    def charge_limit_sunday_entity_id(self) -> str:
        """Return Sunday charge limit entity ID."""
        return self.option_get_id_or_abort(NUMBER_CHARGE_LIMIT_SUNDAY)

    @cached_property
    def charge_endtime_monday_entity_id(self) -> str:
        """Return Monday charge endtime entity ID."""
        return self.option_get_id_or_abort(TIME_CHARGE_ENDTIME_MONDAY)

    @cached_property
    def charge_endtime_tuesday_entity_id(self) -> str:
        """Return Tuesday charge endtime entity ID."""
        return self.option_get_id_or_abort(TIME_CHARGE_ENDTIME_TUESDAY)

    @cached_property
    def charge_endtime_wednesday_entity_id(self) -> str:
        """Return Wednesday charge endtime entity ID."""
        return self.option_get_id_or_abort(TIME_CHARGE_ENDTIME_WEDNESDAY)

    @cached_property
    def charge_endtime_thursday_entity_id(self) -> str:
        """Return Thursday charge endtime entity ID."""
        return self.option_get_id_or_abort(TIME_CHARGE_ENDTIME_THURSDAY)

    @cached_property
    def charge_endtime_friday_entity_id(self) -> str:
        """Return Friday charge endtime entity ID."""
        return self.option_get_id_or_abort(TIME_CHARGE_ENDTIME_FRIDAY)

    @cached_property
    def charge_endtime_saturday_entity_id(self) -> str:
        """Return Saturday charge endtime entity ID."""
        return self.option_get_id_or_abort(TIME_CHARGE_ENDTIME_SATURDAY)

    @cached_property
    def charge_endtime_sunday_entity_id(self) -> str:
        """Return Sunday charge endtime entity ID."""
        return self.option_get_id_or_abort(TIME_CHARGE_ENDTIME_SUNDAY)

    @cached_property
    def get_charge_limit_entity_ids(self) -> dict[str, int]:
        """Return all charge limit entity IDs with their corresponding day index."""
        return {
            self.charge_limit_monday_entity_id: 0,
            self.charge_limit_tuesday_entity_id: 1,
            self.charge_limit_wednesday_entity_id: 2,
            self.charge_limit_thursday_entity_id: 3,
            self.charge_limit_friday_entity_id: 4,
            self.charge_limit_saturday_entity_id: 5,
            self.charge_limit_sunday_entity_id: 6,
        }

    @cached_property
    def get_charge_endtime_entity_ids(self) -> dict[str, int]:
        """Return all charge endtime entity IDs with their corresponding day index."""
        return {
            self.charge_endtime_monday_entity_id: 0,
            self.charge_endtime_tuesday_entity_id: 1,
            self.charge_endtime_wednesday_entity_id: 2,
            self.charge_endtime_thursday_entity_id: 3,
            self.charge_endtime_friday_entity_id: 4,
            self.charge_endtime_saturday_entity_id: 5,
            self.charge_endtime_sunday_entity_id: 6,
        }

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    def _set_config_value_dict(
        self,
        val_dict: ConfigValueDict | None,
        config_name: str | None,
        config_item: str,
        entity_id: str | None,
        entity_val: Any | None = None,
    ) -> None:
        if val_dict is not None:
            val_dict.config_values[config_item] = ConfigValue(
                config_item, entity_id, entity_val
            )

        _LOGGER.debug(
            "%s: %s: '%s' = '%s'",
            config_name,
            config_item,
            entity_id,
            entity_val,
        )

    # ----------------------------------------------------------------------------
    def option_get_id(self, config_item: str) -> str | None:
        """Get entity ID from option config data."""

        return get_saved_option_value(
            self._entry, self._subentry, config_item, use_default=True
        )

    # ----------------------------------------------------------------------------
    def option_get_id_or_abort(self, config_item: str) -> str:
        """Get entity ID from option config data."""

        entity_id = self.option_get_id(config_item)
        if entity_id is None:
            raise ValueError(
                f"{self._subentry.unique_id}: {config_item}: Failed to get entity ID"
            )
        return entity_id

    # ----------------------------------------------------------------------------
    def option_get_string(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> str | None:
        """Try to get config from local device settings first, and if not available then try global defaults."""

        str_val = get_saved_option_value(
            self._entry, self._subentry, config_item, use_default=True
        )

        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, None, str_val
        )

        return str_val

    # ----------------------------------------------------------------------------
    def option_get_list(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> list[Any] | None:
        """Get list from option config data."""

        json_str = self.option_get_string(config_item, val_dict=val_dict)
        if json_str is None:
            return None

        return json.loads(json_str)

    # ----------------------------------------------------------------------------
    # Get entity ID from options config, then get entity value.
    # Requires config_subentry and config_entry.options.
    # ----------------------------------------------------------------------------
    def option_get_entity_number(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> float | None:
        """Get entity ID from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_id(config_item)
        if entity_id:
            entity_val = self.get_number(entity_id)

        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_number_or_abort(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> float:
        """Get entity ID from saved options, then get value for entity."""

        entity_val = self.option_get_entity_number(config_item, val_dict=val_dict)
        if entity_val is None:
            raise ValueError(
                f"{self._subentry.unique_id}: {config_item}: Failed to get entity number value"
            )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_integer(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> int | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_id(config_item)
        if entity_id:
            entity_val = self.get_integer(entity_id)

        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_string(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> str | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_id(config_item)
        if entity_id:
            entity_val = self.get_string(entity_id)

        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_boolean(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> bool | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_id(config_item)
        if entity_id:
            entity_val = self.get_boolean(entity_id)

        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_boolean_or_abort(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> bool:
        """Get entity ID from saved options, then get value for entity."""

        entity_val = self.option_get_entity_boolean(config_item, val_dict)
        if entity_val is None:
            raise ValueError(
                f"{self._subentry.unique_id}: {config_item}: Failed to get entity boolean value"
            )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_time(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> time | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_id(config_item)
        if entity_id:
            entity_val = self.get_time(entity_id)

        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_time_or_abort(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> time:
        """Get entity ID from saved options, then get value for entity."""

        entity_val = self.option_get_entity_time(config_item, val_dict)
        if entity_val is None:
            raise ValueError(
                f"{self._subentry.unique_id}: {config_item}: Failed to get entity time value"
            )

        return entity_val

    # ----------------------------------------------------------------------------
    async def async_option_set_entity_number(
        self,
        config_item: str,
        num: float,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Set number entity."""

        entity_id = self.option_get_id(config_item)
        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id, num
        )

        if entity_id:
            await self.async_set_number(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_option_set_entity_integer(
        self,
        config_item: str,
        num: int,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Set integer entity."""

        entity_id = self.option_get_id(config_item)
        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id, num
        )

        if entity_id:
            await self.async_set_integer(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_option_press_entity_button(
        self,
        config_item: str,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Press a button entity."""

        entity_id = self.option_get_id(config_item)
        self._set_config_value_dict(
            val_dict, self._subentry.unique_id, config_item, entity_id
        )

        if entity_id:
            await self.async_press_button(entity_id)

    # ----------------------------------------------------------------------------
    async def async_option_turn_entity_switch(
        self,
        config_item: str,
        turn_on: bool,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Turn on or off switch entity."""

        entity_id = self.option_get_id(config_item)
        self._set_config_value_dict(
            val_dict,
            self._subentry.unique_id,
            config_item,
            entity_id,
            "on" if turn_on else "off",
        )

        if entity_id:
            await self.async_turn_switch(entity_id, turn_on)

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    async def _async_option_sleep(self, config_item: str) -> None:
        """Wait sleep time."""

        duration = self.option_get_entity_number_or_abort(config_item)
        await asyncio.sleep(duration)

    # ----------------------------------------------------------------------------
    # Global or local defaults, with local defaults taking priority over global defaults.
    # ----------------------------------------------------------------------------
    def is_reduce_charge_limit_difference_between_days(self) -> bool:
        """Return True if reduce charge limit difference between days is enabled."""

        return self.option_get_entity_boolean_or_abort(
            SWITCH_REDUCE_CHARGE_LIMIT_DIFFERENCE
        )

    # ----------------------------------------------------------------------------
    def get_min_charge_limit(self) -> float:
        """Get minimum charge limit."""

        return self.option_get_entity_number_or_abort(NUMBER_CHARGEE_MIN_CHARGE_LIMIT)

    # ----------------------------------------------------------------------------
    def is_sun_above_start_end_elevation_triggers(self) -> tuple[bool, float]:
        """Is sun above start and end elevation triggers?"""

        sun_above_start_end_elevations = False

        sun_state: State = self.get_sun_state_or_abort()
        sunrise_elevation_start_trigger: float = self.option_get_entity_number_or_abort(
            NUMBER_SUNRISE_ELEVATION_START_TRIGGER
        )
        sunset_elevation_end_trigger: float = self.option_get_entity_number_or_abort(
            NUMBER_SUNSET_ELEVATION_END_TRIGGER
        )
        sun_elevation: float = get_sun_attribute_or_abort(
            self._caller, sun_state, "elevation"
        )
        sun_is_rising: bool = get_sun_attribute_or_abort(
            self._caller, sun_state, "rising"
        )

        if (sun_is_rising and sun_elevation >= sunrise_elevation_start_trigger) or (
            not sun_is_rising and sun_elevation > sunset_elevation_end_trigger
        ):
            sun_above_start_end_elevations = True

        return (sun_above_start_end_elevations, sun_elevation)

    # ----------------------------------------------------------------------------
    # Edge cases: Around midnight.
    # _is_sun_below_end_elevation_and_decending() cannot be exactly midnight.
    # If cutoff is just before midnight, before cutoff is ok, after cutoff it won't get tomorrow goal.
    # If cutoff is just after midnight, then ...
    # Midnight time is used to determine whether it is today or tomorrow.
    def is_sun_below_end_elevation_trigger_and_decending(self) -> bool:
        """Roughly between end elevation trigger and midnight."""

        sun_state: State = self.get_sun_state_or_abort()
        sunset_elevation_end_trigger: float = self.option_get_entity_number_or_abort(
            NUMBER_SUNSET_ELEVATION_END_TRIGGER
        )
        sun_elevation: float = get_sun_attribute_or_abort(
            self._caller, sun_state, "elevation"
        )
        sun_is_rising: bool = get_sun_attribute_or_abort(
            self._caller, sun_state, "rising"
        )

        return sun_elevation < sunset_elevation_end_trigger and not sun_is_rising

    # ----------------------------------------------------------------------------
    def is_sun_between_end_elevation_trigger_and_sunset(self) -> bool:
        """Is sun between end elevation trigger and sunset?"""

        sun_state: State = self.get_sun_state_or_abort()
        sunset_elevation_end_trigger: float = self.option_get_entity_number_or_abort(
            NUMBER_SUNSET_ELEVATION_END_TRIGGER
        )
        sun_elevation: float = get_sun_attribute_or_abort(
            self._caller, sun_state, "elevation"
        )
        sun_is_rising: bool = get_sun_attribute_or_abort(
            self._caller, sun_state, "rising"
        )

        if sunset_elevation_end_trigger >= 0:
            # For positive sunset_elevation_end_trigger
            inbetween = (
                sun_elevation >= 0
                and sun_elevation <= sunset_elevation_end_trigger
                and not sun_is_rising
            )
        else:
            # For negative sunset_elevation_end_trigger
            inbetween = (
                sun_elevation < 0
                and sun_elevation >= sunset_elevation_end_trigger
                and not sun_is_rising
            )

        return inbetween

    # ----------------------------------------------------------------------------
    def get_weekly_schedule(self) -> list[ChargeSchedule]:
        """Get daily charge schedule."""

        weekly_schedule: list[ChargeSchedule] = [
            ChargeSchedule(
                charge_day="Monday",
                charge_limit=self.option_get_entity_number_or_abort(
                    NUMBER_CHARGE_LIMIT_MONDAY
                ),
                charge_end_time=self.option_get_entity_time_or_abort(
                    TIME_CHARGE_ENDTIME_MONDAY
                ),
            ),
            ChargeSchedule(
                charge_day="Tuesday",
                charge_limit=self.option_get_entity_number_or_abort(
                    NUMBER_CHARGE_LIMIT_TUESDAY
                ),
                charge_end_time=self.option_get_entity_time_or_abort(
                    TIME_CHARGE_ENDTIME_TUESDAY
                ),
            ),
            ChargeSchedule(
                charge_day="Wednesday",
                charge_limit=self.option_get_entity_number_or_abort(
                    NUMBER_CHARGE_LIMIT_WEDNESDAY
                ),
                charge_end_time=self.option_get_entity_time_or_abort(
                    TIME_CHARGE_ENDTIME_WEDNESDAY
                ),
            ),
            ChargeSchedule(
                charge_day="Thursday",
                charge_limit=self.option_get_entity_number_or_abort(
                    NUMBER_CHARGE_LIMIT_THURSDAY
                ),
                charge_end_time=self.option_get_entity_time_or_abort(
                    TIME_CHARGE_ENDTIME_THURSDAY
                ),
            ),
            ChargeSchedule(
                charge_day="Friday",
                charge_limit=self.option_get_entity_number_or_abort(
                    NUMBER_CHARGE_LIMIT_FRIDAY
                ),
                charge_end_time=self.option_get_entity_time_or_abort(
                    TIME_CHARGE_ENDTIME_FRIDAY
                ),
            ),
            ChargeSchedule(
                charge_day="Saturday",
                charge_limit=self.option_get_entity_number_or_abort(
                    NUMBER_CHARGE_LIMIT_SATURDAY
                ),
                charge_end_time=self.option_get_entity_time_or_abort(
                    TIME_CHARGE_ENDTIME_SATURDAY
                ),
            ),
            ChargeSchedule(
                charge_day="Sunday",
                charge_limit=self.option_get_entity_number_or_abort(
                    NUMBER_CHARGE_LIMIT_SUNDAY
                ),
                charge_end_time=self.option_get_entity_time_or_abort(
                    TIME_CHARGE_ENDTIME_SUNDAY
                ),
            ),
        ]

        return weekly_schedule

    # ----------------------------------------------------------------------------
    # Local device control entities
    # ----------------------------------------------------------------------------
    def is_fast_charge_mode(self) -> bool:
        """Is fast charge mode on?"""
        return self.get_boolean_or_abort(self.fast_charge_mode_switch_entity_id)

    # ----------------------------------------------------------------------------
    def is_poll_charger_update(self) -> bool:
        """Is poll charger update on?"""
        return self.get_boolean_or_abort(self.poll_charger_update_switch_entity_id)

    # ----------------------------------------------------------------------------
    def is_schedule_charge(self) -> bool:
        """Is schedule charge on?"""
        return self.get_boolean_or_abort(self.schedule_charge_switch_entity_id)

    # ----------------------------------------------------------------------------
    def is_plugin_trigger(self) -> bool:
        """Is plugin trigger on?"""
        return self.get_boolean_or_abort(self.plugin_trigger_switch_entity_id)

    # ----------------------------------------------------------------------------
    def is_sun_trigger(self) -> bool:
        """Is sun trigger on?"""
        return self.get_boolean_or_abort(self.sun_trigger_switch_entity_id)

    # ----------------------------------------------------------------------------
    def is_charge_switch_on(self) -> bool:
        """Is charge switch on?"""
        return self.get_boolean_or_abort(self.charge_switch_entity_id)

    # ----------------------------------------------------------------------------
    def is_calibrate_max_charge_speed(self) -> bool:
        """Is calibrate max charge speed on?"""
        return self.get_boolean_or_abort(
            self.calibrate_max_charge_speed_switch_entity_id
        )

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
