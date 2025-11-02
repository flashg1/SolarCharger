"""Config flow for the solarcharger integration."""

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

# import homeassistant.helpers.config_validation as cv
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.selector import (
    DeviceFilterSelectorConfig,
    DeviceSelector,
    DeviceSelectorConfig,
    #    EntitySelector,
    #    EntitySelectorConfig,
    #    NumberSelector,
)
from homeassistant.util import slugify

from .config_option_utils import get_subentry_id
from .config_options_flow import reset_api_entities
from .const import (
    CHARGER_DOMAIN_OCPP,
    CHARGER_DOMAIN_TESLA_CUSTOM,
    OPTION_CHARGER_DEVICE_NAME,
    SUBENTRY_THIRDPARTY_DEVICE_ID,
    SUBENTRY_THIRDPARTY_DEVICE_NAME,
    SUBENTRY_THIRDPARTY_DOMAIN,
    SUBENTRY_TYPE_CHARGER,
    SUPPORTED_CHARGER_DOMAIN_LIST,
)
from .exceptions.validation_exception import ValidationExceptionError

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# Not used
# SUBENTRY_DEVICE_ORIGIN = "device_origin"
# SUBENTRY_DEVICE_NAME_DEFAULT = "device_name_default"

_charger_integration_filter_list: list[DeviceFilterSelectorConfig] = [
    DeviceFilterSelectorConfig(integration=CHARGER_DOMAIN_TESLA_CUSTOM),
    DeviceFilterSelectorConfig(integration=CHARGER_DOMAIN_OCPP),
]

