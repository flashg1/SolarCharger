"""Config flow for the solarcharger integration."""

from __future__ import annotations

from copy import deepcopy
import logging
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

from .config_utils import (
    BUTTON_ENTITY_SELECTOR,
    BUTTON_ENTITY_SELECTOR_READ_ONLY,
    LOCATION_ENTITY_SELECTOR,
    LOCATION_ENTITY_SELECTOR_READ_ONLY,
    NUMBER_ENTITY_SELECTOR,
    NUMBER_ENTITY_SELECTOR_READ_ONLY,
    PERCENT_SELECTOR,
    SENSOR_ENTITY_SELECTOR,
    SENSOR_ENTITY_SELECTOR_READ_ONLY,
    SWITCH_ENTITY_SELECTOR,
    SWITCH_ENTITY_SELECTOR_READ_ONLY,
    TEXT_SELECTOR,
    TEXT_SELECTOR_READ_ONLY,
    TIME_ENTITY_SELECTOR,
    choose_selector,
    get_device_api_entities,
    get_saved_option_value,
    get_subentry_id,
    reset_api_entities,
)
from .const import (
    DEFAULT_CHARGE_LIMIT_FRIDAY,
    DEFAULT_CHARGE_LIMIT_MONDAY,
    DEFAULT_CHARGE_LIMIT_SATURDAY,
    DEFAULT_CHARGE_LIMIT_SUNDAY,
    DEFAULT_CHARGE_LIMIT_THURSDAY,
    DEFAULT_CHARGE_LIMIT_TUESDAY,
    DEFAULT_CHARGE_LIMIT_WEDNESDAY,
    NUMBER_CHARGE_LIMIT_FRIDAY,
    NUMBER_CHARGE_LIMIT_MONDAY,
    NUMBER_CHARGE_LIMIT_SATURDAY,
    NUMBER_CHARGE_LIMIT_SUNDAY,
    NUMBER_CHARGE_LIMIT_THURSDAY,
    NUMBER_CHARGE_LIMIT_TUESDAY,
    NUMBER_CHARGE_LIMIT_WEDNESDAY,
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
    NUMBER_CHARGER_ALLOCATED_POWER,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MAX_SPEED,
    NUMBER_CHARGER_MIN_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
    NUMBER_SUNSET_ELEVATION_END_TRIGGER,
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
    NUMBER_WAIT_CHARGEE_UPDATE_HA,
    NUMBER_WAIT_CHARGEE_WAKEUP,
    NUMBER_WAIT_CHARGER_AMP_CHANGE,
    NUMBER_WAIT_CHARGER_OFF,
    NUMBER_WAIT_CHARGER_ON,
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
    OPTION_CHARGER_GET_CHARGE_CURRENT,
    OPTION_CHARGER_MAX_CURRENT,
    OPTION_CHARGER_NAME,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    OPTION_CHARGER_SET_CHARGE_CURRENT,
    OPTION_GLOBAL_DEFAULT_ENTITIES,
    OPTION_GLOBAL_DEFAULTS_ID,
    OPTION_ID,
    OPTION_NAME,
    OPTION_SELECT_SETTINGS,
    SUBENTRY_CHARGER_TYPES,
    TIME_CHARGE_ENDTIME_FRIDAY,
    TIME_CHARGE_ENDTIME_MONDAY,
    TIME_CHARGE_ENDTIME_SATURDAY,
    TIME_CHARGE_ENDTIME_SUNDAY,
    TIME_CHARGE_ENDTIME_THURSDAY,
    TIME_CHARGE_ENDTIME_TUESDAY,
    TIME_CHARGE_ENDTIME_WEDNESDAY,
)
from .exceptions.validation_exception import ValidationExceptionError

