"""Constants for the Solar Charger integration."""

from enum import Enum
from typing import Any

from homeassistant.const import Platform, __version__ as HA_VERSION

MANUFACTURER = "FlashG"
NAME = "Solar Charger"
DOMAIN = "solarcharger"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.1beta1"
ISSUE_URL = "https://github.com/flashg1/SolarCharger/issues"
CONFIG_URL = "https://github.com/flashg1/SolarCharger"

TRANSLATION_KEY_PREFIX = f"{DOMAIN}"

# Icons
ICON = "mdi:flash"
ICON_BATTERY_50 = "mdi:battery-50"
ICON_CASH = "mdi:cash"
ICON_CONNECTION = "mdi:connection"
ICON_MIN_SOC = "mdi:battery-charging-30"
ICON_START = "mdi:play-circle-outline"
ICON_STOP = "mdi:stop-circle-outline"
ICON_TIME = "mdi:clock-time-four-outline"
ICON_TIMER = "mdi:camera-timer"
ICON_POWER = "mdi:power"

# Platforms
SENSOR = Platform.SENSOR
SWITCH = Platform.SWITCH
BUTTON = Platform.BUTTON
NUMBER = Platform.NUMBER
SELECT = Platform.SELECT
PLATFORMS = [BUTTON, NUMBER, SELECT, SENSOR, SWITCH]
PLATFORM_OCPP = "ocpp"
PLATFORM_USER_CUSTOM = "user_custom"
CHARGER_DOMAIN_OCPP = "ocpp"
CHARGER_DOMAIN_TESLA_CUSTOM = "tesla_custom"

#######################################################
# Make sure the entity key names are unique.
#######################################################
# Sensors
ENTITY_KEY_LAST_CHECK_SENSOR = "last_check"
ENTITY_KEY_RUN_STATE_SENSOR = "run_state"

# Numbers
ENTITY_KEY_CHARGEE_CHARGE_LIMIT = "chargee_charge_limit"

# Switches
ENTITY_KEY_CHARGE_SWITCH = "charge"

# Buttons
ENTITY_KEY_CHARGE_BUTTON = "start_charge"

#######################################################
# Make sure the entity key names are unique.
#######################################################

COORDINATOR_STATE_STOPPED = "stopped"
COORDINATOR_STATE_CHARGING = "charging"
COORDINATOR_STATES: tuple[str, ...] = (
    COORDINATOR_STATE_STOPPED,
    COORDINATOR_STATE_CHARGING,
)

# Event constants
SOLAR_CHARGER_COORDINATOR_EVENT = f"{DOMAIN}_coordinator_event"
EVENT_ACTION_NEW_CHARGER_LIMITS = "new_charger_limits"
EVENT_ATTR_ACTION = "action"
EVENT_ATTR_NEW_LIMITS = "new_limits"

#######################################################
# Subentry constants
#######################################################
SUBENTRY_TYPE_CHARGER = "charger"
SUBENTRY_THIRDPARTY_DOMAIN = "thirdparty_domain"
SUBENTRY_THIRDPARTY_DEVICE_NAME = "thirdparty_device_name"
SUBENTRY_THIRDPARTY_DEVICE_ID = "thirdparty_device_id"

SUBENTRY_TYPE_DEFAULTS = "defaults"

#######################################################
# Option constants
#######################################################

#####################################
# Power import/export sensor
#####################################
CONF_NET_POWER = "net_power"

OPTION_SELECT_SETTINGS = "select_global_or_local_settings"
OPTION_LAST_CHARGER_ID = "last_charger_id"

#####################################
# Internal entities
#####################################
CONTROL_CHARGER_ALLOCATED_POWER = "charger_allocated_power"

#####################################
# Option admin
#####################################
OPTION_GLOBAL_DEFAULTS_ID = "Global defaults"
CONFIG_NAME_GLOBAL_DEFAULTS = "global_defaults"
OPTION_ID = "option_id"
OPTION_NAME = "option_name"

#####################################
# Charger general configs
#####################################
OPTION_CHARGER_EFFECTIVE_VOLTAGE = "charger_effective_voltage"  # 230 Volts
OPTION_CHARGER_MAX_CURRENT = "charger_max_current"  # 15 Amps
OPTION_CHARGER_MAX_SPEED = "charger_max_speed"  # 6.1448 %/hr
OPTION_CHARGER_MIN_CURRENT = "charger_min_current"  # 1 Amps
OPTION_CHARGER_MIN_WORKABLE_CURRENT = "charger_min_workable_current"  # 0 Amps
OPTION_CHARGER_POWER_ALLOCATION_WEIGHT = "charger_power_allocation_weight"  # 1

OPTION_SUNRISE_ELEVATION_START_TRIGGER = "sunrise_elevation_start_trigger"  # 3
OPTION_SUNSET_ELEVATION_END_TRIGGER = "sunset_elevation_end_trigger"  # 6

