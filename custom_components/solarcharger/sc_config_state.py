"""SolarCharger entity state using config from config_entry.data."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .sc_state import ScState

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ScConfigState(ScState):
    """SolarCharger entity state using config from config_entry.data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        caller: str,
    ) -> None:
        """Initialize the ScConfigState instance."""

        self._entry = entry
        ScState.__init__(self, hass, caller)

    # ----------------------------------------------------------------------------
    # Get entity ID from config data, then get entity value.
    # Requires config_entry.data.
    # ----------------------------------------------------------------------------
    def config_get_string(
        self,
        config_item: str,
    ) -> str | None:
        """Get string from config data."""

        config_str = self._entry.data.get(config_item)
        if config_str is None:
            _LOGGER.error("%s: Config not found for '%s'", self._caller, config_item)

        return config_str

    # ----------------------------------------------------------------------------
    def config_get_number_or_abort(
        self,
        config_item: str,
    ) -> float:
        """Get number from config data."""

        num = self._entry.data.get(config_item)
        if num is None:
            raise SystemError(f"{self._caller}: {config_item}: Config not found")

        return num

    # ----------------------------------------------------------------------------
    def config_get_id(
        self,
        config_item: str,
    ) -> str | None:
        """Get entity ID from config data."""

        return self.config_get_string(config_item)

    # ----------------------------------------------------------------------------
    def config_get_entity_number(
        self,
        config_item: str,
    ) -> float | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.config_get_id(config_item)
        if entity_id:
            entity_val = self.get_number(entity_id)

        return entity_val

    # ----------------------------------------------------------------------------
    # General utils
    # ----------------------------------------------------------------------------
    async def _async_config_sleep(self, config_item: str) -> None:
        """Wait sleep time."""

        duration = self.config_get_number_or_abort(config_item)
        await asyncio.sleep(duration)