# if TYPE_CHECKING:
#     from homeassistant.core import HomeAssistant

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
        return config_entry.options.get(key, OPTION_GLOBAL_DEFAULT_ENTITIES.get(key))

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
    # Matches with const.py OPTION_GLOBAL_DEFAULT_ENTITIES
    def _charger_environment_schema(
        self, subentry: ConfigSubentry, use_default: bool
    ) -> dict[Any, Any]:
        """Charger general options."""

        return {
            #####################################
            # Charge environment
            #####################################
            self._optional(
                subentry, NUMBER_CHARGER_EFFECTIVE_VOLTAGE, use_default
            ): NUMBER_ENTITY_SELECTOR,
            #####################################
            # Charge scheduling
            #####################################
            # Charge limit defaults
            self._optional(
                subentry, DEFAULT_CHARGE_LIMIT_MONDAY, use_default
            ): PERCENT_SELECTOR,
            self._optional(
                subentry, DEFAULT_CHARGE_LIMIT_TUESDAY, use_default
            ): PERCENT_SELECTOR,
            self._optional(
                subentry, DEFAULT_CHARGE_LIMIT_WEDNESDAY, use_default
            ): PERCENT_SELECTOR,
            self._optional(
                subentry, DEFAULT_CHARGE_LIMIT_THURSDAY, use_default
            ): PERCENT_SELECTOR,
            self._optional(
                subentry, DEFAULT_CHARGE_LIMIT_FRIDAY, use_default
            ): PERCENT_SELECTOR,
            self._optional(
                subentry, DEFAULT_CHARGE_LIMIT_SATURDAY, use_default
            ): PERCENT_SELECTOR,
            self._optional(
                subentry, DEFAULT_CHARGE_LIMIT_SUNDAY, use_default
            ): PERCENT_SELECTOR,
            # Charge limits
            self._optional(
                subentry, NUMBER_CHARGE_LIMIT_MONDAY, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_CHARGE_LIMIT_TUESDAY, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_CHARGE_LIMIT_WEDNESDAY, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_CHARGE_LIMIT_THURSDAY, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_CHARGE_LIMIT_FRIDAY, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_CHARGE_LIMIT_SATURDAY, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_CHARGE_LIMIT_SUNDAY, use_default
            ): NUMBER_ENTITY_SELECTOR,
            # Charge end times
            self._optional(
                subentry, TIME_CHARGE_ENDTIME_MONDAY, use_default
            ): TIME_ENTITY_SELECTOR,
            self._optional(
                subentry, TIME_CHARGE_ENDTIME_TUESDAY, use_default
            ): TIME_ENTITY_SELECTOR,
            self._optional(
                subentry, TIME_CHARGE_ENDTIME_WEDNESDAY, use_default
            ): TIME_ENTITY_SELECTOR,
            self._optional(
                subentry, TIME_CHARGE_ENDTIME_THURSDAY, use_default
            ): TIME_ENTITY_SELECTOR,
            self._optional(
                subentry, TIME_CHARGE_ENDTIME_FRIDAY, use_default
            ): TIME_ENTITY_SELECTOR,
            self._optional(
                subentry, TIME_CHARGE_ENDTIME_SATURDAY, use_default
            ): TIME_ENTITY_SELECTOR,
            self._optional(
                subentry, TIME_CHARGE_ENDTIME_SUNDAY, use_default
            ): TIME_ENTITY_SELECTOR,
            #####################################
            # Sunrise/sunset triggers
            #####################################
            self._optional(
                subentry, NUMBER_SUNRISE_ELEVATION_START_TRIGGER, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_SUNSET_ELEVATION_END_TRIGGER, use_default
            ): NUMBER_ENTITY_SELECTOR,
            #####################################
            # Wait times
            #####################################
            self._optional(
                subentry, NUMBER_WAIT_CHARGEE_WAKEUP, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_WAIT_CHARGEE_UPDATE_HA, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_WAIT_CHARGEE_LIMIT_CHANGE, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_WAIT_CHARGER_ON, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_WAIT_CHARGER_OFF, use_default
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, NUMBER_WAIT_CHARGER_AMP_CHANGE, use_default
            ): NUMBER_ENTITY_SELECTOR,
        }

    # ----------------------------------------------------------------------------
    # TODO: Create dynamic list base on sensor, number, etc., otherwise it is text selector.

    def _charger_device_control_schema(
        self, subentry: ConfigSubentry, use_default: bool
    ) -> dict[Any, Any]:
        """Charger control entities."""
        api_entities: dict[str, str | None] | None = get_device_api_entities(subentry)

        return {
            #####################################
            # Charge environment
            #####################################
            self._optional(
                subentry, NUMBER_CHARGER_MAX_SPEED, use_default
            ): choose_selector(
                api_entities,
                NUMBER_CHARGER_MAX_SPEED,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
                modifiable_if_local_config_entity=True,
            ),
            self._optional(
                subentry, NUMBER_CHARGER_MIN_CURRENT, use_default
            ): choose_selector(
                api_entities,
                NUMBER_CHARGER_MIN_CURRENT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
                modifiable_if_local_config_entity=True,
            ),
            self._optional(
                subentry, NUMBER_CHARGER_MIN_WORKABLE_CURRENT, use_default
            ): choose_selector(
                api_entities,
                NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT, use_default
            ): choose_selector(
                api_entities,
                NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, NUMBER_CHARGER_ALLOCATED_POWER, use_default
            ): choose_selector(
                api_entities,
                NUMBER_CHARGER_ALLOCATED_POWER,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, NUMBER_CHARGEE_MIN_CHARGE_LIMIT, use_default
            ): choose_selector(
                api_entities,
                NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, NUMBER_CHARGEE_MAX_CHARGE_LIMIT, use_default
            ): choose_selector(
                api_entities,
                NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            #####################################
            # Local device entities
            #####################################
            self._optional(subentry, OPTION_CHARGER_NAME, use_default): choose_selector(
                None,
                OPTION_CHARGER_NAME,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_PLUGGED_IN_SENSOR, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_PLUGGED_IN_SENSOR,
                SENSOR_ENTITY_SELECTOR_READ_ONLY,
                SENSOR_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CONNECT_TRIGGER_LIST, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_CONNECT_TRIGGER_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CONNECT_STATE_LIST, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_CONNECT_STATE_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_ON_OFF_SWITCH, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_ON_OFF_SWITCH,
                SWITCH_ENTITY_SELECTOR_READ_ONLY,
                SWITCH_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CHARGING_SENSOR, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_CHARGING_SENSOR,
                SENSOR_ENTITY_SELECTOR_READ_ONLY,
                SENSOR_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_CHARGING_STATE_LIST, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_CHARGING_STATE_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_MAX_CURRENT, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_MAX_CURRENT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
                modifiable_if_local_config_entity=True,
            ),
            self._optional(
                subentry, OPTION_CHARGER_GET_CHARGE_CURRENT, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_GET_CHARGE_CURRENT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGER_SET_CHARGE_CURRENT, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGER_SET_CHARGE_CURRENT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_SOC_SENSOR, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGEE_SOC_SENSOR,
                SENSOR_ENTITY_SELECTOR_READ_ONLY,
                SENSOR_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_CHARGE_LIMIT, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGEE_CHARGE_LIMIT,
                NUMBER_ENTITY_SELECTOR_READ_ONLY,
                NUMBER_ENTITY_SELECTOR,
                modifiable_if_local_config_entity=True,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_LOCATION_SENSOR, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGEE_LOCATION_SENSOR,
                LOCATION_ENTITY_SELECTOR_READ_ONLY,
                LOCATION_ENTITY_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_LOCATION_STATE_LIST, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGEE_LOCATION_STATE_LIST,
                TEXT_SELECTOR_READ_ONLY,
                TEXT_SELECTOR,
            ),
            self._optional(
                subentry, OPTION_CHARGEE_WAKE_UP_BUTTON, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGEE_WAKE_UP_BUTTON,
                BUTTON_ENTITY_SELECTOR_READ_ONLY,
                BUTTON_ENTITY_SELECTOR,
            ),
            # Turning on force HA update switch will override the in-built update HA button.
            self._optional(
                subentry, OPTION_CHARGEE_UPDATE_HA_BUTTON, use_default
            ): choose_selector(
                api_entities,
                OPTION_CHARGEE_UPDATE_HA_BUTTON,
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

        return reset_api_entities(self.config_entry, config_name, data)

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
            general_schema = self._charger_environment_schema(
                subentry, use_default=True
            )
            combine_schema = {**general_schema}
        else:
            general_schema = self._charger_environment_schema(
                subentry, use_default=False
            )
            entities_schema = self._charger_device_control_schema(
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
            if subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
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
