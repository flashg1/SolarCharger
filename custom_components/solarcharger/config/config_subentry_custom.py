# ruff: noqa: TID252, RET504
"""Config subentry flow to create user custom charger."""

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

from ..const import (
    DOMAIN,
    ERROR_DEVICE_ALREADY_ADDED,
    ERROR_SELECT_CHARGER,
    ERROR_SUBENTRY_CREATED,
    OPTION_CHARGER_NAME,
    OPTION_GLOBAL_DEFAULTS_ID,
    SENSOR,
    SENSOR_DELTA_ALLOCATED_POWER,
    SUBENTRY_CHARGER_DEVICE_DOMAIN,
    SUBENTRY_CHARGER_DEVICE_ID,
    SUBENTRY_CHARGER_DEVICE_NAME,
    SUBENTRY_CHARGER_DEVICE_SUBDOMAIN,
    SUBENTRY_TYPE_CUSTOM,
)
from ..entity import compose_entity_id
from ..exceptions.validation_exception import ValidationExceptionError
from ..helpers.utils import compose_subdomain
from .config_options_flow import process_api_config
from .config_utils import (
    TEXT_SELECTOR,
    async_ha_store_load,
    async_ha_store_save,
    async_ha_store_update_device_list,
    get_subentry_id,
    ha_store_open,
)

# ----------------------------------------------------------------------------
# Local constants and variables
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

STEP_SELECT_CHARGER_SCHEMA = vol.Schema(
    {
        vol.Required(SUBENTRY_CHARGER_DEVICE_NAME): TEXT_SELECTOR,
    }
)