# Wait times
OPTION_WAIT_NET_POWER_UPDATE = "wait_net_power_update"  # 60 seconds
OPTION_WAIT_CHARGEE_WAKEUP = "wait_chargee_wakeup"  # 40 seconds
OPTION_WAIT_CHARGEE_UPDATE_HA = "wait_chargee_update_ha"  # 5 seconds
OPTION_WAIT_CHARGEE_LIMIT_CHANGE = "wait_chargee_limit_change"  # 5 seconds
OPTION_WAIT_CHARGER_ON = "wait_charger_on"  # 11 seconds
OPTION_WAIT_CHARGER_OFF = "wait_charger_off"  # 5 seconds
OPTION_WAIT_CHARGER_AMP_CHANGE = "wait_charger_amp_change"  # 1 second

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
OPTION_CHARGER_GET_CHARGE_CURRENT = "charger_get_charge_current"
OPTION_CHARGER_SET_CHARGE_CURRENT = "charger_set_charge_current"

#####################################
# Chargee control entities
#####################################
OPTION_CHARGEE_SOC_SENSOR = "chargee_soc_sensor"
OPTION_CHARGEE_CHARGE_LIMIT = "chargee_charge_limit"
OPTION_CHARGEE_LOCATION_SENSOR = "chargee_location_sensor"
OPTION_CHARGEE_LOCATION_STATE_LIST = "chargee_location_state_list"
OPTION_CHARGEE_WAKE_UP_BUTTON = "chargee_wake_up_button"
OPTION_CHARGEE_UPDATE_HA_BUTTON = "chargee_update_ha_button"

#######################################################
# Lists
#######################################################
# Global default entities
OPTION_GLOBAL_DEFAULT_ENTITY_LIST: dict[str, str] = {
    OPTION_CHARGER_EFFECTIVE_VOLTAGE: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_CHARGER_EFFECTIVE_VOLTAGE}",
    OPTION_CHARGER_MAX_CURRENT: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_CHARGER_MAX_CURRENT}",
    OPTION_CHARGER_MAX_SPEED: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_CHARGER_MAX_SPEED}",
    OPTION_CHARGER_MIN_CURRENT: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_CHARGER_MIN_CURRENT}",
    OPTION_CHARGER_MIN_WORKABLE_CURRENT: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_CHARGER_MIN_WORKABLE_CURRENT}",
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_CHARGER_POWER_ALLOCATION_WEIGHT}",
    OPTION_SUNRISE_ELEVATION_START_TRIGGER: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_SUNRISE_ELEVATION_START_TRIGGER}",
    OPTION_SUNSET_ELEVATION_END_TRIGGER: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_SUNSET_ELEVATION_END_TRIGGER}",
    OPTION_WAIT_NET_POWER_UPDATE: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_WAIT_NET_POWER_UPDATE}",
    OPTION_WAIT_CHARGEE_WAKEUP: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_WAIT_CHARGEE_WAKEUP}",
    OPTION_WAIT_CHARGEE_UPDATE_HA: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_WAIT_CHARGEE_UPDATE_HA}",
    OPTION_WAIT_CHARGEE_LIMIT_CHANGE: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_WAIT_CHARGEE_LIMIT_CHANGE}",
    OPTION_WAIT_CHARGER_ON: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_WAIT_CHARGER_ON}",
    OPTION_WAIT_CHARGER_OFF: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_WAIT_CHARGER_OFF}",
    OPTION_WAIT_CHARGER_AMP_CHANGE: f"number.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{OPTION_WAIT_CHARGER_AMP_CHANGE}",
}

OPTION_GLOBAL_DEFAULT_VALUE_LIST: dict[str, Any] = {
    OPTION_CHARGER_EFFECTIVE_VOLTAGE: 230,
    OPTION_CHARGER_MAX_CURRENT: 15,
    OPTION_CHARGER_MAX_SPEED: 6.1448,
    OPTION_CHARGER_MIN_CURRENT: 1,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT: 0,
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT: 1,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER: 3,
    OPTION_SUNSET_ELEVATION_END_TRIGGER: 6,
    OPTION_WAIT_NET_POWER_UPDATE: 60,
    OPTION_WAIT_CHARGEE_WAKEUP: 40,
    OPTION_WAIT_CHARGEE_UPDATE_HA: 5,
    OPTION_WAIT_CHARGEE_LIMIT_CHANGE: 5,
    OPTION_WAIT_CHARGER_ON: 11,
    OPTION_WAIT_CHARGER_OFF: 5,
    OPTION_WAIT_CHARGER_AMP_CHANGE: 1,
    #####################################
    # Internal entities
    #####################################
    CONTROL_CHARGER_ALLOCATED_POWER: 0,
}

