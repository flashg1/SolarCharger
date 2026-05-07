"""Config flow for the solarcharger integration."""

import logging
from typing import Any

from packaging.version import parse as parse_version
import voluptuous as vol

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

from .config.config_options_flow import ConfigOptionsFlowHandler
from .config.config_subentry_charger import AddChargerSubEntryFlowHandler
from .config.config_subentry_custom import AddCustomSubEntryFlowHandler
from .config.config_utils import POWER_ENTITY_SELECTOR, WAIT_TIME_SELECTOR
from .const import (
    CONFIG_CURRENT_UPDATE_PERIOD,
    CONFIG_NET_POWER_SENSOR,
    CONFIG_WAIT_NET_POWER_UPDATE,
    DEFAULT_CURRENT_UPDATE_PERIOD,
    DEFAULT_WAIT_NET_POWER_UPDATE,
    DOMAIN,
    ERROR_CURRENT_UPDATE_PERIOD,
    ERROR_WAIT_NET_POWER_UPDATE,
    NAME,
    SUBENTRY_TYPE_CHARGER,
    SUBENTRY_TYPE_CUSTOM,
)
from .exceptions.validation_exception import ValidationExceptionError

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONF_CHARGER_DEVICE = "charger_device"


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

        return {
            SUBENTRY_TYPE_CHARGER: AddChargerSubEntryFlowHandler,
            SUBENTRY_TYPE_CUSTOM: AddCustomSubEntryFlowHandler,
        }

    # ----------------------------------------------------------------------------
    def _validate_user_config(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> dict[str, Any]:
        """Validate the user input for the power collection step."""

        wait_net_power_update: float = data[CONFIG_WAIT_NET_POWER_UPDATE]
        current_update_period: float = data[CONFIG_CURRENT_UPDATE_PERIOD]

        if current_update_period < wait_net_power_update:
            errors[CONFIG_WAIT_NET_POWER_UPDATE] = ERROR_WAIT_NET_POWER_UPDATE
            errors[CONFIG_CURRENT_UPDATE_PERIOD] = ERROR_CURRENT_UPDATE_PERIOD

        # Return info that you want to store in the config entry.
        return data

    # ----------------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entry point for initial config."""
        errors: dict[str, str] = {}

        if user_input is not None:
            config_data = self._validate_user_config(user_input, errors)

            if not errors:
                # Reconfigure step: reconfigure entry.
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=config_data
                    )

                # Initial user step: create entry.
                return self.async_create_entry(title=NAME, data=config_data)

        # The following is not required since single_config_entry is set in manifest.json.
        # config_entries: list[ConfigEntry] = self._async_current_entries()
        # if config_entries:
        #     if len(config_entries) >= 1:
        #         return self.async_abort(reason=ERROR_SINGLE_INSTANCE_ALLOWED)

        if user_input is not None:
            # User step or reconfigure step with incorrect user input.
            net_power_sensor: str = user_input.get(CONFIG_NET_POWER_SENSOR)
            wait_net_power_update: float = user_input.get(CONFIG_WAIT_NET_POWER_UPDATE)
            current_update_period: float = user_input.get(CONFIG_CURRENT_UPDATE_PERIOD)

        elif self.source == SOURCE_RECONFIGURE:
            # Starting reconfigure step, user_input is None.
            # Get previously configured valies to show as defaults in the form.
            self._abort_if_unique_id_mismatch()
            net_power_sensor: str = self._get_reconfigure_entry().data[
                CONFIG_NET_POWER_SENSOR
            ]
            wait_net_power_update: float = self._get_reconfigure_entry().data[
                CONFIG_WAIT_NET_POWER_UPDATE
            ]
            current_update_period: float = self._get_reconfigure_entry().data[
                CONFIG_CURRENT_UPDATE_PERIOD
            ]

        else:
            # Starting initial user step, user_input is None.
            net_power_sensor: str | None = None
            wait_net_power_update: float = DEFAULT_WAIT_NET_POWER_UPDATE
            current_update_period: float = DEFAULT_CURRENT_UPDATE_PERIOD

        # Create schema with default values.
        step_user_schema = vol.Schema(
            {
                vol.Required(
                    CONFIG_NET_POWER_SENSOR, default=net_power_sensor
                ): POWER_ENTITY_SELECTOR,
                vol.Optional(
                    CONFIG_WAIT_NET_POWER_UPDATE, default=wait_net_power_update
                ): WAIT_TIME_SELECTOR,
                vol.Optional(
                    CONFIG_CURRENT_UPDATE_PERIOD, default=current_update_period
                ): WAIT_TIME_SELECTOR,
            }
        )

        # Use single step for both "user" and "reconfigure", so no need to duplicate translations.
        return self.async_show_form(
            step_id="user", data_schema=step_user_schema, errors=errors
        )

    # ----------------------------------------------------------------------------
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing config entry."""

        return await self.async_step_user(user_input)
