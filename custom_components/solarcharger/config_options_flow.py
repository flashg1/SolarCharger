"""Config flow for the solarcharger integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
)

from .exceptions.validation_exception import ValidationExceptionError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
OPTION_NET_POWER = "net_power"

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

OPTION_TESLACUSTOM_NAME = "tesla_custom_name"
DEFAULT_TESLACUSTOM_NAME = ""

STEP_TESLACUSTOM_SCHEMA = vol.Schema(
    {
        vol.Required(OPTION_TESLACUSTOM_NAME, default=DEFAULT_TESLACUSTOM_NAME): str,
    }
)


DEFAULT_VALUES: dict[str, Any] = {
    OPTION_CHARGER_MAX_CURRENT: 15,
    OPTION_CHARGER_MAX_SPEED: 6.1448,
    OPTION_CHARGER_MIN_CURRENT: 1,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT: 0,
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT: 1,
    OPTION_WAIT_NET_POWER_UPDATE: 60,
    OPTION_WAIT_CHARGER_UPDATE: 5,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER: 3,
    OPTION_SUNSET_ELEVATION_END_TRIGGER: 6,
    OPTION_TESLACUSTOM_NAME: "",
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
# ----------------------------------------------------------------------------
class ConfigOptionsFlowHandler(OptionsFlow):
    """Handle an options flow for solarcharger."""

    def __init__(self, config_entry: ConfigEntry | None = None) -> None:
        """Initialize options flow.

        @see https://developers.home-assistant.io/blog/2024/11/12/options-flow/
        """
        if config_entry is not None:
            self.config_entry = config_entry

    @staticmethod
    def get_option_value(config_entry: ConfigEntry, key: str) -> Any:
        """Get the value of an option from the config entry."""
        return config_entry.options.get(key, DEFAULT_VALUES.get(key))

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
                        DEFAULT_VALUES[OPTION_CHARGER_MAX_CURRENT],
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
                        DEFAULT_VALUES[OPTION_CHARGER_MIN_WORKABLE_CURRENT],
                    ),
                ): NumberSelector(
                    {"min": 0, "max": 100, "mode": "box", "unit_of_measurement": "A"}
                ),
                vol.Optional(
                    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
                    default=options_values.get(
                        OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
                        DEFAULT_VALUES[OPTION_CHARGER_POWER_ALLOCATION_WEIGHT],
                    ),
                ): NumberSelector({"min": 1, "max": 100, "mode": "box"}),
                vol.Optional(
                    OPTION_WAIT_NET_POWER_UPDATE,
                    default=options_values.get(
                        OPTION_WAIT_NET_POWER_UPDATE,
                        DEFAULT_VALUES[OPTION_WAIT_NET_POWER_UPDATE],
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
                        DEFAULT_VALUES[OPTION_WAIT_CHARGER_UPDATE],
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
                        DEFAULT_VALUES[OPTION_SUNRISE_ELEVATION_START_TRIGGER],
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
                        DEFAULT_VALUES[OPTION_SUNSET_ELEVATION_END_TRIGGER],
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
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        input_data: dict[str, Any] | None = None

        if user_input is not None:
            try:
                input_data = await validate_init_input(self.hass, user_input)

            except ValidationExceptionError as ex:
                errors[ex.base] = ex.key
            except ValueError:
                errors["base"] = "invalid_number_format"

            if not errors and input_data is not None:
                return self.async_create_entry(title="", data=input_data)

        return self.async_show_form(
            step_id="init", data_schema=self._options_schema(), errors=errors
        )
