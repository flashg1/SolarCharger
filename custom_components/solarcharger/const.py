"""Constants for the Solar Charger integration."""

from enum import Enum
from typing import Any

from homeassistant.const import Platform, __version__ as HA_VERSION

MANUFACTURER = "FlashG"
NAME = "Solar Charger"
DOMAIN = "solarcharger"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.1"
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
ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE = "charger_effective_voltage"
# ENTITY_KEY_CHARGER_MAX_CURRENT = "charger_max_current"
ENTITY_KEY_CHARGER_MAX_SPEED = "charger_max_speed"
ENTITY_KEY_CHARGER_MIN_CURRENT = "charger_min_current"
# ENTITY_KEY_CHARGER_MIN_WORKABLE_CURRENT = "charger_min_workable_current"
ENTITY_KEY_CHARGER_POWER_ALLOCATION_WEIGHT = "charger_power_allocation_weight"
# ENTITY_KEY_WAIT_NET_POWER_UPDATE = "wait_net_power_update"
# ENTITY_KEY_WAIT_CHARGER_UPDATE = "wait_charger_update"
# ENTITY_KEY_SUNRISE_ELEVATION_START_TRIGGER = "sunrise_elevation_start_trigger"
# ENTITY_KEY_SUNSET_ELEVATION_END_TRIGGER = "sunset_elevation_end_trigger"

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

# Wait times
WAIT_CHARGEE_WAKEUP = 40  # seconds
WAIT_CHARGEE_UPDATE_HA = 60  # seconds

#######################################################
# Subentry constants
#######################################################
SUBENTRY_TYPE_CHARGER = "charger"
SUBENTRY_CHARGER_DEVICE = "charger_device"
SUBENTRY_DEVICE_DOMAIN = "device_domain"
SUBENTRY_DEVICE_NAME = "device_name"

#######################################################
# Option constants
#######################################################

#####################################
# Power import/export sensor
#####################################
OPTION_NET_POWER = "net_power"

OPTION_SELECT_CHARGER = "select_charger"
OPTION_LAST_CHARGER_ID = "last_charger_id"

#####################################
# Option admin
#####################################
OPTION_GLOBAL_DEFAULTS = "Global defaults"
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

#######################################################
# Lists
#######################################################
# Default values
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
}

# API entities
OPTION_DEVICE_ENTITY_LIST = {
    OPTION_CHARGER_DEVICE_NAME,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_CHARGING_AMPS,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
}

# Use this to delete an entity from saved options, eg. sensor.deleteme, button.deleteme
OPTION_DELETE_ENTITY = ".deleteme"
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
    OPTION_CHARGER_DEVICE_NAME: DEVICE_MARKER,
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
