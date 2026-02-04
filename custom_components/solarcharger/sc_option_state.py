"""SolarCharger entity state using config from config_entry.options and config_subentry."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from .config_utils import get_saved_option_value
from .const import (
    NUMBER_CHARGE_LIMIT_FRIDAY,
    NUMBER_CHARGE_LIMIT_MONDAY,
    NUMBER_CHARGE_LIMIT_SATURDAY,
    NUMBER_CHARGE_LIMIT_SUNDAY,
    NUMBER_CHARGE_LIMIT_THURSDAY,
    NUMBER_CHARGE_LIMIT_TUESDAY,
    NUMBER_CHARGE_LIMIT_WEDNESDAY,
    TIME_CHARGE_ENDTIME_FRIDAY,
    TIME_CHARGE_ENDTIME_MONDAY,
    TIME_CHARGE_ENDTIME_SATURDAY,
    TIME_CHARGE_ENDTIME_SUNDAY,
    TIME_CHARGE_ENDTIME_THURSDAY,
    TIME_CHARGE_ENDTIME_TUESDAY,
    TIME_CHARGE_ENDTIME_WEDNESDAY,
)
from .model_config import ConfigValue, ConfigValueDict
from .sc_config_state import ScConfigState


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ChargeSchedule:
    """Daily charge schedule."""

    charge_day: str
    charge_limit: float
    charge_end_time: time


@dataclass
class ScheduleData:
    """Charge limit schedule data."""

    weekly_schedule: list[ChargeSchedule]
    use_charge_schedule: bool = False
    has_charge_endtime: bool = False
    day_index: int = -1
    session_starttime: datetime = datetime.min

    # Current device charge limit
    old_charge_limit: float = -1
    # New charge limit or from schedule
    new_charge_limit: float = -1

    charge_endtime = datetime.min

    battery_soc: float | None = None

    # Requires battery_soc to calculate
    need_charge_duration: timedelta = timedelta.min
    propose_charge_starttime: datetime = datetime.min
    is_immediate_start: bool = False


@dataclass
class StateOfCharge:
    """State of charge data."""

    state_of_charge: float
    update_time: datetime


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
    # General utils
    # ----------------------------------------------------------------------------
    def _get_subentry(self, subentry: ConfigSubentry | None) -> ConfigSubentry:
        if subentry is None:
            subentry = self._subentry
        return subentry

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
    def option_get_id(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> str | None:
        """Get entity ID from option config data."""

        subentry = self._get_subentry(subentry)
        return get_saved_option_value(
            self._entry, subentry, config_item, use_default=True
        )

    # ----------------------------------------------------------------------------
    def option_get_id_or_abort(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> str:
        """Get entity ID from option config data."""

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        if entity_id is None:
            raise ValueError(
                f"{subentry.unique_id}: {config_item}: Failed to get entity ID"
            )
        return entity_id

    # ----------------------------------------------------------------------------
    def option_get_string(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> str | None:
        """Try to get config from local device settings first, and if not available then try global defaults."""

        subentry = self._get_subentry(subentry)
        str_val = get_saved_option_value(
            self._entry, subentry, config_item, use_default=True
        )

        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, None, str_val
        )

        return str_val

    # ----------------------------------------------------------------------------
    def option_get_list(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> list[Any] | None:
        """Get list from option config data."""

        json_str = self.option_get_string(config_item, subentry, val_dict)
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
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> float | None:
        """Get entity ID from saved options, then get value for entity."""
        entity_val = None

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_number(entity_id)

        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_number_or_abort(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> float:
        """Get entity ID from saved options, then get value for entity."""

        subentry = self._get_subentry(subentry)
        entity_val = self.option_get_entity_number(config_item, subentry, val_dict)
        if entity_val is None:
            raise ValueError(
                f"{subentry.unique_id}: {config_item}: Failed to get entity number value"
            )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_integer(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> int | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_integer(entity_id)

        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_string(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> str | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_string(entity_id)

        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_boolean(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> bool | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_boolean(entity_id)

        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_boolean_or_abort(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> bool:
        """Get entity ID from saved options, then get value for entity."""

        subentry = self._get_subentry(subentry)
        entity_val = self.option_get_entity_boolean(config_item, subentry, val_dict)
        if entity_val is None:
            raise ValueError(
                f"{subentry.unique_id}: {config_item}: Failed to get entity boolean value"
            )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_time(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> time | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_time(entity_id)

        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, entity_val
        )

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_time_or_abort(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> time:
        """Get entity ID from saved options, then get value for entity."""

        subentry = self._get_subentry(subentry)
        entity_val = self.option_get_entity_time(config_item, subentry, val_dict)
        if entity_val is None:
            raise ValueError(
                f"{subentry.unique_id}: {config_item}: Failed to get entity time value"
            )

        return entity_val

    # ----------------------------------------------------------------------------
    async def async_option_set_entity_number(
        self,
        config_item: str,
        num: float,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Set number entity."""

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, num
        )

        if entity_id:
            await self.async_set_number(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_option_set_entity_integer(
        self,
        config_item: str,
        num: int,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Set integer entity."""

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, num
        )

        if entity_id:
            await self.async_set_integer(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_option_press_entity_button(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Press a button entity."""

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id
        )

        if entity_id:
            await self.async_press_button(entity_id)

    # ----------------------------------------------------------------------------
    async def async_option_turn_entity_switch_on(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Turn on switch entity."""

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, "on"
        )

        if entity_id:
            await self.async_turn_switch_on(entity_id)

    # ----------------------------------------------------------------------------
    async def async_option_turn_entity_switch_off(
        self,
        config_item: str,
        subentry: ConfigSubentry | None = None,
        val_dict: ConfigValueDict | None = None,
    ) -> None:
        """Turn off switch entity."""

        subentry = self._get_subentry(subentry)
        entity_id = self.option_get_id(config_item, subentry)
        self._set_config_value_dict(
            val_dict, subentry.unique_id, config_item, entity_id, "off"
        )

        if entity_id:
            await self.async_turn_switch_off(entity_id)

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    async def _async_option_sleep(self, config_item: str) -> None:
        """Wait sleep time."""

        duration = self.option_get_entity_number_or_abort(config_item)
        await asyncio.sleep(duration)

    # ----------------------------------------------------------------------------
    # Specific utils
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
