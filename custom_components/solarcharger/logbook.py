"""Logbook implementation."""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_DOMAIN,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    DOMAIN,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    EVENT_ATTR_ACTION,
    EVENT_ATTR_VALUE,
    SOLAR_CHARGER_COORDINATOR_EVENT,
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@callback
def async_describe_events(
    _hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, Any]]], None],
) -> None:
    """Describe SolarCharger events."""

    @callback
    def async_describe_charger_event(event: Event) -> dict[str, Any]:
        """Describe a charger change event."""
        data = event.data
        action = data.get(EVENT_ATTR_ACTION)

        if action == EVENT_ACTION_NEW_CHARGE_CURRENT:
            new_current = data.get(EVENT_ATTR_VALUE, {})
            message = f"charge current set to {new_current}A"
        else:
            msg = f"Unknown action: {action}"
            raise ValueError(msg)

        return {
            LOGBOOK_ENTRY_NAME: "Solar Charger",
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_DOMAIN: DOMAIN,
        }

    async_describe_event(
        DOMAIN, SOLAR_CHARGER_COORDINATOR_EVENT, async_describe_charger_event
    )
