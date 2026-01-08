"""Support basic HA state requests."""

from collections.abc import Callable
from datetime import date, datetime, time
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.const import ATTR_DEVICE_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceResponse, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.util.dt import as_local, utcnow

from .const import (
    DATETIME,
    EVENT_ATTR_ACTION,
    EVENT_ATTR_VALUE,
    HA_SUN_ENTITY,
    NUMBER,
    SOLAR_CHARGER_COORDINATOR_EVENT,
)
from .utils import get_next_sunrise_time, get_next_sunset_time

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
    def get_ha(self) -> HomeAssistant:
        """Get Home Assistant instance."""

        return self._hass

    # ----------------------------------------------------------------------------
    # Time utils
    # ----------------------------------------------------------------------------
    def get_utc_datetime(self) -> datetime:
        """Get the current time in UTC."""

        return utcnow()

    # ----------------------------------------------------------------------------
    def convert_utc_to_local_datetime(self, utc_dt: datetime) -> datetime:
        """Convert a UTC datetime to the HA local timezone."""

        return as_local(utc_dt)

    # ----------------------------------------------------------------------------
    def get_local_timezone(self) -> ZoneInfo:
        """Get the HA timezone."""

        return ZoneInfo(self._hass.config.time_zone)

    # ----------------------------------------------------------------------------
    def get_local_datetime(self) -> datetime:
        """Get the current time in the HA timezone."""

        return datetime.now(self.get_local_timezone())

    # ----------------------------------------------------------------------------
    def combine_local_date_time(self, local_date: date, local_time: time) -> datetime:
        """Combine local date and time."""

        return datetime.combine(
            local_date,
            local_time,
            tzinfo=self.get_local_timezone(),
        )

    # ----------------------------------------------------------------------------
    def parse_local_datetime(self, datetime_str: str) -> datetime:
        """Parse a datetime string in the HA local timezone."""

        # Stored string is in ISO format UTC or local (eg. 2025-12-28T05:51:05+00:00).
        # Convert to local timezone (eg. 2025-12-28 16:51:05+11:00)
        return datetime.fromisoformat(datetime_str).astimezone(
            self.get_local_timezone()
        )

    # ----------------------------------------------------------------------------
    def parse_local_time(self, time_str: str) -> time:
        """Parse a time string in the HA local timezone."""

        # eg. time_str = '00:00:00'
        # return datetime.strptime(time_str, "%H:%M:%S").time()
        return time.fromisoformat(time_str)

    # ----------------------------------------------------------------------------
    # ----------------------------------------------------------------------------
    def get_entity_entry(self, entity_id: str) -> RegistryEntry | None:
        """Get entity entry from entity registry."""

        entity_registry = er.async_get(self._hass)
        return entity_registry.async_get(entity_id)

    # ----------------------------------------------------------------------------
    def get_device_entry(self, entity_id: str) -> DeviceEntry | None:
        """Get DeviceEntry for entity from device registry."""
        device_entry: DeviceEntry | None = None

        entity_entry = self.get_entity_entry(entity_id)
        if entity_entry:
            device_id = entity_entry.device_id
            if device_id:
                device_registry: DeviceRegistry = dr.async_get(self._hass)
                device_entry = device_registry.async_get(device_id)

        return device_entry

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
    def get_state_string(self, entity_id: str) -> str | None:
        """Get entity state string."""
        state_str: str | None = None

        try:
            state_str = self._get_entity_value(entity_id)
        except ValueError as e:
            _LOGGER.debug(
                "%s: Failed to get state string for entity '%s': '%s'",
                self._caller,
                entity_id,
                e,
            )

        _LOGGER.debug("%s: '%s' = '%s'", self._caller, entity_id, state_str)

        return state_str

    # ----------------------------------------------------------------------------
    def get_number(self, entity_id: str) -> float | None:
        """Get float object."""

        state_str = self.get_state_string(entity_id)
        if state_str is None or state_str in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            _LOGGER.warning(
                "%s: Cannot get number: entity='%s', value='%s'",
                self._caller,
                entity_id,
                state_str,
            )
            return None

        try:
            return float(state_str)
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "%s: Failed to parse state '%s' for entity '%s': %s",
                self._caller,
                state_str,
                entity_id,
                e,
            )
            return None

    # ----------------------------------------------------------------------------
    def get_integer(self, entity_id: str) -> int | None:
        """Get int object."""

        num: float | None = self.get_number(entity_id)
        if num is None:
            return None

        return int(num)

    # ----------------------------------------------------------------------------
    def get_string(self, entity_id: str) -> str | None:
        """Get string object."""

        state_str = self.get_state_string(entity_id)
        if state_str is None:
            _LOGGER.warning(
                "%s: Cannot get string for entity '%s'",
                self._caller,
                entity_id,
            )
            return None

        return state_str

    # ----------------------------------------------------------------------------
    def get_boolean(self, entity_id: str) -> bool | None:
        """Get boolean object."""

        state_str = self.get_state_string(entity_id)
        if state_str is None:
            _LOGGER.warning(
                "%s: Cannot get boolean for entity '%s'",
                self._caller,
                entity_id,
            )
            return None

        return state_str == "on" or state_str is True

    # ----------------------------------------------------------------------------
    def get_datetime(self, entity_id: str) -> datetime | None:
        """Get datetime object."""

        state_str = self.get_state_string(entity_id)
        if state_str is None:
            _LOGGER.warning(
                "%s: Cannot get datetime for entity '%s'",
                self._caller,
                entity_id,
            )
            return None

        try:
            return self.parse_local_datetime(state_str)
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "%s: Failed to parse state '%s' for entity '%s': %s",
                self._caller,
                state_str,
                entity_id,
                e,
            )
            return None

    # ----------------------------------------------------------------------------
    def get_time(self, entity_id: str) -> time | None:
        """Get time object."""

        state_str = self.get_state_string(entity_id)
        if state_str is None:
            _LOGGER.warning(
                "%s: Cannot get time for entity '%s'",
                self._caller,
                entity_id,
            )
            return None

        try:
            return self.parse_local_time(state_str)
        except (ValueError, TypeError) as e:
            _LOGGER.warning(
                "%s: Failed to parse state '%s' for entity '%s': %s",
                self._caller,
                state_str,
                entity_id,
                e,
            )
            return None

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
    async def async_set_datetime(self, entity_id: str, val: datetime) -> None:
        """Set datetime entity.

        See https://www.home-assistant.io/integrations/datetime/
        """

        domain_name = DATETIME
        service_name = "set_value"
        service_data: dict[str, Any] = {
            "entity_id": entity_id,
            "datetime": val.isoformat(),
        }
        await self.async_ha_call(domain_name, service_name, service_data)

    # ----------------------------------------------------------------------------
    async def async_set_number(self, entity_id: str, num: float) -> None:
        """Set number entity."""

        domain_name = NUMBER
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
    def is_daytime(self) -> bool:
        """Return true if within daylight hours."""

        sun_state = self.get_sun_state_or_abort()
        next_sunrise = get_next_sunrise_time(self._caller, sun_state)
        next_sunset = get_next_sunset_time(self._caller, sun_state)
        return next_sunrise > next_sunset

    # ----------------------------------------------------------------------------
    def is_time_between_sunset_and_midnight(self) -> bool:
        """Time between sunset and mid-night is considered to be tomorrow."""

        sun_state = self.get_sun_state_or_abort()
        next_sunset = get_next_sunset_time(self._caller, sun_state)
        now_time = self.get_local_datetime()
        today_sunset = self.combine_local_date_time(now_time.date(), next_sunset.time())

        return now_time > today_sunset

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