# API entities
OPTION_DEVICE_ENTITY_LIST = {
    OPTION_CHARGER_DEVICE_NAME,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_GET_CHARGE_CURRENT,
    OPTION_CHARGER_SET_CHARGE_CURRENT,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
}

# Use this to delete an entity from saved options, eg. sensor.deleteme, button.deleteme
OPTION_DELETE_ENTITY = ".deleteme"
DEVICE_NAME_MARKER = "<DeviceName>"
CONFIG_NAME_MARKER = "<ConfigName>"

TESLA_CUSTOM_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_DEVICE_NAME: DEVICE_NAME_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"binary_sensor.{DEVICE_NAME_MARKER}charger",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: '["on"]',
    OPTION_CHARGER_CONNECT_STATE_LIST: '["on"]',
    OPTION_CHARGER_ON_OFF_SWITCH: f"switch.{DEVICE_NAME_MARKER}charger",
    OPTION_CHARGER_CHARGING_SENSOR: f"binary_sensor.{DEVICE_NAME_MARKER}charging",
    OPTION_CHARGER_CHARGING_STATE_LIST: '["on"]',
    OPTION_CHARGER_GET_CHARGE_CURRENT: f"number.{DEVICE_NAME_MARKER}charging_amps",
    OPTION_CHARGER_SET_CHARGE_CURRENT: f"number.{DEVICE_NAME_MARKER}charging_amps",
    OPTION_CHARGEE_SOC_SENSOR: f"sensor.{DEVICE_NAME_MARKER}battery",
    OPTION_CHARGEE_CHARGE_LIMIT: f"number.{DEVICE_NAME_MARKER}charge_limit",
    OPTION_CHARGEE_LOCATION_SENSOR: f"device_tracker.{DEVICE_NAME_MARKER}location_tracker",
    OPTION_CHARGEE_LOCATION_STATE_LIST: '["home"]',
    OPTION_CHARGEE_WAKE_UP_BUTTON: f"button.{DEVICE_NAME_MARKER}wake_up",
    OPTION_CHARGEE_UPDATE_HA_BUTTON: f"button.{DEVICE_NAME_MARKER}force_data_update",
    CONTROL_CHARGER_ALLOCATED_POWER: f"number.{DOMAIN}_{CONFIG_NAME_MARKER}_{CONTROL_CHARGER_ALLOCATED_POWER}",
}

OCPP_CHARGER_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_DEVICE_NAME: DEVICE_NAME_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"sensor.{DEVICE_NAME_MARKER}status_connector",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: '["Preparing"]',
    OPTION_CHARGER_CONNECT_STATE_LIST: '["Preparing", "Charging", "SuspendedEV", "SuspendedEVSE", "Finishing"]',
    OPTION_CHARGER_ON_OFF_SWITCH: f"switch.{DEVICE_NAME_MARKER}charge_control",
    OPTION_CHARGER_CHARGING_SENSOR: f"sensor.{DEVICE_NAME_MARKER}status_connector",
    OPTION_CHARGER_CHARGING_STATE_LIST: '["Charging", "SuspendedEV", "SuspendedEVSE"]',
    OPTION_CHARGER_GET_CHARGE_CURRENT: f"sensor.{DEVICE_NAME_MARKER}current_import",
    OPTION_CHARGER_SET_CHARGE_CURRENT: f"number.{DEVICE_NAME_MARKER}charge_current",
    OPTION_CHARGEE_SOC_SENSOR: None,
    OPTION_CHARGEE_CHARGE_LIMIT: None,
    OPTION_CHARGEE_LOCATION_SENSOR: None,
    OPTION_CHARGEE_LOCATION_STATE_LIST: None,
    OPTION_CHARGEE_WAKE_UP_BUTTON: None,
    OPTION_CHARGEE_UPDATE_HA_BUTTON: None,
    CONTROL_CHARGER_ALLOCATED_POWER: f"number.{DOMAIN}_{CONFIG_NAME_MARKER}_{CONTROL_CHARGER_ALLOCATED_POWER}",
}

CHARGE_API_ENTITIES: dict[str, dict[str, str | None]] = {
    CHARGER_DOMAIN_TESLA_CUSTOM: TESLA_CUSTOM_ENTITIES,
    CHARGER_DOMAIN_OCPP: OCPP_CHARGER_ENTITIES,
}


#######################################################
# Misc
#######################################################
class ChargeControlApi(Enum):
    """Enumeration of supported ChargeControl APIs."""

    TESLA_CUSTOM_API = "tesla_custom_api"
    TESLA_FLEET_API = "tesla_fleet_api"
    TESSIE_API = "tessie_api"
    TESLA_BLE_MQTT_API = "tesla_ble_mqtt_api"
    OCPP_CHARGER_API = "ocpp_charger_api"
    USER_CUSTOM_API = "user_custom_api"


DEBUG = False

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
Home Assistant: {HA_VERSION}
-------------------------------------------------------------------
"""
