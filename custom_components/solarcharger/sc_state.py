"""Support basic HA state requests."""

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceResponse, State

from .const import (
    EVENT_ATTR_ACTION,
    EVENT_ATTR_VALUE,
    HA_SUN_ENTITY,
    SOLAR_CHARGER_COORDINATOR_EVENT,
)

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ScState:
    """Base class for HA entity state."""

    def __init__(
        self,
        hass: HomeAssistant,
        caller: str,
    ) -> None:
        """Initialize the HaState instance."""

        self._hass = hass
        self._caller = caller

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    def _get_entity_state(
        self, entity_id: str | None, parser_fn: Callable | None = None
    ) -> State | None:
        """Get the state of the entity for a given entity."""

        if entity_id is None:
            raise ValueError("Cannot get entity state because entity ID is None")
        state = self._hass.states.get(entity_id)
        if state is None:
            _LOGGER.debug("State not found for entity %s", entity_id)
            return None

        return state

    # ----------------------------------------------------------------------------
    def _get_entity_value(
        self, entity_id: str | None, parser_fn: Callable | None = None
    ) -> Any | None:
        """Get the state of the entity for a given entity. Can be parsed."""

        # Python got confused and call _get_entity_state() in ha_device.py
        state: State | None = self._get_entity_state(entity_id)
        if state is None:
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
            val = self._get_entity_value(entity_id)
        except ValueError as e:
            _LOGGER.debug(
                "%s: Failed to get value for entity '%s': '%s'",
                self._caller,
                entity_id,
                e,
            )

        _LOGGER.debug("%s: '%s' = '%s'", self._caller, entity_id, val)

        return val

    # ----------------------------------------------------------------------------
    def get_number(self, entity_id: str) -> float | None:
        """Get number entity."""

        val = self.get_value(entity_id)
        if val is None:
            _LOGGER.warning(
                "%s: Cannot get number for entity '%s'",
                self._caller,
                entity_id,
            )
            return None

        try:
            return float(val)
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "%s: Failed to parse state '%s' for entity '%s': %s",
                self._caller,
                val,
                entity_id,
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

        str_val = self.get_value(entity_id)
        if str_val is None:
            _LOGGER.warning(
                "%s: Cannot get string for entity '%s'",
                self._caller,
                entity_id,
            )
            return None

        return str_val

    # ----------------------------------------------------------------------------
    async def async_ha_call(
        self,
        domain_name: str,
        service_name: str,
        service_data: dict[str, Any],
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> ServiceResponse:
        """HA service call for entity."""

        try:
            # Call the Home Assistant service
            return await self._hass.services.async_call(
                domain=domain_name,
                service=service_name,
                service_data=service_data,
                blocking=True,
                target=target,
                return_response=return_response,
            )
        except (ValueError, RuntimeError, TimeoutError) as e:
            _LOGGER.warning(
                "%s: Failed %s %s: data='%s': %s",
                self._caller,
                domain_name,
                service_name,
                service_data,
                e,
            )

    # ----------------------------------------------------------------------------
    async def async_set_number(self, entity_id: str, num: float) -> None:
        """Set number entity."""

        domain_name = "number"
        service_name = "set_value"
        service_data: dict[str, Any] = {
            "entity_id": entity_id,
            "value": num,
        }
        await self.async_ha_call(domain_name, service_name, service_data)

    # ----------------------------------------------------------------------------
    async def async_set_integer(self, entity_id: str, num: int) -> None:
        """Set integer entity."""

        await self.async_set_number(entity_id, float(num))

    # ----------------------------------------------------------------------------
    async def async_ha_entity_call(
        self, domain_name: str, service_name: str, entity_id: str
    ) -> None:
        """HA service call for entity."""

        service_data: dict[str, Any] = {"entity_id": entity_id}
        await self.async_ha_call(domain_name, service_name, service_data)

    # ----------------------------------------------------------------------------
    async def async_press_button(self, entity_id: str) -> None:
        """Press button entity."""

        await self.async_ha_entity_call("button", "press", entity_id)

    # ----------------------------------------------------------------------------
    async def async_turn_switch_on(self, entity_id: str) -> None:
        """Turn on switch entity."""

        await self.async_ha_entity_call("switch", "turn_on", entity_id)

    # ----------------------------------------------------------------------------
    async def async_turn_switch_off(self, entity_id: str) -> None:
        """Turn off switch entity."""

        await self.async_ha_entity_call("switch", "turn_off", entity_id)

    # ----------------------------------------------------------------------------
    # Utils
    # ----------------------------------------------------------------------------
    def get_sun_state_or_abort(self) -> State:
        """Get sun state or abort."""
        sun_state: State | None = self._get_entity_state(HA_SUN_ENTITY)
        if sun_state is None:
            raise ValueError(f"{self._caller}: Failed to get sun state")
        _LOGGER.debug("%s: Sun state: %s", self._caller, sun_state)

        return sun_state

    # ----------------------------------------------------------------------------
    def emit_solarcharger_event(
        self, device_id: str, action: str, new_current: float
    ) -> None:
        """Emit an event to Home Assistant's device event log."""
        self._hass.bus.async_fire(
            SOLAR_CHARGER_COORDINATOR_EVENT,
            {
                ATTR_DEVICE_ID: device_id,
                EVENT_ATTR_ACTION: action,
                EVENT_ATTR_VALUE: new_current,
            },
        )

        _LOGGER.debug(
            "Emitted SolarCharger event: action=%s, value=%s", action, new_current
        )
