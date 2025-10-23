"""Config flow for the solarcharger integration."""

from __future__ import annotations

import logging
from typing import Any

from packaging.version import parse as parse_version
import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass

# import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    DeviceFilterSelectorConfig,
    DeviceSelector,
    DeviceSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    # NumberSelector,
)

from .config_options_flow import ConfigOptionsFlowHandler
from .config_subentry_flow import SUBENTRY_TYPE_CHARGER, AddChargerSubEntryFlowHandler
from .const import CHARGER_DOMAIN_OCPP, CHARGER_DOMAIN_TESLA_CUSTOM, DOMAIN
from .exceptions.validation_exception import ValidationExceptionError

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


CONF_NET_POWER = "net_power"
CONF_NET_POWER_DEFAULT = "sensor.net_power"

CONF_CHARGER_DEVICE = "charger_device"
CONF_DEVICE_ORIGIN = "device_origin"
CONF_DEVICE_NAME_DEFAULT = "device_name_default"

STEP_SOURCE_POWER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NET_POWER, default=None): EntitySelector(
            EntitySelectorConfig(
                multiple=False,
                domain=["sensor"],
                device_class=[SensorDeviceClass.POWER],
            )
        ),
    }
)

# _charger_integration_filter_list: list[DeviceFilterSelectorConfig] = [
#     DeviceFilterSelectorConfig(integration=CHARGER_DOMAIN_TESLA_CUSTOM),
#     DeviceFilterSelectorConfig(integration=CHARGER_DOMAIN_OCPP),
# ]

# STEP_SELECT_CHARGER_SCHEMA = vol.Schema(
#     {
#         vol.Required(CONF_CHARGER_DEVICE): DeviceSelector(
#             DeviceSelectorConfig(
#                 multiple=False,
#                 filter=_charger_integration_filter_list,
#             )
#         ),
#     }
# )


# ----------------------------------------------------------------------------
def validate_charger_selection(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger selection step."""
    if not data.get(CONF_CHARGER_DEVICE):
        raise ValidationExceptionError("base", "select_charger_error")

    return data


def validate_charger_config(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger config step."""
    return data


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Charger."""

    VERSION = 1
    MINOR_VERSION = 0

    cf_data: dict | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the config flow."""
        super().__init__(*args, **kwargs)
        self.cf_data = {}

    # ----------------------------------------------------------------------------
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ConfigOptionsFlowHandler:
        """Get the options flow for this handler."""
        # see https://developers.home-assistant.io/blog/2024/11/12/options-flow/
        if parse_version(ha_version) < parse_version("2024.11.0"):
            return ConfigOptionsFlowHandler(config_entry=config_entry)

        return ConfigOptionsFlowHandler()

    # ----------------------------------------------------------------------------
    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_CHARGER: AddChargerSubEntryFlowHandler}

    # ----------------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entry point for initial config."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.validate_power_input(user_input, errors)
            if not errors and self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=user_input
                )

            return self.async_create_entry(
                title="SolarCharger",
                data=user_input,
            )

        config_entries: list[ConfigEntry] = self._async_current_entries()
        if config_entries:
            if len(config_entries) >= 1:
                return self.async_abort(reason="single_instance_allowed")

        return self.async_show_form(
            step_id="user", data_schema=STEP_SOURCE_POWER_SCHEMA, errors=errors
        )

    # ----------------------------------------------------------------------------
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle reconfiguration of an existing config entry."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._abort_if_unique_id_mismatch()

            self.validate_power_input(user_input, errors)

            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=user_input
                )

        # Get entity name
        net_power: str = self._get_reconfigure_entry().data[CONF_NET_POWER]

        net_power_schema = vol.Schema(
            {
                vol.Required(CONF_NET_POWER, default=net_power): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False,
                        domain="sensor",
                        device_class=[SensorDeviceClass.POWER],
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=net_power_schema,
            errors=errors,
        )

    # ----------------------------------------------------------------------------
    def validate_power_input(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> dict[str, Any]:
        """Validate the user input for the power collection step."""
        # Return info that you want to store in the config entry.
        return data
