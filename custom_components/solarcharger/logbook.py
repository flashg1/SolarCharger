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
    EVENT_ATTR_NEW_VALUE,
    EVENT_ATTR_OLD_VALUE,
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
            old_val = data.get(EVENT_ATTR_OLD_VALUE)
            new_val = data.get(EVENT_ATTR_NEW_VALUE)
            message = (
                f"changed from {old_val}A to {new_val}A"
                if old_val is not None
                else f"set to {new_val}A"
            )
        else:
            msg = f"Unknown action: {action}"
            raise ValueError(msg)

        return {
            LOGBOOK_ENTRY_NAME: "AMP:",
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_DOMAIN: DOMAIN,
        }

    async_describe_event(
        DOMAIN, SOLAR_CHARGER_COORDINATOR_EVENT, async_describe_charger_event
    )
