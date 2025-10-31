"""Config flow for the solarcharger integration."""

from __future__ import annotations

from copy import deepcopy
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentry,
    OptionsFlow,
)
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

# from homeassistant.helpers.typing import UNDEFINED, UndefinedType
# from homeassistant.helpers.template import device_name
from homeassistant.util import slugify

from .config_option_utils import (
    BUTTON_ENTITY_SELECTOR,
    BUTTON_ENTITY_SELECTOR_READ_ONLY,
    LOCATION_ENTITY_SELECTOR,
    LOCATION_ENTITY_SELECTOR_READ_ONLY,
    NUMBER_ENTITY_SELECTOR,
    NUMBER_ENTITY_SELECTOR_READ_ONLY,
    SENSOR_ENTITY_SELECTOR,
    SENSOR_ENTITY_SELECTOR_READ_ONLY,
    SWITCH_ENTITY_SELECTOR,
    SWITCH_ENTITY_SELECTOR_READ_ONLY,
    TEXT_SELECTOR,
    TEXT_SELECTOR_READ_ONLY,
    entity_selector,
    get_saved_option_value,
    get_subentry_id,
    reset_api_entities,
)
from .const import (
    CHARGE_API_ENTITIES,
    CONTROL_CHARGER_ALLOCATED_POWER,
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_LOCATION_STATE_LIST,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_CHARGING_STATE_LIST,
    OPTION_CHARGER_CONNECT_STATE_LIST,
    OPTION_CHARGER_CONNECT_TRIGGER_LIST,
    OPTION_CHARGER_DEVICE_NAME,
    OPTION_CHARGER_EFFECTIVE_VOLTAGE,
    OPTION_CHARGER_GET_CHARGE_CURRENT,
    OPTION_CHARGER_MAX_CURRENT,
    OPTION_CHARGER_MAX_SPEED,
    OPTION_CHARGER_MIN_CURRENT,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
    OPTION_CHARGER_SET_CHARGE_CURRENT,
    OPTION_GLOBAL_DEFAULT_ENTITY_LIST,
    OPTION_GLOBAL_DEFAULTS_ID,
    OPTION_ID,
    OPTION_NAME,
    OPTION_SELECT_SETTINGS,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER,
    OPTION_SUNSET_ELEVATION_END_TRIGGER,
    OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
    OPTION_WAIT_CHARGEE_UPDATE_HA,
    OPTION_WAIT_CHARGEE_WAKEUP,
    OPTION_WAIT_CHARGER_AMP_CHANGE,
    OPTION_WAIT_CHARGER_OFF,
    OPTION_WAIT_CHARGER_ON,
    OPTION_WAIT_NET_POWER_UPDATE,
    SUBENTRY_DEVICE_DOMAIN,
    SUBENTRY_TYPE_CHARGER,
)
from .exceptions.validation_exception import ValidationExceptionError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# GLOBAL_DEFAULTS_ID: str = uuid4().hex
# GLOBAL_DEFAULTS_SUBENTRY: ConfigSubentry = ConfigSubentry(
#     title="Global defaults",
#     unique_id=OPTION_GLOBAL_DEFAULTS,
#     subentry_id=GLOBAL_DEFAULTS_ID,
#     subentry_type="global_defaults",
#     data=MappingProxyType(  # make data immutable
#         {
#             SUBENTRY_DEVICE_DOMAIN: "N/A",  # Integration domain
#             SUBENTRY_DEVICE_NAME: "N/A",  # Integration-specific device name
#             SUBENTRY_CHARGER_DEVICE: "N/A",  # Integration-specific device ID
#         }
#     ),
# )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# async def validate_init_input(
#     _hass: HomeAssistant,
#     data: dict[str, Any],
# ) -> dict[str, Any]:
#     """Validate the input data for the options flow."""
#     return data


