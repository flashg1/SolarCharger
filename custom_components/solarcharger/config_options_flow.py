"""Config flow for the solarcharger integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import all_
import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentry,
    OptionsFlow,
)
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TemplateSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    selector,
)
from homeassistant.util import slugify

from . import config_subentry_flow as csef
from .config_subentry_flow import SUBENTRY_DEVICE_DOMAIN, SUBENTRY_DEVICE_NAME
from .const import CHARGER_DOMAIN_OCPP, CHARGER_DOMAIN_TESLA_CUSTOM
from .exceptions.validation_exception import ValidationExceptionError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


#####################################
# Common selectors
#####################################
BOOLEAN_SELECTOR = BooleanSelector()
TEMPLATE_SELECTOR = TemplateSelector(TemplateSelectorConfig())
TEMPLATE_SELECTOR_READ_ONLY = TemplateSelector(TemplateSelectorConfig(read_only=True))
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
TEXT_SELECTOR_READ_ONLY = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, read_only=True)
)
OPTIONS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[],
        custom_value=True,
        multiple=True,
    )
)
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))

TARGET_TEMPERATURE_FEATURE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["single", "high_low", "none"],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="target_temperature_feature",
    )
)

NUMBER_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["number", "input_number", "sensor"],
    )
)
SENSOR_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["sensor", "binary_sensor"],
    )
)
SWITCH_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["switch"],
    )
)
BUTTON_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["button"],
    )
)
LOCATION_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["device_tracker", "binary_sensor"],
    )
)


ELECTRIC_CURRENT_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=0, max=100, unit_of_measurement="A"
    )
)
WAIT_TIME_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=1, max=600, unit_of_measurement="sec"
    )
)
SUN_ELEVATION_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=-90, max=+90, unit_of_measurement="degree"
    )
)
ALLOCATION_WEIGHT_SELECTOR = NumberSelector(
    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=100)
)

#####################################
# Power import/export sensor
#####################################
OPTION_NET_POWER = "net_power"

OPTION_SELECT_CHARGER = "select_charger"
OPTION_LAST_CHARGER_ID = "last_charger_id"

#####################################
# Option admin
#####################################
OPTION_ID = "option_id"
OPTION_NAME = "option_name"

#####################################
# Charger general configs
#####################################
OPTION_CHARGER_EFFECTIVE_VOLTAGE = "charger_effective_voltage"
OPTION_CHARGER_MAX_CURRENT = "charger_max_current"
OPTION_CHARGER_MAX_SPEED = "charger_max_speed"
OPTION_CHARGER_MIN_CURRENT = "charger_min_current"
OPTION_CHARGER_MIN_WORKABLE_CURRENT = "charger_min_workable_current"
OPTION_CHARGER_POWER_ALLOCATION_WEIGHT = "charger_power_allocation_weight"

OPTION_WAIT_NET_POWER_UPDATE = "wait_net_power_update"
OPTION_WAIT_CHARGER_UPDATE = "wait_charger_update"

OPTION_SUNRISE_ELEVATION_START_TRIGGER = "sunrise_elevation_start_trigger"
OPTION_SUNSET_ELEVATION_END_TRIGGER = "sunset_elevation_end_trigger"

#####################################
# Charger control entities
#####################################
OPTION_CHARGER_DEVICE_NAME = "charger_device_name"
OPTION_CHARGER_PLUGGED_IN_SENSOR = "charger_plugged_in_sensor"
OPTION_CHARGER_CONNECT_TRIGGER_LIST = "charger_connect_trigger_list"
OPTION_CHARGER_CONNECT_STATE_LIST = "charger_connect_state_list"
OPTION_CHARGER_ON_OFF_SWITCH = "charger_on_off_switch"
OPTION_CHARGER_CHARGING_SENSOR = "charger_charging_sensor"
OPTION_CHARGER_CHARGING_STATE_LIST = "charger_charging_state_list"
OPTION_CHARGER_CHARGING_AMPS = "charger_charging_amps"

#####################################
# Chargee control entities
#####################################
OPTION_CHARGEE_SOC_SENSOR = "chargee_soc_sensor"
OPTION_CHARGEE_CHARGE_LIMIT = "chargee_charge_limit"
OPTION_CHARGEE_LOCATION_SENSOR = "chargee_location_sensor"
OPTION_CHARGEE_LOCATION_STATE_LIST = "chargee_location_state_list"
OPTION_CHARGEE_WAKE_UP_BUTTON = "chargee_wake_up_button"
OPTION_CHARGEE_UPDATE_HA_BUTTON = "chargee_update_ha_button"

#####################################
# Charger specific configs
#####################################
# OPTION_TESLACUSTOM_NAME = "tesla_custom_name"
# DEFAULT_TESLACUSTOM_NAME = ""

# OPTION_OCPPCHARGER_NAME = "ocpp_custom_name"
# DEFAULT_OCPPCHARGER_NAME = "charger"

#####################################
# Default values
#####################################
OPTION_DEFAULT_VALUES: dict[str, Any] = {
    OPTION_CHARGER_EFFECTIVE_VOLTAGE: None,
    OPTION_CHARGER_MAX_CURRENT: 15,
    OPTION_CHARGER_MAX_SPEED: 6.1448,
    OPTION_CHARGER_MIN_CURRENT: 1,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT: 0,
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT: 1,
    OPTION_WAIT_NET_POWER_UPDATE: 60,
    OPTION_WAIT_CHARGER_UPDATE: 5,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER: 3,
    OPTION_SUNSET_ELEVATION_END_TRIGGER: 6,
    # OPTION_TESLACUSTOM_NAME: DEFAULT_TESLACUSTOM_NAME,
    # OPTION_OCPPCHARGER_NAME: DEFAULT_OCPPCHARGER_NAME,
}

# STEP_TESLACUSTOM_SCHEMA = vol.Schema(
#     {
#         vol.Required(OPTION_TESLACUSTOM_NAME, default=DEFAULT_TESLACUSTOM_NAME): str,
#     }
# )

DEVICE_MARKER = "<DeviceName>"

TESLA_CUSTOM_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_DEVICE_NAME: DEVICE_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"binary_sensor.{DEVICE_MARKER}charger",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: "['on']",
    OPTION_CHARGER_CONNECT_STATE_LIST: "['on']",
    OPTION_CHARGER_ON_OFF_SWITCH: f"switch.{DEVICE_MARKER}charger",
    OPTION_CHARGER_CHARGING_SENSOR: f"binary_sensor.{DEVICE_MARKER}charging",
    OPTION_CHARGER_CHARGING_STATE_LIST: "['on']",
    OPTION_CHARGER_CHARGING_AMPS: f"number.{DEVICE_MARKER}charging_amps",
    OPTION_CHARGEE_SOC_SENSOR: f"sensor.{DEVICE_MARKER}battery",
    OPTION_CHARGEE_CHARGE_LIMIT: f"number.{DEVICE_MARKER}charge_limit",
    OPTION_CHARGEE_LOCATION_SENSOR: f"device_tracker.{DEVICE_MARKER}location_tracker",
    OPTION_CHARGEE_LOCATION_STATE_LIST: "['home']",
    OPTION_CHARGEE_WAKE_UP_BUTTON: f"button.{DEVICE_MARKER}wake_up",
    OPTION_CHARGEE_UPDATE_HA_BUTTON: f"button.{DEVICE_MARKER}force_data_update",
}

OCPP_CHARGER_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_DEVICE_NAME: "charger",
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"sensor.{DEVICE_MARKER}status_connector",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: "['Preparing']",
    OPTION_CHARGER_CONNECT_STATE_LIST: "['Preparing', 'Charging', 'SuspendedEV', 'SuspendedEVSE', 'Finishing']",
    OPTION_CHARGER_ON_OFF_SWITCH: f"switch.{DEVICE_MARKER}charge_control",
    OPTION_CHARGER_CHARGING_SENSOR: f"sensor.{DEVICE_MARKER}status_connector",
    OPTION_CHARGER_CHARGING_STATE_LIST: "['Charging', 'SuspendedEV', 'SuspendedEVSE']",
    OPTION_CHARGER_CHARGING_AMPS: f"sensor.{DEVICE_MARKER}current_import",
    OPTION_CHARGEE_SOC_SENSOR: None,
    OPTION_CHARGEE_CHARGE_LIMIT: None,
    OPTION_CHARGEE_LOCATION_SENSOR: None,
    OPTION_CHARGEE_LOCATION_STATE_LIST: None,
    OPTION_CHARGEE_WAKE_UP_BUTTON: None,
    OPTION_CHARGEE_UPDATE_HA_BUTTON: None,
}

CHARGE_API_ENTITIES: dict[str, dict[str, str | None]] = {
    CHARGER_DOMAIN_TESLA_CUSTOM: TESLA_CUSTOM_ENTITIES,
    CHARGER_DOMAIN_OCPP: OCPP_CHARGER_ENTITIES,
}


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def validate_init_input(
    _hass: HomeAssistant,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Validate the input data for the options flow."""
    return data


