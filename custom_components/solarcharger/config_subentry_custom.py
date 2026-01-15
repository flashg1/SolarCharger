"""Config subentry flow to create user custom charger."""

from __future__ import annotations

# from collections.abc import Mapping
import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.util import slugify

from .config_options_flow import reset_api_entities
from .config_utils import TEXT_SELECTOR, get_subentry_id
from .const import (
    DOMAIN,
    ERROR_DEVICE_ALREADY_ADDED,
    ERROR_SELECT_CHARGER,
    ERROR_SUBENTRY_CREATED,
    NUMBER,
    NUMBER_CHARGER_ALLOCATED_POWER,
    OPTION_CHARGER_NAME,
    OPTION_GLOBAL_DEFAULTS_ID,
    SUBENTRY_CHARGER_DEVICE_DOMAIN,
    SUBENTRY_CHARGER_DEVICE_ID,
    SUBENTRY_CHARGER_DEVICE_NAME,
    SUBENTRY_TYPE_CUSTOM,
)
from .entity import compose_entity_id
from .exceptions.validation_exception import ValidationExceptionError

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

STEP_SELECT_CHARGER_SCHEMA = vol.Schema(
    {
        vol.Required(SUBENTRY_CHARGER_DEVICE_NAME): TEXT_SELECTOR,
    }
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
def validate_charger_selection(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger selection step."""
    if not data.get(SUBENTRY_CHARGER_DEVICE_NAME):
        raise ValidationExceptionError("base", ERROR_SELECT_CHARGER)  # noqa: EM101

    return data


def validate_charger_config(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger config step."""
    return data


def validate_power_input(_hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input for the power collection step."""
    # Return info that you want to store in the config entry.
    return data


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class AddCustomSubEntryFlowHandler(ConfigSubentryFlow):
    """Handles subentry flow for creating charger."""

    # ----------------------------------------------------------------------------
    def setup_options(
        self, config_entry: ConfigEntry, subentry_unique_id: str, device_name: str
    ) -> None:
        """Set up default options for the new subentry."""

        _LOGGER.debug(
            "Setting up default options for subentry with unique_id: %s",
            subentry_unique_id,
        )

        data: dict[str, Any] = {
            OPTION_CHARGER_NAME: device_name,
        }
        reset_api_entities(config_entry, subentry_unique_id, data)

        self.hass.config_entries.async_update_entry(
            config_entry,
            options=config_entry.options
            | {
                subentry_unique_id: data,
            },
        )

    # ----------------------------------------------------------------------------
    def get_device_entry(self, entity_id: str) -> DeviceEntry | None:
        """Get DeviceEntry for entity."""
        device_entry: DeviceEntry | None = None

        entity_registry = er.async_get(self.hass)
        entry = entity_registry.async_get(entity_id)
        if entry:
            device_id = entry.device_id
            if device_id:
                device_registry: DeviceRegistry = dr.async_get(self.hass)
                device_entry = device_registry.async_get(device_id)

        return device_entry

    # ----------------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Entry point for subentry config. Prompts for charger selection."""
        errors: dict[str, str] = {}
        input_data: dict[str, Any] | None = None

        config_entry = self._get_entry()
        # config_entry.solarcharger_data = {}
        if user_input is not None:
            try:
                input_data = validate_charger_selection(self.hass, user_input)
            except ValidationExceptionError as ex:
                errors[ex.base] = ex.key

            if not errors and input_data is not None:
                # Get charger device subentry
                custom_charger_name: str | None = input_data.get(
                    SUBENTRY_CHARGER_DEVICE_NAME
                )
                if not custom_charger_name:
                    raise ValueError(
                        f"Subentry {SUBENTRY_CHARGER_DEVICE_NAME} not defined"
                    )

                global_defaults_allocated_power = compose_entity_id(
                    NUMBER, OPTION_GLOBAL_DEFAULTS_ID, NUMBER_CHARGER_ALLOCATED_POWER
                )
                global_defaults_device_entry: DeviceEntry | None = (
                    self.get_device_entry(global_defaults_allocated_power)
                )
                if not global_defaults_device_entry:
                    raise ValueError(
                        f"Charger device {custom_charger_name} not found in device registry."
                    )

                custom_charger_display_name = (
                    f"{SUBENTRY_TYPE_CUSTOM} {custom_charger_name}"
                )
                custom_charger_config_name = slugify(f"{custom_charger_display_name}")

                _LOGGER.info(
                    "Creating subentry %d for charger '%s' with unique_id '%s'",
                    len(config_entry.subentries) + 1,
                    custom_charger_name,
                    custom_charger_config_name,
                )

                # Check if subentry with this unique_id already exists
                subentry_id = get_subentry_id(config_entry, custom_charger_config_name)
                if subentry_id is not None:
                    return self.async_abort(reason=ERROR_DEVICE_ALREADY_ADDED)

                # Create new subentry
                self.hass.config_entries.async_add_subentry(
                    config_entry,
                    ConfigSubentry(
                        subentry_type=SUBENTRY_TYPE_CUSTOM,
                        title=custom_charger_display_name,
                        unique_id=custom_charger_config_name,
                        data=MappingProxyType(  # make data immutable
                            {
                                SUBENTRY_CHARGER_DEVICE_DOMAIN: DOMAIN,  # Integration domain
                                SUBENTRY_CHARGER_DEVICE_NAME: custom_charger_name,  # Integration-specific device name
                                SUBENTRY_CHARGER_DEVICE_ID: global_defaults_device_entry.id,  # Integration-specific device ID
                            }
                        ),
                    ),
                )

                self.setup_options(
                    config_entry,
                    custom_charger_config_name,
                    slugify(custom_charger_name),
                )

                _LOGGER.info(
                    "Created subentry %d for charger '%s' with config_name '%s'",
                    len(config_entry.subentries),
                    custom_charger_name,
                    custom_charger_config_name,
                )

                # Must return with SubentryFlowResult as stipulated in the return type
                return self.async_abort(
                    reason=ERROR_SUBENTRY_CREATED,
                    description_placeholders={
                        "subentry": custom_charger_config_name,
                        "subentry_count": f"{len(config_entry.subentries)}",
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_SELECT_CHARGER_SCHEMA, errors=errors
        )