# ----------------------------------------------------------------------------
# def get_config_item_name(device_name, config_item) -> str:
#     """Get unique config parameter name."""
#     # return f"{device_name}-{config_item}"
#     return config_item


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ConfigOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for solarcharger."""

    def __init__(self, config_entry: ConfigEntry | None = None):
        """Initialize options flow.

        @see https://developers.home-assistant.io/blog/2024/11/12/options-flow/
        """
        if config_entry is not None:
            self.config_entry = config_entry

    # ----------------------------------------------------------------------------
    @staticmethod
    def get_option_value(config_entry: ConfigEntry, key: str) -> Any:
        """Get the value of an option from the config entry."""
        return config_entry.options.get(key, OPTION_GLOBAL_DEFAULT_ENTITY_LIST.get(key))

    # ----------------------------------------------------------------------------
    def _prompt(
        self, cls, subentry: ConfigSubentry, config_item: str, use_default: bool
    ) -> vol.Required | vol.Optional:
        saved_val = get_saved_option_value(
            self.config_entry, subentry, config_item, use_default
        )

        if saved_val:
            return cls(config_item, default=saved_val)

        return cls(config_item)

    # ----------------------------------------------------------------------------
    def _required(
        self, subentry: ConfigSubentry, config_item: str, use_default: bool
    ) -> vol.Required:
        saved_val = get_saved_option_value(
            self.config_entry, subentry, config_item, use_default
        )

        if saved_val:
            return vol.Required(config_item, default=saved_val)

        return vol.Required(config_item)

    # ----------------------------------------------------------------------------
    def _optional(
        self, subentry: ConfigSubentry, config_item: str, use_default: bool
    ) -> vol.Optional:
        saved_val = get_saved_option_value(
            self.config_entry, subentry, config_item, use_default
        )

        if saved_val:
            return vol.Optional(config_item, default=saved_val)

        return vol.Optional(config_item)

    # ----------------------------------------------------------------------------
    def _charger_general_options_schema(
        self, subentry: ConfigSubentry, use_default: bool
    ) -> dict[Any, Any]:
        """Charger general options."""

        return {
            self._optional(
                subentry, OPTION_CHARGER_EFFECTIVE_VOLTAGE, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_MAX_CURRENT, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_MAX_SPEED, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_MIN_CURRENT, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_MIN_WORKABLE_CURRENT, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_POWER_ALLOCATION_WEIGHT, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_SUNRISE_ELEVATION_START_TRIGGER, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_SUNSET_ELEVATION_END_TRIGGER, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_WAIT_NET_POWER_UPDATE, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_WAIT_CHARGEE_WAKEUP, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_WAIT_CHARGEE_UPDATE_HA, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_WAIT_CHARGEE_LIMIT_CHANGE, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_WAIT_CHARGER_ON, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_WAIT_CHARGER_OFF, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_WAIT_CHARGER_AMP_CHANGE, use_default
            ): NUMBER_ENTITY_SELECTOR,
        }

    # ----------------------------------------------------------------------------
    def _charger_control_entities_schema(
        self, subentry: ConfigSubentry, use_default: bool
    ) -> dict[Any, Any]:
        """Charger control entities."""
        api_entities: dict[str, str | None] | None = None

        device_domain = subentry.data.get(SUBENTRY_DEVICE_DOMAIN)
        if device_domain:
            api_entities = CHARGE_API_ENTITIES.get(device_domain)

        return {
            self._optional(
                subentry, OPTION_CHARGER_DEVICE_NAME, use_default
            ): entity_selector(
                None,
                OPTION_CHARGER_DEVICE_NAME,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_PLUGGED_IN_SENSOR, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_PLUGGED_IN_SENSOR,
                SENSOR_ENTITY_SELECTOR_READ_ONLY,
                SENSOR_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CONNECT_TRIGGER_LIST, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_CONNECT_TRIGGER_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CONNECT_STATE_LIST, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_CONNECT_STATE_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_ON_OFF_SWITCH, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_ON_OFF_SWITCH,
                SWITCH_ENTITY_SELECTOR_READ_ONLY,
                SWITCH_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CHARGING_SENSOR, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_CHARGING_SENSOR,
                SENSOR_ENTITY_SELECTOR_READ_ONLY,
                SENSOR_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CHARGING_STATE_LIST, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_CHARGING_STATE_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_GET_CHARGE_CURRENT, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_GET_CHARGE_CURRENT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_SET_CHARGE_CURRENT, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGER_SET_CHARGE_CURRENT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_SOC_SENSOR, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGEE_SOC_SENSOR,
                SENSOR_ENTITY_SELECTOR_READ_ONLY,
                SENSOR_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_CHARGE_LIMIT, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGEE_CHARGE_LIMIT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_LOCATION_SENSOR, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGEE_LOCATION_SENSOR,
                LOCATION_ENTITY_SELECTOR_READ_ONLY,
                LOCATION_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_LOCATION_STATE_LIST, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGEE_LOCATION_STATE_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_WAKE_UP_BUTTON, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGEE_WAKE_UP_BUTTON,
                BUTTON_ENTITY_SELECTOR_READ_ONLY,
                BUTTON_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_UPDATE_HA_BUTTON, use_default
            ): entity_selector(
                api_entities,
                OPTION_CHARGEE_UPDATE_HA_BUTTON,
                BUTTON_ENTITY_SELECTOR_READ_ONLY,
                BUTTON_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, CONTROL_CHARGER_ALLOCATED_POWER, use_default
            ): entity_selector(
                api_entities,
                CONTROL_CHARGER_ALLOCATED_POWER,
                BUTTON_ENTITY_SELECTOR_READ_ONLY,
                BUTTON_ENTITY_SELECTOR,
            ),
        }

    # ----------------------------------------------------------------------------
    async def validate_init_input(
        self,
        config_name: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate the input data for the options flow."""

        return reset_api_entities(
            self.config_entry,
            config_name,
            data,
        )

    # ----------------------------------------------------------------------------
    async def async_step_config_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select charger device to configure."""

        # Must deepcopy to avoid modifying original options, otherwise changes are not saved.
        options_config: dict[str, Any] = deepcopy(dict(self.config_entry.options))

        errors = {}
        input_data = None
        combine_schema = {}

        config_name = self._config_name
        subentry_id = get_subentry_id(self.config_entry, config_name)
        if not subentry_id:
            errors["subentry_id_not_found"] = f"Subentry ID not found for {config_name}"
            return self.async_abort(
                reason="subentry_id_not_found",
            )

        # Process options
        if user_input is not None:
            if config_name:
                # validate input
                try:
                    # input_data = await validate_init_input(
                    #     self.hass, config_name, user_input
                    # )
                    input_data = await self.validate_init_input(config_name, user_input)
                except ValidationExceptionError as ex:
                    errors[ex.base] = ex.key
                except ValueError:
                    errors["base"] = "invalid_number_format"

                if not errors and input_data is not None:
                    device_options = options_config.get(config_name)
                    if not device_options:
                        device_options = {}
                        device_options[OPTION_NAME] = config_name
                        device_options[OPTION_ID] = subentry_id
                        options_config[config_name] = device_options

                    device_options.update(input_data)

                    return self.async_create_entry(data=options_config)

        # Prompt user for options
        subentry = self.config_entry.subentries.get(subentry_id)
        if not subentry:
            errors["subentry_not_found"] = f"Subentry not found for {config_name}"
            return self.async_abort(
                reason="subentry_not_found",
            )

        if subentry.unique_id == OPTION_GLOBAL_DEFAULTS_ID:
            general_schema = self._charger_general_options_schema(
                subentry, use_default=True
            )
            combine_schema = {**general_schema}
        else:
            general_schema = self._charger_general_options_schema(
                subentry, use_default=False
            )
            entities_schema = self._charger_control_entities_schema(
                subentry, use_default=True
            )
            # combine_schema = {
            #     vol.Required("General config"): section(
            #         vol.Schema(general_schema), {"collapsed": True}
            #     ),
            #     vol.Required("Device entities"): section(
            #         vol.Schema(entities_schema), {"collapsed": True}
            #     ),
            # }
            combine_schema = {**general_schema, **entities_schema}

        return self.async_show_form(
            step_id="config_device",
            data_schema=vol.Schema(combine_schema),
            errors=errors,
            last_step=True,
        )

    # ----------------------------------------------------------------------------
    # See https://developers.home-assistant.io/docs/data_entry_flow_index
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Entry point for options config. Select charger device to configure."""
        errors = {}

        if user_input is not None:
            self._config_name = user_input[OPTION_SELECT_SETTINGS]
            return await self.async_step_config_device(None)

        if not self.config_entry.subentries:
            errors["empty_charger_device_list"] = "Use + sign to add charger devices."
            return self.async_abort(
                reason="empty_charger_device_list",
            )

        device_list = [OPTION_GLOBAL_DEFAULTS_ID]
        for subentry in self.config_entry.subentries.values():
            if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
                if subentry.unique_id:
                    device_list.append(subentry.unique_id)

        fields = {}
        fields[vol.Required(OPTION_SELECT_SETTINGS)] = SelectSelector(
            SelectSelectorConfig(
                options=device_list,
                custom_value=True,
                multiple=False,
            )
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=False,
        )