# ----------------------------------------------------------------------------
# Global functions
# ----------------------------------------------------------------------------
def _validate_charger_selection(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger selection step."""
    if not data.get(SUBENTRY_CHARGER_DEVICE_NAME):
        raise ValidationExceptionError("base", ERROR_SELECT_CHARGER)

    return data


# ----------------------------------------------------------------------------
def _validate_charger_config(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger config step."""
    return data


# ----------------------------------------------------------------------------
def _validate_power_input(_hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input for the power collection step."""
    # Return info that you want to store in the config entry.
    return data


# ----------------------------------------------------------------------------
async def _async_setup_options(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    subentry_unique_id: str,
    domain: str,
    name: str,
    device_id: str,
) -> None:
    """Set up default options for the new subentry."""

    device_name = slugify(name)
    _LOGGER.debug(
        "Setting up default options for subentry with unique_id: %s",
        subentry_unique_id,
    )

    data: dict[str, Any] = {
        OPTION_CHARGER_NAME: device_name,
    }

    # Look for historical config left behind by a previous installation.
    store = ha_store_open(hass, subentry_unique_id)
    store_config = await async_ha_store_load(store)
    if store_config is not None:
        data.update(store_config)

    process_api_config(config_entry, subentry_unique_id, data, is_init_all=True)

    # Save device settings to file storage.
    await async_ha_store_save(store, data)
    await async_ha_store_update_device_list(hass, domain, name, device_id)

    hass.config_entries.async_update_entry(
        config_entry,
        options=config_entry.options
        | {
            subentry_unique_id: data,
        },
    )


# ----------------------------------------------------------------------------
def _get_device_entry(hass: HomeAssistant, entity_id: str) -> DeviceEntry | None:
    """Get DeviceEntry for entity."""
    device_entry: DeviceEntry | None = None

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(entity_id)
    if entry:
        device_id = entry.device_id
        if device_id:
            device_registry: DeviceRegistry = dr.async_get(hass)
            device_entry = device_registry.async_get(device_id)

    return device_entry


# ----------------------------------------------------------------------------
async def async_create_custom_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry[Any],
    input_data: dict[str, Any],
) -> str | None:
    """Create custom device."""

    # Get charger device subentry
    custom_charger_name: str | None = input_data.get(SUBENTRY_CHARGER_DEVICE_NAME)
    if not custom_charger_name:
        error_msg = f"Subentry {SUBENTRY_CHARGER_DEVICE_NAME} not defined"
        # raise ValueError(error_msg)
        return error_msg

    custom_charger_display_name = f"{SUBENTRY_TYPE_CUSTOM} {custom_charger_name}"
    custom_charger_config_name = slugify(f"{custom_charger_display_name}")

    global_defaults_net_power = compose_entity_id(
        SENSOR, OPTION_GLOBAL_DEFAULTS_ID, SENSOR_DELTA_ALLOCATED_POWER
    )
    global_defaults_device_entry: DeviceEntry | None = _get_device_entry(
        hass, global_defaults_net_power
    )
    if not global_defaults_device_entry:
        error_msg = f"{OPTION_GLOBAL_DEFAULTS_ID} entry not found in device registry."
        # raise ValueError(error_msg)
        return error_msg

    #######################################################
    # Global defaults device must be created first in order to get global_defaults_device_entry.id
    # Global defaults device is required for this custom charger to function.
    # A newly created global defaults device will have different ID to the old.
    #######################################################
    device_id = global_defaults_device_entry.id

    # custom_charger_subdomain = compose_subdomain(
    #     config_entry.domain,
    #     MANUFACTURER,
    #     DEVICE_MODEL_MAP[CONFIG_NAME_GLOBAL_DEFAULTS],
    # )
    custom_charger_subdomain = compose_subdomain(
        config_entry.domain,
        global_defaults_device_entry.manufacturer,
        global_defaults_device_entry.model,
    )

    _LOGGER.info(
        "Creating subentry %d: charger='%s', unique_id='%s', sub-domain='%s'",
        len(config_entry.subentries) + 1,
        custom_charger_name,
        custom_charger_config_name,
        custom_charger_subdomain,
    )

    # Check if subentry with this unique_id already exists
    subentry_id = get_subentry_id(config_entry, custom_charger_config_name)
    if subentry_id is not None:
        return ERROR_DEVICE_ALREADY_ADDED

    # Create new subentry
    hass.config_entries.async_add_subentry(
        config_entry,
        ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_CUSTOM,
            title=custom_charger_display_name,
            unique_id=custom_charger_config_name,
            data=MappingProxyType(  # make data immutable
                {
                    SUBENTRY_CHARGER_DEVICE_DOMAIN: DOMAIN,  # Integration domain
                    SUBENTRY_CHARGER_DEVICE_SUBDOMAIN: custom_charger_subdomain,  # Integration sub-domain
                    SUBENTRY_CHARGER_DEVICE_NAME: custom_charger_name,  # Integration-specific device name
                    SUBENTRY_CHARGER_DEVICE_ID: device_id,  # Integration-specific device ID
                }
            ),
        ),
    )

    await _async_setup_options(
        hass,
        config_entry,
        custom_charger_config_name,
        DOMAIN,
        custom_charger_name,
        device_id,
    )

    _LOGGER.info(
        "Created subentry %d: charger='%s', unique_id='%s', sub-domain='%s'",
        len(config_entry.subentries),
        custom_charger_name,
        custom_charger_config_name,
        custom_charger_subdomain,
    )

    return None


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class AddCustomSubEntryFlowHandler(ConfigSubentryFlow):
    """Handles subentry flow for creating charger."""

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
                input_data = _validate_charger_selection(self.hass, user_input)
            except ValidationExceptionError as ex:
                errors[ex.base] = ex.key

            if not errors and input_data is not None:
                error_msg = await async_create_custom_device(
                    self.hass, config_entry, input_data
                )
                if error_msg is not None:
                    _LOGGER.error("%s", error_msg)
                    return self.async_abort(reason=error_msg)

                # Must return with SubentryFlowResult as stipulated in the return type
                return self.async_abort(
                    reason=ERROR_SUBENTRY_CREATED,
                    # description_placeholders={
                    #     "subentry": custom_charger_config_name,
                    #     "subentry_count": f"{len(config_entry.subentries)}",
                    # },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_SELECT_CHARGER_SCHEMA, errors=errors
        )
