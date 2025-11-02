"""SolarCharger entity state using config from config_entry.options and config_subentry."""

import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from .config_option_utils import get_saved_option_value
from .sc_config_state import ScConfigState

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
        config_entry: ConfigEntry,
        config_subentry: ConfigSubentry,
        caller: str,
    ) -> None:
        """Initialize the ScOptionState instance."""

        self.hass = hass
        self._config_entry = config_entry
        self._config_subentry = config_subentry
        self._caller = caller

        ScConfigState.__init__(self, hass, config_entry, caller)

    # ----------------------------------------------------------------------------
    # Get entity ID from options config, then get entity value.
    # Requires config_subentry and config_entry.options.
    # ----------------------------------------------------------------------------
    def option_get_string(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> str | None:
        """Try to get config from local device settings first, and if not available then try global defaults."""

        if subentry is None:
            subentry = self._config_subentry

        config_str = get_saved_option_value(
            self._config_entry, subentry, config_item, use_default=True
        )
        if config_str is None:
            _LOGGER.warning("%s: Config not found for '%s'", self._caller, config_item)

        return config_str

    # ----------------------------------------------------------------------------
    def option_get_list(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> list[Any] | None:
        """Get list from option config data."""

        json_str = self.option_get_string(config_item, subentry)
        if json_str is None:
            return None

        return json.loads(json_str)

    # ----------------------------------------------------------------------------
    def option_get_entity_id(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> str | None:
        """Get entity ID from option config data."""

        entity_id = self.option_get_string(config_item, subentry)
        if not entity_id:
            _LOGGER.warning(
                "%s: Entity ID not found for '%s'", self._caller, config_item
            )

        return entity_id

    # ----------------------------------------------------------------------------
    def option_get_entity_number(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> float | None:
        """Get entity ID from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_number(entity_id)

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_integer(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> int | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_integer(entity_id)

        return entity_val

    # ----------------------------------------------------------------------------
    def option_get_entity_string(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> str | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            entity_val = self.get_string(entity_id)

        return entity_val

    # ----------------------------------------------------------------------------
    async def async_option_set_entity_number(
        self, config_item: str, num: float, subentry: ConfigSubentry | None = None
    ) -> None:
        """Set number entity."""

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            await self.async_set_number(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_option_set_entity_integer(
        self, config_item: str, num: int, subentry: ConfigSubentry | None = None
    ) -> None:
        """Set integer entity."""

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            await self.async_set_integer(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_option_press_entity_button(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> None:
        """Press a button entity."""

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            await self.async_press_button(entity_id)

    # ----------------------------------------------------------------------------
    async def async_option_turn_entity_switch_on(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> None:
        """Turn on switch entity."""

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            await self.async_turn_switch_on(entity_id)

    # ----------------------------------------------------------------------------
    async def async_option_turn_entity_switch_off(
        self, config_item: str, subentry: ConfigSubentry | None = None
    ) -> None:
        """Turn off switch entity."""

        entity_id = self.option_get_entity_id(config_item, subentry)
        if entity_id:
            await self.async_turn_switch_off(entity_id)
