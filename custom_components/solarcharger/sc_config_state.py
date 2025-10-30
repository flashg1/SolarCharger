"""SolarCharger entity state using config from config_entry.data."""

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
        config_entry: ConfigEntry,
        caller: str,
    ) -> None:
        """Initialize the ScConfigState instance."""

        self.hass = hass
        self._config_entry = config_entry
        self._caller = caller

        ScState.__init__(self, hass, caller)

    # ----------------------------------------------------------------------------
    # Get entity ID from config data, then get entity value.
    # Requires config_entry.data.
    # ----------------------------------------------------------------------------
    def config_get_data(
        self,
        config_item: str,
    ) -> str | None:
        """Get config from config data."""

        config_str = self._config_entry.data.get(config_item)
        if config_str is None:
            _LOGGER.warning("%s: Config not found for '%s'", self._caller, config_item)

        return config_str

    # ----------------------------------------------------------------------------
    def config_get_entity_id(
        self,
        config_item: str,
    ) -> str | None:
        """Get entity name from config data."""

        entity_id = self._config_entry.data.get(config_item)
        if not entity_id:
            _LOGGER.error("%s: Entity ID not found for '%s'", self._caller, config_item)

        return entity_id

    # ----------------------------------------------------------------------------
    def config_get_number(
        self,
        config_item: str,
    ) -> float | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.config_get_entity_id(config_item)
        if entity_id:
            entity_val = self.get_number(entity_id)

        return entity_val