# ----------------------------------------------------------------------------
def get_config_item_name(device_name, config_item) -> str:
    """Get unique config parameter name."""
    # return f"{device_name}-{config_item}"
    return config_item


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ConfigOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for solarcharger."""

    def __init__(self, config_entry: ConfigEntry | None = None) -> None:
        """Initialize options flow.

        @see https://developers.home-assistant.io/blog/2024/11/12/options-flow/
        """
        if config_entry is not None:
            self.config_entry = config_entry

    # ----------------------------------------------------------------------------
    @staticmethod
    def get_option_value(config_entry: ConfigEntry, key: str) -> Any:
        """Get the value of an option from the config entry."""
        return config_entry.options.get(key, OPTION_DEFAULT_VALUES.get(key))

    # ----------------------------------------------------------------------------
    def _get_device_id(self, device_name: str) -> str | None:
        subentry_id: str | None = None

        if self.config_entry.subentries:
            for subentry in self.config_entry.subentries.values():
                if subentry.subentry_type == csef.SUBENTRY_TYPE_CHARGER:
                    if subentry.unique_id == device_name:
                        subentry_id = subentry.subentry_id
                        break

        return subentry_id

    # ----------------------------------------------------------------------------
    def _get_default_entity(
        self,
        defaults: dict[str, str | None] | None,
        config_item: str,
        substr: str | None,
    ) -> str | None:
        """Get default value from dictionary with substition."""
        default_val: Any | None = None

        if substr:
            if defaults:
                default_val = defaults.get(config_item)
                if default_val:
                    if default_val == DEVICE_MARKER:
                        default_val = substr
                    else:
                        default_val = default_val.replace(DEVICE_MARKER, f"{substr}_")

        return default_val

    # ----------------------------------------------------------------------------
    def _get_default_value(
        self, subentry: ConfigSubentry, config_item: str
    ) -> Any | None:
        """Get default value for config item."""

        # Get parameter default value
        default_val = OPTION_DEFAULT_VALUES.get(config_item)

        # Get entity name
        if not default_val:
            if subentry:
                device_domain = subentry.data.get(SUBENTRY_DEVICE_DOMAIN)
                device_name_default = subentry.data.get(SUBENTRY_DEVICE_NAME)
                device_name_default = slugify(device_name_default)

                if device_domain:
                    api_entities = CHARGE_API_ENTITIES.get(device_domain)

                    if api_entities:
                        device_options = self.config_entry.options.get(
                            subentry.subentry_id
                        )
                        if device_options:
                            # Get device name for substitution
                            device_name = device_options.get(
                                OPTION_CHARGER_DEVICE_NAME, device_name_default
                            )
                            default_val = self._get_default_entity(
                                api_entities,
                                config_item,
                                device_name,
                            )

            # match device_domain:
            #     case const.CHARGER_DOMAIN_TESLA_CUSTOM:
            #         device_name = options.get(
            #             OPTION_CHARGER_DEVICE_NAME, DEFAULT_TESLACUSTOM_NAME
            #         )
            #         default = self._get_default_entity(
            #             CHARGE_API_ENTITIES.get(device_domain),
            #             config_item,
            #             device_name,
            #         )
            #     case const.CHARGER_DOMAIN_OCPP:
            #         device_name = options.get(
            #             OPTION_OCPPCHARGER_NAME, DEFAULT_OCPPCHARGER_NAME
            #         )
            #         default = self._get_default_entity(
            #             CHARGE_API_ENTITIES.get(device_domain),
            #             config_item,
            #             device_name,
            #         )
            #     case _:
            #         default = None

        return default_val

    # ----------------------------------------------------------------------------
    def _get_option_parameters(
        self, subentry: ConfigSubentry, config_item: str
    ) -> tuple[str, Any]:
        options = self.config_entry.options

        unique_config_item = get_config_item_name(subentry.unique_id, config_item)
        default_val = self._get_default_value(subentry, config_item)

        device_options = options.get(subentry.subentry_id)
        if device_options:
            default_final = device_options.get(unique_config_item, default_val)
        else:
            default_final = default_val

        _LOGGER.debug(
            "Required option=%s, default=%s, final=%s",
            unique_config_item,
            default_val,
            default_final,
        )

        return unique_config_item, default_final

    # ----------------------------------------------------------------------------
    def _required(self, subentry: ConfigSubentry, config_item: str) -> vol.Required:
        unique_config_item, default_final = self._get_option_parameters(
            subentry, config_item
        )
        return vol.Required(unique_config_item, default=default_final)

    # ----------------------------------------------------------------------------
    def _optional(self, subentry: ConfigSubentry, config_item: str) -> vol.Optional:
        unique_config_item, default_final = self._get_option_parameters(
            subentry, config_item
        )
        return vol.Optional(unique_config_item, default=default_final)

    # ----------------------------------------------------------------------------
    def _charger_general_options_schema(
        self, subentry: ConfigSubentry
    ) -> dict[Any, Any]:
        """Charger general options."""

        return {
            self._required(
                subentry, OPTION_CHARGER_EFFECTIVE_VOLTAGE
            ): NUMBER_ENTITY_SELECTOR,
            self._required(
                subentry, OPTION_CHARGER_MAX_CURRENT
            ): ELECTRIC_CURRENT_SELECTOR,
            self._optional(subentry, OPTION_CHARGER_MAX_SPEED): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_MIN_CURRENT
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_MIN_WORKABLE_CURRENT
            ): ELECTRIC_CURRENT_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_POWER_ALLOCATION_WEIGHT
            ): ALLOCATION_WEIGHT_SELECTOR,
            self._optional(subentry, OPTION_WAIT_NET_POWER_UPDATE): WAIT_TIME_SELECTOR,
            self._optional(subentry, OPTION_WAIT_CHARGER_UPDATE): WAIT_TIME_SELECTOR,
            self._optional(
                subentry, OPTION_SUNRISE_ELEVATION_START_TRIGGER
            ): SUN_ELEVATION_SELECTOR,
            self._optional(
                subentry, OPTION_SUNSET_ELEVATION_END_TRIGGER
            ): SUN_ELEVATION_SELECTOR,
        }

    # ----------------------------------------------------------------------------
    def _charger_control_entities_schema(
        self, subentry: ConfigSubentry
    ) -> dict[Any, Any]:
        """Charger control entities."""

        return {
            self._optional(subentry, OPTION_CHARGER_DEVICE_NAME): TEXT_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_PLUGGED_IN_SENSOR
            ): SENSOR_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_CONNECT_TRIGGER_LIST
            ): SENSOR_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_CONNECT_STATE_LIST
            ): SENSOR_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_ON_OFF_SWITCH
            ): SWITCH_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_CHARGING_SENSOR
            ): SENSOR_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_CHARGING_STATE_LIST
            ): SENSOR_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGER_CHARGING_AMPS
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(subentry, OPTION_CHARGEE_SOC_SENSOR): SENSOR_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGEE_CHARGE_LIMIT
            ): NUMBER_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGEE_LOCATION_SENSOR
            ): LOCATION_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGEE_LOCATION_STATE_LIST
            ): SENSOR_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGEE_WAKE_UP_BUTTON
            ): BUTTON_ENTITY_SELECTOR,
            self._optional(
                subentry, OPTION_CHARGEE_UPDATE_HA_BUTTON
            ): BUTTON_ENTITY_SELECTOR,
        }

    # ----------------------------------------------------------------------------
    def _options_schema(self) -> vol.Schema:
        """Define the schema for the options flow."""
        options_values = self.config_entry.options

        return vol.Schema(
            {
                vol.Required(
                    OPTION_NET_POWER, default=options_values.get(OPTION_NET_POWER, None)
                ): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False,
                        domain="sensor",
                        device_class=[SensorDeviceClass.POWER],
                    )
                ),
                vol.Required(
                    OPTION_CHARGER_EFFECTIVE_VOLTAGE,
                    default=options_values.get(OPTION_CHARGER_EFFECTIVE_VOLTAGE, None),
                ): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False,
                        domain=["sensor", "input_number"],
                    )
                ),
                vol.Required(
                    OPTION_CHARGER_MAX_CURRENT,
                    default=options_values.get(
                        OPTION_CHARGER_MAX_CURRENT,
                        OPTION_DEFAULT_VALUES[OPTION_CHARGER_MAX_CURRENT],
                    ),
                ): NumberSelector(
                    {"min": 1, "max": 100, "mode": "box", "unit_of_measurement": "A"}
                ),
                vol.Optional(
                    OPTION_CHARGER_MAX_SPEED,
                    default=options_values.get(OPTION_CHARGER_MAX_SPEED, None),
                ): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False,
                        domain=["input_number", "number", "sensor"],
                    )
                ),
                vol.Optional(
                    OPTION_CHARGER_MIN_CURRENT,
                    default=options_values.get(OPTION_CHARGER_MIN_CURRENT, None),
                ): EntitySelector(
                    EntitySelectorConfig(
                        multiple=False,
                        domain=["input_number", "number", "sensor"],
                    )
                ),
                vol.Optional(
                    OPTION_CHARGER_MIN_WORKABLE_CURRENT,
                    default=options_values.get(
                        OPTION_CHARGER_MIN_WORKABLE_CURRENT,
                        OPTION_DEFAULT_VALUES[OPTION_CHARGER_MIN_WORKABLE_CURRENT],
                    ),
                ): NumberSelector(
                    {"min": 0, "max": 100, "mode": "box", "unit_of_measurement": "A"}
                ),
                vol.Optional(
                    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
                    default=options_values.get(
                        OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
                        OPTION_DEFAULT_VALUES[OPTION_CHARGER_POWER_ALLOCATION_WEIGHT],
                    ),
                ): NumberSelector({"min": 1, "max": 100, "mode": "box"}),
                vol.Optional(
                    OPTION_WAIT_NET_POWER_UPDATE,
                    default=options_values.get(
                        OPTION_WAIT_NET_POWER_UPDATE,
                        OPTION_DEFAULT_VALUES[OPTION_WAIT_NET_POWER_UPDATE],
                    ),
                ): NumberSelector(
                    {
                        "min": 1,
                        "max": 600,
                        "mode": "box",
                        "unit_of_measurement": "second",
                    }
                ),
                vol.Optional(
                    OPTION_WAIT_CHARGER_UPDATE,
                    default=options_values.get(
                        OPTION_WAIT_CHARGER_UPDATE,
                        OPTION_DEFAULT_VALUES[OPTION_WAIT_CHARGER_UPDATE],
                    ),
                ): NumberSelector(
                    {
                        "min": 1,
                        "max": 600,
                        "mode": "box",
                        "unit_of_measurement": "second",
                    }
                ),
                vol.Optional(
                    OPTION_SUNRISE_ELEVATION_START_TRIGGER,
                    default=options_values.get(
                        OPTION_SUNRISE_ELEVATION_START_TRIGGER,
                        OPTION_DEFAULT_VALUES[OPTION_SUNRISE_ELEVATION_START_TRIGGER],
                    ),
                ): NumberSelector(
                    {
                        "min": -90,
                        "max": +90,
                        "mode": "box",
                        "unit_of_measurement": "degree",
                    }
                ),
                vol.Optional(
                    OPTION_SUNSET_ELEVATION_END_TRIGGER,
                    default=options_values.get(
                        OPTION_SUNSET_ELEVATION_END_TRIGGER,
                        OPTION_DEFAULT_VALUES[OPTION_SUNSET_ELEVATION_END_TRIGGER],
                    ),
                ): NumberSelector(
                    {
                        "min": -90,
                        "max": +90,
                        "mode": "box",
                        "unit_of_measurement": "degree",
                    }
                ),
            }
        )

    # ----------------------------------------------------------------------------
    def _all_charger_options_schema(self, errors) -> vol.Schema:
        all_schema = None

        for subentry in self.config_entry.subentries.values():
            if subentry.subentry_type == csef.SUBENTRY_TYPE_CHARGER:
                if subentry.unique_id:
                    _LOGGER.debug(
                        "Set up subentry options: unique_id=%s, subentry_id=%s, subentry_type=%s, title=%s",
                        subentry.unique_id,
                        subentry.subentry_id,
                        subentry.subentry_type,
                        subentry.title,
                    )

                    general_schema = self._charger_general_options_schema(subentry)
                    entities_schema = self._charger_control_entities_schema(subentry)
                    combine_schema = {**general_schema, **entities_schema}
                    charger_schema = {
                        vol.Required(subentry.unique_id): section(
                            vol.Schema(combine_schema), {"collapsed": True}
                        ),
                    }
                    if all_schema:
                        all_schema = {**all_schema, **charger_schema}
                    else:
                        all_schema = charger_schema

        return vol.Schema(all_schema)

    # ----------------------------------------------------------------------------
    async def async_step_config_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select charger device to configure."""
        errors = {}
        options_config: dict[str, Any] = dict(self.config_entry.options)
        input_data = None
        combine_schema = {}

        device_name = self._device_to_update
        subentry_id = self._get_device_id(device_name)

        # Process options
        if user_input is not None:
            if subentry_id:
                # validate input
                try:
                    input_data = await validate_init_input(self.hass, user_input)
                except ValidationExceptionError as ex:
                    errors[ex.base] = ex.key
                except ValueError:
                    errors["base"] = "invalid_number_format"

                if not errors and input_data is not None:
                    device_options = options_config.get(subentry_id)
                    if not device_options:
                        device_options = {}
                        device_options[OPTION_ID] = subentry_id
                        device_options[OPTION_NAME] = device_name
                        options_config[subentry_id] = device_options

                    device_options.update(input_data)

                    return self.async_create_entry(data=options_config)

        # Prompt user for options
        if subentry_id:
            subentry = self.config_entry.subentries.get(subentry_id)
            if not subentry:
                errors["subentry_not_found"] = f"Subentry not found for {device_name}"
                return self.async_abort(
                    reason="subentry_not_found",
                )

            general_schema = self._charger_general_options_schema(subentry)
            entities_schema = self._charger_control_entities_schema(subentry)
            combine_schema = {**general_schema, **entities_schema}
            # charger_schema = {
            #     vol.Required(subentry.unique_id): section(
            #         vol.Schema(combine_schema), {"collapsed": False}
            #     ),
            # }

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
            self._device_to_update = user_input[OPTION_SELECT_CHARGER]
            return await self.async_step_config_device(None)

        if not self.config_entry.subentries:
            errors["empty_charger_device_list"] = "Use + sign to add charger devices."
            return self.async_abort(
                reason="empty_charger_device_list",
            )

        device_list = []
        for subentry in self.config_entry.subentries.values():
            if subentry.subentry_type == csef.SUBENTRY_TYPE_CHARGER:
                if subentry.unique_id:
                    device_list.append(subentry.unique_id)

        fields = {}
        fields[vol.Required(OPTION_SELECT_CHARGER)] = SelectSelector(
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

    # ----------------------------------------------------------------------------
    # async def async_step_init(
    #     self, user_input: dict[str, Any] | None = None
    # ) -> ConfigFlowResult:
    #     """Handle the initial step."""
    #     errors: dict[str, str] = {}
    #     input_data: dict[str, Any] | None = None

    #     if user_input is not None:
    #         try:
    #             input_data = await validate_init_input(self.hass, user_input)

    #         except ValidationExceptionError as ex:
    #             errors[ex.base] = ex.key
    #         except ValueError:
    #             errors["base"] = "invalid_number_format"

    #         if not errors and input_data is not None:
    #             return self.async_create_entry(title="", data=input_data)

    #     if not self.config_entry.subentries:
    #         errors["empty_charger_device_list"] = "Use + sign to add charger devices."
    #         return self.async_abort(
    #             reason="empty_charger_device_list",
    #         )

    #     return self.async_show_form(
    #         step_id="init",
    #         data_schema=self._all_charger_options_schema(errors),
    #         errors=errors,
    #     )
