"""HA Device.  Combined with code from dirkgroenen/hass-evse-load-balancer for reference."""

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant

from .config_option_utils import get_saved_option_value

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class HaState:
    """Base class for HA entity state."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        config_subentry: ConfigSubentry,
        caller: str,
    ) -> None:
        """Initialize the HaState instance."""

        self.hass = hass
        self._config_entry = config_entry
        self._config_subentry = config_subentry
        self._caller = caller

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    def _get_entity_state(
        self, entity_id: str | None, parser_fn: Callable | None = None
    ) -> Any | None:
        """Get the state of the entity for a given entity. Can be parsed."""

        if entity_id is None:
            raise ValueError("Cannot get entity state because entity ID is None")
        state = self.hass.states.get(entity_id)
        if state is None:
            _LOGGER.debug("State not found for entity %s", entity_id)
            return None

        try:
            return parser_fn(state.state) if parser_fn else state.state
        except ValueError:
            _LOGGER.warning(
                "State for entity %s can't be parsed: %s", entity_id, state.state
            )
            return None

    # ----------------------------------------------------------------------------
    def get_value(self, entity_id: str) -> Any | None:
        """Get entity value."""
        val: Any | None = None

        try:
            val = self._get_entity_state(entity_id)
        except ValueError as e:
            _LOGGER.debug(
                "Failed to get value for entity '%s': '%s'",
                entity_id,
                e,
            )

        return val

    # ----------------------------------------------------------------------------
    def get_number(self, entity_id: str) -> float | None:
        """Get number entity."""

        val = self.get_value(entity_id)
        if val is None:
            _LOGGER.warning(
                "Cannot get number for device %s. Please check entity '%s'.",
                self._caller,
                entity_id,
            )
            return None

        try:
            return float(val)
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "Failed to parse state '%s' for '%s' from device %s: %s",
                val,
                entity_id,
                self._caller,
                e,
            )
            return None

    # ----------------------------------------------------------------------------
    def get_integer(self, entity_id: str) -> int | None:
        """Get integer entity."""

        num: float | None = self.get_number(entity_id)
        if num is None:
            return None

        return int(num)

    # ----------------------------------------------------------------------------
    def get_string(self, entity_id: str) -> str | None:
        """Get string entity."""

        state = self.get_value(entity_id)
        if state is None:
            _LOGGER.warning(
                "Cannot get string for device %s. Please check entity '%s'.",
                self._caller,
                entity_id,
            )
            return None

        return state.state

    # ----------------------------------------------------------------------------
    async def async_set_number(self, entity_id: str, num: float) -> None:
        """Set number entity."""

        try:
            # Call the Home Assistant number.set_value service
            await self.hass.services.async_call(
                domain="number",
                service="set_value",
                service_data={
                    "entity_id": entity_id,
                    "value": num,
                },
                blocking=True,
            )
        except (ValueError, RuntimeError, TimeoutError) as e:
            _LOGGER.warning(
                "Failed to set %s to %d for device %s: %s",
                entity_id,
                num,
                self._caller,
                e,
            )

    # ----------------------------------------------------------------------------
    async def async_set_integer(self, entity_id: str, num: int) -> None:
        """Set integer entity."""

        await self.async_set_number(entity_id, float(num))

    # ----------------------------------------------------------------------------
    async def async_press_button(self, entity_id: str) -> None:
        """Press a button entity."""

        try:
            # Call the Home Assistant button.press service
            await self.hass.services.async_call(
                domain="button",
                service="press",
                service_data={
                    "entity_id": entity_id,
                },
                blocking=True,
            )
        except (ValueError, RuntimeError, TimeoutError) as e:
            _LOGGER.warning(
                "Button press %s failed for device %s: %s",
                entity_id,
                self._caller,
                e,
            )

    # ----------------------------------------------------------------------------
    # Get entity ID from options config, then get entity value.
    # ----------------------------------------------------------------------------
    def get_config(
        self,
        config_item: str,
    ) -> str | None:
        """Try to get config from local device settings first, and if not available then try global defaults."""

        config_str = get_saved_option_value(
            self._config_entry, self._config_subentry, config_item, use_default=True
        )
        if config_str is None:
            _LOGGER.error("%s: Config not found for '%s'", self._caller, config_item)

        return config_str

    # ----------------------------------------------------------------------------
    def get_entity_id(
        self,
        config_item: str,
    ) -> str | None:
        """Try to get entity name from local device settings first, and if not available then try global defaults."""

        entity_id = get_saved_option_value(
            self._config_entry, self._config_subentry, config_item, use_default=True
        )
        if not entity_id:
            _LOGGER.error("%s: Entity ID not found for '%s'", self._caller, config_item)

        return entity_id

    # ----------------------------------------------------------------------------
    def get_entity_number(
        self,
        config_item: str,
    ) -> float | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.get_entity_id(config_item)
        if entity_id:
            entity_val = self.get_number(entity_id)

        return entity_val

    # ----------------------------------------------------------------------------
    def get_entity_integer(
        self,
        config_item: str,
    ) -> int | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.get_entity_id(config_item)
        if entity_id:
            entity_val = self.get_integer(entity_id)

        return entity_val

    # ----------------------------------------------------------------------------
    def get_entity_string(
        self,
        config_item: str,
    ) -> str | None:
        """Get entity name from saved options, then get value for entity."""
        entity_val = None

        entity_id = self.get_entity_id(config_item)
        if entity_id:
            entity_val = self.get_string(entity_id)

        return entity_val

    # ----------------------------------------------------------------------------
    async def async_set_entity_number(self, config_item: str, num: float) -> None:
        """Set number entity."""

        entity_id = self.get_entity_id(config_item)
        if entity_id:
            await self.async_set_number(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_set_entity_integer(self, config_item: str, num: int) -> None:
        """Set integer entity."""

        entity_id = self.get_entity_id(config_item)
        if entity_id:
            await self.async_set_integer(entity_id, num)

    # ----------------------------------------------------------------------------
    async def async_press_entity_button(self, config_item: str) -> None:
        """Press a button entity."""

        entity_id = self.get_entity_id(config_item)
        if entity_id:
            await self.async_press_button(entity_id)