STEP_SELECT_CHARGER_SCHEMA = vol.Schema(
    {
        vol.Required(SUBENTRY_THIRDPARTY_DEVICE_ID): DeviceSelector(
            DeviceSelectorConfig(
                multiple=False,
                filter=_charger_integration_filter_list,
            )
        ),
    }
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
def validate_charger_selection(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger selection step."""
    if not data.get(SUBENTRY_THIRDPARTY_DEVICE_ID):
        raise ValidationExceptionError("base", "select_charger_error")  # noqa: EM101

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
class AddChargerSubEntryFlowHandler(ConfigSubentryFlow):
    """Handles subentry flow for creating charger."""

    # cf_data: dict | None = None

    # ----------------------------------------------------------------------------
    # def _set_global_defaults(self, data: dict[str, dict[str, Any]]) -> None:
    #     """Set global data for the config flow."""
    #     self.cf_data = data or {}

    # ----------------------------------------------------------------------------
    def setup_options(
        self, config_entry: ConfigEntry, subentry_unique_id: str, device_name: str
    ) -> None:
        """Set up default options for the new subentry."""

        _LOGGER.debug(
            "Setting up default options for subentry with unique_id: %s",
            subentry_unique_id,
        )

        # entry.options = {
        #     **entry.options,
        #     subentry_unique_id: {
        #         OPTION_CHARGER_DEVICE_NAME: device_name,
        #     },
        # }

        # await self.reset_api_entities(
        #     config_name,
        #     device_name,
        #     data,
        # )

        data: dict[str, Any] = {
            OPTION_CHARGER_DEVICE_NAME: device_name,
        }
        reset_api_entities(
            config_entry,
            subentry_unique_id,
            data,
            reset_all_entities=True,
        )

        self.hass.config_entries.async_update_entry(
            config_entry,
            options=config_entry.options
            | {
                subentry_unique_id: data,
            },
        )

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
                # self.cf_data = input_data
                # await self.async_step_config_charger()

                # Get charger device subentry
                thirdparty_charger_id: str | None = input_data.get(
                    SUBENTRY_THIRDPARTY_DEVICE_ID
                )
                if not thirdparty_charger_id:
                    raise ValueError(
                        f"Subentry {SUBENTRY_THIRDPARTY_DEVICE_ID} not defined"
                    )
                registry: DeviceRegistry = dr.async_get(self.hass)
                thirdparty_charger: DeviceEntry | None = registry.async_get(
                    thirdparty_charger_id
                )
                if not thirdparty_charger:
                    raise ValueError(
                        f"Charger device {thirdparty_charger_id} not found in device registry."
                    )

                # Get charger domain and name to create unique_id
                # Tesla has 2 config entries in "Device info": Tesla Custom Integration, Template
                thirdparty_config_entry_id: str | None = None
                thirdparty_config_entry: ConfigEntry | None = None

                for entry_id in thirdparty_charger.config_entries:
                    entry: ConfigEntry | None = (
                        self.hass.config_entries.async_get_entry(entry_id)
                    )
                    if entry is not None:
                        # Best guess to match
                        if entry.domain in SUPPORTED_CHARGER_DOMAIN_LIST:
                            thirdparty_config_entry_id = entry_id
                            thirdparty_config_entry = entry
                            break

                # Tesla has 2 config entries in "Device info": Tesla Custom Integration, Template
                # So following can sometimes can get Template as domain name!
                # thirdparty_config_entry_id: str = next(
                #     iter(thirdparty_charger.config_entries)
                # )
                # thirdparty_config_entry: ConfigEntry | None = (
                #     self.hass.config_entries.async_get_entry(thirdparty_config_entry_id)
                # )

                if not thirdparty_config_entry:
                    raise ValueError(
                        f"Charger config entry {thirdparty_config_entry_id} not found."
                    )
                thirdparty_display_name = (
                    f"{thirdparty_config_entry.domain} {thirdparty_charger.name}"
                )
                thirdparty_config_name = slugify(f"{thirdparty_display_name}")

                _LOGGER.info(
                    "Creating subentry %d for charger '%s' with unique_id '%s'",
                    len(config_entry.subentries) + 1,
                    thirdparty_charger.name,
                    thirdparty_config_name,
                )

                # Check if subentry with this unique_id already exists
                subentry_id = get_subentry_id(config_entry, thirdparty_config_name)
                if subentry_id is not None:
                    return self.async_abort(reason="device_already_added")

                # Create new subentry
                if (
                    not thirdparty_config_entry.domain
                    or not thirdparty_charger.name
                    or not thirdparty_charger_id
                ):
                    raise ValueError(
                        f"Charger config entry domain, name, or ID is missing: "
                        f"{thirdparty_config_entry.domain=}, {thirdparty_charger.name=}, {thirdparty_charger_id=}"
                    )

                self.hass.config_entries.async_add_subentry(
                    config_entry,
                    ConfigSubentry(
                        subentry_type=SUBENTRY_TYPE_CHARGER,
                        title=thirdparty_display_name,
                        unique_id=thirdparty_config_name,
                        data=MappingProxyType(  # make data immutable
                            {
                                SUBENTRY_THIRDPARTY_DOMAIN: thirdparty_config_entry.domain,  # Integration domain
                                SUBENTRY_THIRDPARTY_DEVICE_NAME: thirdparty_charger.name,  # Integration-specific device name
                                SUBENTRY_THIRDPARTY_DEVICE_ID: thirdparty_charger_id,  # Integration-specific device ID
                            }
                        ),
                    ),
                )

                self.setup_options(
                    config_entry,
                    thirdparty_config_name,
                    slugify(thirdparty_charger.name),
                )

                _LOGGER.info(
                    "Created subentry %d for charger '%s' with config_name '%s'",
                    len(config_entry.subentries),
                    thirdparty_charger.name,
                    thirdparty_config_name,
                )

                # Must return with SubentryFlowResult as stipulated in the return type
                return self.async_abort(
                    reason="device_subentry_created",
                    description_placeholders={
                        "subentry": thirdparty_config_name,
                        "subentry_count": f"{len(config_entry.subentries)}",
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_SELECT_CHARGER_SCHEMA, errors=errors
        )
