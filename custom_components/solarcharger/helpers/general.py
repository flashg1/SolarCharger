"""General helpers."""

# pylint: disable=relative-beyond-top-level
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import State

from ..const import CHARGE_API_ENTITIES, CONTROL_CHARGER_ALLOCATED_POWER  # noqa: TID252
from ..models import ChargeControl  # noqa: TID252

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
def get_parameter(config_entry: ConfigEntry, parameter: str, default_val: Any = None):
    """Get parameter from OptionsFlow or ConfigFlow."""

    if parameter in config_entry.options:
        return config_entry.options.get(parameter)
    if parameter in config_entry.data:
        return config_entry.data.get(parameter)

    return default_val


# ----------------------------------------------------------------------------
async def async_set_allocated_power(
    control: ChargeControl, allocated_power: float
) -> bool:
    """Set allocated power number entity."""
    ok: bool = False

    if control.numbers:
        await control.numbers[CONTROL_CHARGER_ALLOCATED_POWER].async_set_native_value(
            allocated_power
        )
        ok = True

    return ok


# ----------------------------------------------------------------------------
def is_config_entity_used_as_local_device_entity(
    domain: str | None, config_item: str
) -> bool:
    """Check if SolarCharger config entity is used as local device entity."""
    used_as_local_device_entity = False

    if domain is not None:
        api_entities = CHARGE_API_ENTITIES.get(domain)
        if api_entities is not None:
            entity_id = api_entities.get(config_item)
            if entity_id is not None:
                used_as_local_device_entity = config_item in entity_id

    return used_as_local_device_entity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class Validator:
    """Validator class."""

    # ----------------------------------------------------------------------------
    @staticmethod
    def is_float(element: Any) -> bool:
        """Check that argument is a float."""

        try:
            float(element)
        except ValueError:
            return False
        except TypeError:
            return False

        return True

    # ----------------------------------------------------------------------------
    @staticmethod
    def is_soc_state(soc_state: State) -> bool:
        """Check that argument is a SOC state."""

        if soc_state is not None:
            if soc_state.state != "unavailable":
                soc = soc_state.state
                if not Validator.is_float(soc):
                    return False
                if 0.0 <= float(soc) <= 100.0:
                    return True
        return False
