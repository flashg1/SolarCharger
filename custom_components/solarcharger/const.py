"""Constants for the Solar Charger integration."""

from enum import Enum
from typing import Any

from homeassistant.const import Platform, __version__ as HA_VERSION

MANUFACTURER = "FlashG"
NAME = "Solar Charger"
DOMAIN = "solarcharger"
DOMAIN_DATA = f"{DOMAIN}_data"
# Also used in manifest.json
VERSION = "0.3beta4"
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

# HA entities
HA_SUN_ENTITY = "sun.sun"

# Platforms
SENSOR = Platform.SENSOR
SWITCH = Platform.SWITCH
BUTTON = Platform.BUTTON
NUMBER = Platform.NUMBER
TIME = Platform.TIME
DATETIME = Platform.DATETIME
BINARY_SENSOR = Platform.BINARY_SENSOR
DEVICE_TRACKER = Platform.DEVICE_TRACKER
SELECT = Platform.SELECT
PLATFORMS = [BUTTON, NUMBER, SELECT, SENSOR, SWITCH, TIME, DATETIME]
PLATFORM_OCPP = "ocpp"
PLATFORM_USER_CUSTOM = "user_custom"

CHARGER_DOMAIN_OCPP = "ocpp"
CHARGER_DOMAIN_TESLA_CUSTOM = "tesla_custom"
CHARGER_DOMAIN_TESLA_MQTTBLE = "mqtt"
CHARGER_DOMAIN_TESLA_FLEET = "tesla"
CHARGER_DOMAIN_TESLA_TESSIE = "tessie"


SUPPORTED_CHARGER_DOMAIN_LIST: list[str] = [
    CHARGER_DOMAIN_OCPP,
    CHARGER_DOMAIN_TESLA_CUSTOM,
    CHARGER_DOMAIN_TESLA_MQTTBLE,
    CHARGER_DOMAIN_TESLA_FLEET,
    CHARGER_DOMAIN_TESLA_TESSIE,
]

#######################################################
# Make sure the entity key names are unique.
#######################################################
#####################################
# Internal entities
#####################################
# Sensors
SENSOR_LAST_CHECK = "last_check"
SENSOR_RUN_STATE = "run_state"

# Boolean switches
SWITCH_FAST_CHARGE_MODE = "fast_charge_mode"
SWITCH_FORCE_HA_UPDATE = "force_ha_update"

# Action switches
SWITCH_START_CHARGE = "charge"
SWITCH_SCHEDULE_CHARGE = "schedule_charge"
SWITCH_PLUGIN_TRIGGER = "plugin_trigger"
SWITCH_SUN_TRIGGER = "sun_trigger"
SWITCH_CALIBRATE_MAX_CHARGE_SPEED = "calibrate_max_charge_speed"

# Buttons
BUTTON_START_CHARGE = "start_charge"
BUTTON_RESET_CHARGE_LIMIT_AND_TIME = "reset_charge_limit_and_time"

# Datetime triggers
DATETIME_NEXT_CHARGE_TIME = "next_charge_time"

# Number triggers
NUMBER_CHARGER_ALLOCATED_POWER = "charger_allocated_power"

# Calibrate max charge speed configs
CALIBRATE_MAX_SOC = 91
CALIBRATE_SOC_INCREASE = 4


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
EVENT_ACTION_NEW_CHARGE_CURRENT = "new_charge_current"
EVENT_ATTR_ACTION = "action"
EVENT_ATTR_VALUE = "new_current"

#######################################################
# Subentry constants
#######################################################
SUBENTRY_TYPE_DEFAULTS = "defaults"
SUBENTRY_TYPE_CHARGER = "charger"
SUBENTRY_TYPE_CUSTOM = "custom"

# Charger device types
SUBENTRY_CHARGER_TYPES: list[str] = [SUBENTRY_TYPE_CHARGER, SUBENTRY_TYPE_CUSTOM]

SUBENTRY_CHARGER_DEVICE_DOMAIN = "charger_device_domain"
SUBENTRY_CHARGER_DEVICE_NAME = "charger_device_name"
SUBENTRY_CHARGER_DEVICE_ID = "charger_device_id"

#######################################################
# Option constants
#######################################################

#####################################
# Power import/export sensor
#####################################
CONF_NET_POWER = "net_power"
CONF_WAIT_NET_POWER_UPDATE = "wait_net_power_update"  # 60 seconds

OPTION_SELECT_SETTINGS = "select_global_or_local_settings"
OPTION_LAST_CHARGER_ID = "last_charger_id"

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
NUMBER_CHARGER_EFFECTIVE_VOLTAGE = "charger_effective_voltage"  # No defaults
NUMBER_CHARGER_MAX_SPEED = "charger_max_speed"  # 6.1448 %/hr
NUMBER_CHARGER_MIN_CURRENT = "charger_min_current"  # 1 Amps
NUMBER_CHARGER_MIN_WORKABLE_CURRENT = "charger_min_workable_current"  # 0 Amps
NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT = "charger_power_allocation_weight"  # 1
NUMBER_CHARGEE_MIN_CHARGE_LIMIT = "chargee_min_charge_limit"
NUMBER_CHARGEE_MAX_CHARGE_LIMIT = "chargee_max_charge_limit"

NUMBER_SUNRISE_ELEVATION_START_TRIGGER = "sunrise_elevation_start_trigger"  # 3
NUMBER_SUNSET_ELEVATION_END_TRIGGER = "sunset_elevation_end_trigger"  # 6

# Wait times
NUMBER_WAIT_CHARGEE_WAKEUP = "wait_chargee_wakeup"  # 40 seconds
NUMBER_WAIT_CHARGEE_UPDATE_HA = "wait_chargee_update_ha"  # 5 seconds
NUMBER_WAIT_CHARGEE_LIMIT_CHANGE = "wait_chargee_limit_change"  # 5 seconds
NUMBER_WAIT_CHARGER_ON = "wait_charger_on"  # 11 seconds
NUMBER_WAIT_CHARGER_OFF = "wait_charger_off"  # 5 seconds
NUMBER_WAIT_CHARGER_AMP_CHANGE = "wait_charger_amp_change"  # 1 second

#####################################
# Charger control entities
#####################################
OPTION_CHARGER_NAME = "charger_name"
OPTION_CHARGER_PLUGGED_IN_SENSOR = "charger_plugged_in_sensor"
OPTION_CHARGER_CONNECT_TRIGGER_LIST = "charger_connect_trigger_list"
OPTION_CHARGER_CONNECT_STATE_LIST = "charger_connect_state_list"
OPTION_CHARGER_ON_OFF_SWITCH = "charger_on_off_switch"
OPTION_CHARGER_CHARGING_SENSOR = "charger_charging_sensor"
OPTION_CHARGER_CHARGING_STATE_LIST = "charger_charging_state_list"
OPTION_CHARGER_MAX_CURRENT = "charger_max_current"
OPTION_CHARGER_GET_CHARGE_CURRENT = "charger_get_charge_current"
OPTION_CHARGER_SET_CHARGE_CURRENT = "charger_set_charge_current"
OPTION_OCPP_CHARGER_ID = "charger_specific_id"
OPTION_OCPP_TRANSACTION_ID = "charger_transaction_id"

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
# Charge schedule entities
#####################################
NUMBER_CHARGE_LIMIT_MONDAY = "charge_limit_monday"
NUMBER_CHARGE_LIMIT_TUESDAY = "charge_limit_tuesday"
NUMBER_CHARGE_LIMIT_WEDNESDAY = "charge_limit_wednesday"
NUMBER_CHARGE_LIMIT_THURSDAY = "charge_limit_thursday"
NUMBER_CHARGE_LIMIT_FRIDAY = "charge_limit_friday"
NUMBER_CHARGE_LIMIT_SATURDAY = "charge_limit_saturday"
NUMBER_CHARGE_LIMIT_SUNDAY = "charge_limit_sunday"

TIME_CHARGE_ENDTIME_MONDAY = "charge_endtime_monday"
TIME_CHARGE_ENDTIME_TUESDAY = "charge_endtime_tuesday"
TIME_CHARGE_ENDTIME_WEDNESDAY = "charge_endtime_wednesday"
TIME_CHARGE_ENDTIME_THURSDAY = "charge_endtime_thursday"
TIME_CHARGE_ENDTIME_FRIDAY = "charge_endtime_friday"
TIME_CHARGE_ENDTIME_SATURDAY = "charge_endtime_saturday"
TIME_CHARGE_ENDTIME_SUNDAY = "charge_endtime_sunday"

#######################################################
# Default values
#######################################################
# Switch defaults
DEFAULT_ON = True
DEFAULT_OFF = False
RESTORE_ON_START_TRUE = True
RESTORE_ON_START_FALSE = False

OPTION_COMMON_DEFAULT_VALUES: dict[str, Any] = {
    #####################################
    # Global defaults: Environment defaults
    #####################################
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE: None,
    #####################################
    # Global defaults: Charge limit defaults
    #####################################
    NUMBER_CHARGE_LIMIT_MONDAY: 70,
    NUMBER_CHARGE_LIMIT_TUESDAY: 70,
    NUMBER_CHARGE_LIMIT_WEDNESDAY: 70,
    NUMBER_CHARGE_LIMIT_THURSDAY: 70,
    NUMBER_CHARGE_LIMIT_FRIDAY: 80,
    NUMBER_CHARGE_LIMIT_SATURDAY: 80,
    NUMBER_CHARGE_LIMIT_SUNDAY: 80,
    #####################################
    # Global defaults: Sun elevation triggers
    #####################################
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER: 3,
    NUMBER_SUNSET_ELEVATION_END_TRIGGER: 6,
    #####################################
    # Global defaults: Wait times
    #####################################
    NUMBER_WAIT_CHARGEE_WAKEUP: 40,
    NUMBER_WAIT_CHARGEE_UPDATE_HA: 5,
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE: 5,
    NUMBER_WAIT_CHARGER_ON: 11,
    NUMBER_WAIT_CHARGER_OFF: 5,
    NUMBER_WAIT_CHARGER_AMP_CHANGE: 1,
    #####################################
    # Local device required defaults
    #####################################
    NUMBER_CHARGER_MAX_SPEED: 6.1448,
    NUMBER_CHARGER_MIN_CURRENT: 1,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: 0,
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT: 1,
    NUMBER_CHARGER_ALLOCATED_POWER: 0,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT: 50,
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT: 100,
    #####################################
    # Local device optional defaults
    #####################################
    OPTION_CHARGER_MAX_CURRENT: None,
    OPTION_CHARGEE_CHARGE_LIMIT: 70,
    #####################################
    # Local device switch defaults
    #####################################
    SWITCH_START_CHARGE: DEFAULT_OFF,
    SWITCH_FAST_CHARGE_MODE: DEFAULT_OFF,
    SWITCH_FORCE_HA_UPDATE: DEFAULT_OFF,
    SWITCH_SCHEDULE_CHARGE: DEFAULT_OFF,
    SWITCH_PLUGIN_TRIGGER: DEFAULT_ON,
    SWITCH_SUN_TRIGGER: DEFAULT_ON,
    SWITCH_CALIBRATE_MAX_CHARGE_SPEED: DEFAULT_OFF,
}

OCPP_DEFAULT_VALUES: dict[str, Any] = {
    NUMBER_CHARGER_MIN_CURRENT: 0,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: 6,
}

TESLA_MQTTBLE_DEFAULT_VALUES: dict[str, Any] = {
    NUMBER_WAIT_CHARGEE_UPDATE_HA: 25,
}

USER_CUSTOM_DEFAULT_VALUES: dict[str, Any] = {
    SWITCH_PLUGIN_TRIGGER: DEFAULT_OFF,
}

CHARGE_API_DEFAULT_VALUES: dict[str, dict[str, Any | None]] = {
    OPTION_GLOBAL_DEFAULTS_ID: OPTION_COMMON_DEFAULT_VALUES,
    CHARGER_DOMAIN_OCPP: OCPP_DEFAULT_VALUES,
    CHARGER_DOMAIN_TESLA_CUSTOM: {},
    CHARGER_DOMAIN_TESLA_MQTTBLE: TESLA_MQTTBLE_DEFAULT_VALUES,
    CHARGER_DOMAIN_TESLA_FLEET: {},
    CHARGER_DOMAIN_TESLA_TESSIE: {},
    DOMAIN: USER_CUSTOM_DEFAULT_VALUES,
}

#######################################################
# Lists
#######################################################

#####################################
# Global default entities
# Matches with config_options_flow.py _charger_general_options_schema().
# Equivalent entities are also created for local device but hidden.
#####################################
OPTION_GLOBAL_DEFAULT_ENTITIES: dict[str, str] = {
    #####################################
    # Charge environment
    #####################################
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGER_EFFECTIVE_VOLTAGE}",
    # NUMBER_CHARGER_MAX_SPEED: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGER_MAX_SPEED}",
    # NUMBER_CHARGER_MIN_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGER_MIN_CURRENT}",
    # NUMBER_CHARGER_MIN_WORKABLE_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGER_MIN_WORKABLE_CURRENT}",
    # NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT}",
    # NUMBER_CHARGEE_MIN_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGEE_MIN_CHARGE_LIMIT}",
    # NUMBER_CHARGEE_MAX_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGEE_MAX_CHARGE_LIMIT}",
    #####################################
    # Charge scheduling
    #####################################
    NUMBER_CHARGE_LIMIT_MONDAY: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGE_LIMIT_MONDAY}",
    TIME_CHARGE_ENDTIME_MONDAY: f"{TIME}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{TIME_CHARGE_ENDTIME_MONDAY}",
    NUMBER_CHARGE_LIMIT_TUESDAY: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGE_LIMIT_TUESDAY}",
    TIME_CHARGE_ENDTIME_TUESDAY: f"{TIME}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{TIME_CHARGE_ENDTIME_TUESDAY}",
    NUMBER_CHARGE_LIMIT_WEDNESDAY: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGE_LIMIT_WEDNESDAY}",
    TIME_CHARGE_ENDTIME_WEDNESDAY: f"{TIME}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{TIME_CHARGE_ENDTIME_WEDNESDAY}",
    NUMBER_CHARGE_LIMIT_THURSDAY: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGE_LIMIT_THURSDAY}",
    TIME_CHARGE_ENDTIME_THURSDAY: f"{TIME}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{TIME_CHARGE_ENDTIME_THURSDAY}",
    NUMBER_CHARGE_LIMIT_FRIDAY: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGE_LIMIT_FRIDAY}",
    TIME_CHARGE_ENDTIME_FRIDAY: f"{TIME}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{TIME_CHARGE_ENDTIME_FRIDAY}",
    NUMBER_CHARGE_LIMIT_SATURDAY: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGE_LIMIT_SATURDAY}",
    TIME_CHARGE_ENDTIME_SATURDAY: f"{TIME}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{TIME_CHARGE_ENDTIME_SATURDAY}",
    NUMBER_CHARGE_LIMIT_SUNDAY: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_CHARGE_LIMIT_SUNDAY}",
    TIME_CHARGE_ENDTIME_SUNDAY: f"{TIME}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{TIME_CHARGE_ENDTIME_SUNDAY}",
    #####################################
    # Sunrise/sunset triggers
    #####################################
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_SUNRISE_ELEVATION_START_TRIGGER}",
    NUMBER_SUNSET_ELEVATION_END_TRIGGER: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_SUNSET_ELEVATION_END_TRIGGER}",
    #####################################
    # Wait times
    #####################################
    NUMBER_WAIT_CHARGEE_WAKEUP: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_WAIT_CHARGEE_WAKEUP}",
    NUMBER_WAIT_CHARGEE_UPDATE_HA: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_WAIT_CHARGEE_UPDATE_HA}",
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_WAIT_CHARGEE_LIMIT_CHANGE}",
    NUMBER_WAIT_CHARGER_ON: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_WAIT_CHARGER_ON}",
    NUMBER_WAIT_CHARGER_OFF: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_WAIT_CHARGER_OFF}",
    NUMBER_WAIT_CHARGER_AMP_CHANGE: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_GLOBAL_DEFAULTS}_{NUMBER_WAIT_CHARGER_AMP_CHANGE}",
}

#####################################
# Device API entities
#
# Note:
# Key name used in entity ID indicates entity created is not hidden and is configured in local defaults, eg.
#     OPTION_CHARGEE_CHARGE_LIMIT: f"number.{DOMAIN}_{CONFIG_NAME_MARKER}_{OPTION_CHARGEE_CHARGE_LIMIT}",
# ie. not using equivalent entity from global defaults.
#####################################
# Use this to delete an entity from saved options, eg. sensor.deleteme, button.deleteme
OPTION_DELETE_ENTITY = ".deleteme"
DEVICE_NAME_MARKER = "<DeviceName>"
CONFIG_NAME_MARKER = "<ConfigName>"

# See OCPP spec v1.6j page 38 transition states, and page 77 ChargePointStatus (sensor.charger_status_connector).
# Available (no EV connected)
# Preparing (EV plugged in but charging yet to start)
# Charging (EV plugged in with active charging session)
# SuspendedEV (EV plugged in but not accepting charge, eg. EV getting ready, charge limit reached)
# SuspendedEVSE (EV plugged in but EVSE does not allow charging, eg. current drops below 6A)
# Finishing (EV plugged in but charging session ending, ie. charger switched off)
# OCPP uses single sensor to indicate plugged in and charging
# Use 'Available' state for trigger testing with IAMMeter. Just need to turn on then off OCPP "Charge Control" to trigger the automation.
# OPTION_CHARGER_CONNECT_TRIGGER_LIST: '["Preparing", "Available"]',
# Add 'Available' to rc_ocpp_charger_connected for normal testing, and switch off charger to exit automation.
# OPTION_CHARGER_CONNECT_STATE_LIST: '["Preparing", "Charging", "SuspendedEV", "SuspendedEVSE", "Finishing", "Available"]',
OCPP_CHARGER_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_NAME: DEVICE_NAME_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}status_connector",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: '["Preparing"]',
    OPTION_CHARGER_CONNECT_STATE_LIST: '["Preparing", "Charging", "SuspendedEV", "SuspendedEVSE", "Finishing"]',
    OPTION_CHARGER_ON_OFF_SWITCH: f"{SWITCH}.{DEVICE_NAME_MARKER}charge_control",
    OPTION_CHARGER_CHARGING_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}status_connector",
    OPTION_CHARGER_CHARGING_STATE_LIST: '["Charging", "SuspendedEV", "SuspendedEVSE"]',
    OPTION_CHARGER_MAX_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}maximum_current",
    OPTION_CHARGER_GET_CHARGE_CURRENT: f"{SENSOR}.{DEVICE_NAME_MARKER}current_import",
    OPTION_CHARGER_SET_CHARGE_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}charge_current",
    OPTION_CHARGEE_SOC_SENSOR: None,
    OPTION_CHARGEE_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{OPTION_CHARGEE_CHARGE_LIMIT}",
    OPTION_CHARGEE_LOCATION_SENSOR: None,
    OPTION_CHARGEE_LOCATION_STATE_LIST: None,
    OPTION_CHARGEE_WAKE_UP_BUTTON: None,
    OPTION_CHARGEE_UPDATE_HA_BUTTON: None,
    # Non-configurable entities: Device specific entities
    OPTION_OCPP_CHARGER_ID: f"{SENSOR}.{DEVICE_NAME_MARKER}id",
    OPTION_OCPP_TRANSACTION_ID: f"{SENSOR}.{DEVICE_NAME_MARKER}transaction_id",
    # Configurable entities: Extra device specific entities
    NUMBER_CHARGER_MAX_SPEED: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MAX_SPEED}",
    NUMBER_CHARGER_MIN_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_CURRENT}",
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_WORKABLE_CURRENT}",
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT}",
    NUMBER_CHARGER_ALLOCATED_POWER: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_ALLOCATED_POWER}",
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MIN_CHARGE_LIMIT}",
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MAX_CHARGE_LIMIT}",
    # Non-configurable entities: Local device internal control entities (not used here, FYI only)
    DATETIME_NEXT_CHARGE_TIME: f"{DATETIME}.{DOMAIN}_{CONFIG_NAME_MARKER}_{DATETIME_NEXT_CHARGE_TIME}",
    SWITCH_START_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_START_CHARGE}",
    SWITCH_FAST_CHARGE_MODE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_FAST_CHARGE_MODE}",
    SWITCH_SCHEDULE_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SCHEDULE_CHARGE}",
    SWITCH_PLUGIN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_PLUGIN_TRIGGER}",
    SWITCH_SUN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SUN_TRIGGER}",
}

TESLA_CUSTOM_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_NAME: DEVICE_NAME_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"{BINARY_SENSOR}.{DEVICE_NAME_MARKER}charger",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: '["on"]',
    OPTION_CHARGER_CONNECT_STATE_LIST: '["on"]',
    OPTION_CHARGER_ON_OFF_SWITCH: f"{SWITCH}.{DEVICE_NAME_MARKER}charger",
    OPTION_CHARGER_CHARGING_SENSOR: f"{BINARY_SENSOR}.{DEVICE_NAME_MARKER}charging",
    OPTION_CHARGER_CHARGING_STATE_LIST: '["on"]',
    OPTION_CHARGER_MAX_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{OPTION_CHARGER_MAX_CURRENT}",
    OPTION_CHARGER_GET_CHARGE_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}charging_amps",
    OPTION_CHARGER_SET_CHARGE_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}charging_amps",
    OPTION_CHARGEE_SOC_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}battery",
    OPTION_CHARGEE_CHARGE_LIMIT: f"{NUMBER}.{DEVICE_NAME_MARKER}charge_limit",
    OPTION_CHARGEE_LOCATION_SENSOR: f"{DEVICE_TRACKER}.{DEVICE_NAME_MARKER}location_tracker",
    OPTION_CHARGEE_LOCATION_STATE_LIST: '["home"]',
    OPTION_CHARGEE_WAKE_UP_BUTTON: f"{BUTTON}.{DEVICE_NAME_MARKER}wake_up",
    OPTION_CHARGEE_UPDATE_HA_BUTTON: f"{BUTTON}.{DEVICE_NAME_MARKER}force_data_update",
    # Non-configurable entities: Device specific entities
    # Configurable entities: Extra device specific entities
    NUMBER_CHARGER_MAX_SPEED: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MAX_SPEED}",
    NUMBER_CHARGER_MIN_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_CURRENT}",
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_WORKABLE_CURRENT}",
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT}",
    NUMBER_CHARGER_ALLOCATED_POWER: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_ALLOCATED_POWER}",
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MIN_CHARGE_LIMIT}",
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MAX_CHARGE_LIMIT}",
    # Non-configurable entities: Local device internal control entities (not used here, FYI only)
    DATETIME_NEXT_CHARGE_TIME: f"{DATETIME}.{DOMAIN}_{CONFIG_NAME_MARKER}_{DATETIME_NEXT_CHARGE_TIME}",
    SWITCH_START_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_START_CHARGE}",
    SWITCH_FAST_CHARGE_MODE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_FAST_CHARGE_MODE}",
    SWITCH_SCHEDULE_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SCHEDULE_CHARGE}",
    SWITCH_PLUGIN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_PLUGIN_TRIGGER}",
    SWITCH_SUN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SUN_TRIGGER}",
}

TESLA_MQTTBLE_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_NAME: DEVICE_NAME_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}charge_cable",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: '["SAE", "IEC"]',
    OPTION_CHARGER_CONNECT_STATE_LIST: '["SAE", "IEC"]',
    OPTION_CHARGER_ON_OFF_SWITCH: f"{SWITCH}.{DEVICE_NAME_MARKER}charger",
    OPTION_CHARGER_CHARGING_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}charging_state",
    OPTION_CHARGER_CHARGING_STATE_LIST: '["Charging"]',
    OPTION_CHARGER_MAX_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{OPTION_CHARGER_MAX_CURRENT}",
    OPTION_CHARGER_GET_CHARGE_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}charging_current",
    OPTION_CHARGER_SET_CHARGE_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}charging_current",
    OPTION_CHARGEE_SOC_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}battery_level",
    OPTION_CHARGEE_CHARGE_LIMIT: f"{NUMBER}.{DEVICE_NAME_MARKER}charging_limit",
    OPTION_CHARGEE_LOCATION_SENSOR: None,
    OPTION_CHARGEE_LOCATION_STATE_LIST: None,
    OPTION_CHARGEE_WAKE_UP_BUTTON: f"{BUTTON}.{DEVICE_NAME_MARKER}wake_up_car",
    OPTION_CHARGEE_UPDATE_HA_BUTTON: f"{BUTTON}.{DEVICE_NAME_MARKER}force_update_charge",
    # Non-configurable entities: Device specific entities
    # Configurable entities: Extra device specific entities
    NUMBER_WAIT_CHARGEE_UPDATE_HA: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_WAIT_CHARGEE_UPDATE_HA}",
    NUMBER_CHARGER_MAX_SPEED: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MAX_SPEED}",
    NUMBER_CHARGER_MIN_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_CURRENT}",
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_WORKABLE_CURRENT}",
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT}",
    NUMBER_CHARGER_ALLOCATED_POWER: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_ALLOCATED_POWER}",
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MIN_CHARGE_LIMIT}",
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MAX_CHARGE_LIMIT}",
    # Non-configurable entities: Local device internal control entities (not used here, FYI only)
    DATETIME_NEXT_CHARGE_TIME: f"{DATETIME}.{DOMAIN}_{CONFIG_NAME_MARKER}_{DATETIME_NEXT_CHARGE_TIME}",
    SWITCH_START_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_START_CHARGE}",
    SWITCH_FAST_CHARGE_MODE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_FAST_CHARGE_MODE}",
    SWITCH_SCHEDULE_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SCHEDULE_CHARGE}",
    SWITCH_PLUGIN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_PLUGIN_TRIGGER}",
    SWITCH_SUN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SUN_TRIGGER}",
}

TESLA_FLEET_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_NAME: DEVICE_NAME_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: f"{BINARY_SENSOR}.{DEVICE_NAME_MARKER}charge_cable",
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: '["on"]',
    OPTION_CHARGER_CONNECT_STATE_LIST: '["on"]',
    OPTION_CHARGER_ON_OFF_SWITCH: f"{SWITCH}.{DEVICE_NAME_MARKER}charge",
    OPTION_CHARGER_CHARGING_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}charging",
    OPTION_CHARGER_CHARGING_STATE_LIST: '["charging"]',
    OPTION_CHARGER_MAX_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{OPTION_CHARGER_MAX_CURRENT}",
    OPTION_CHARGER_GET_CHARGE_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}charge_current",
    OPTION_CHARGER_SET_CHARGE_CURRENT: f"{NUMBER}.{DEVICE_NAME_MARKER}charge_current",
    OPTION_CHARGEE_SOC_SENSOR: f"{SENSOR}.{DEVICE_NAME_MARKER}battery_level",
    OPTION_CHARGEE_CHARGE_LIMIT: f"{NUMBER}.{DEVICE_NAME_MARKER}charge_limit",
    OPTION_CHARGEE_LOCATION_SENSOR: f"{DEVICE_TRACKER}.{DEVICE_NAME_MARKER}location",
    OPTION_CHARGEE_LOCATION_STATE_LIST: '["home"]',
    OPTION_CHARGEE_WAKE_UP_BUTTON: f"{BUTTON}.{DEVICE_NAME_MARKER}wake",
    OPTION_CHARGEE_UPDATE_HA_BUTTON: None,
    # Non-configurable entities: Device specific entities
    # Configurable entities: Extra device specific entities
    NUMBER_CHARGER_MAX_SPEED: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MAX_SPEED}",
    NUMBER_CHARGER_MIN_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_CURRENT}",
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_WORKABLE_CURRENT}",
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT}",
    NUMBER_CHARGER_ALLOCATED_POWER: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_ALLOCATED_POWER}",
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MIN_CHARGE_LIMIT}",
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MAX_CHARGE_LIMIT}",
    # Non-configurable entities: Local device internal control entities (not used here, FYI only)
    DATETIME_NEXT_CHARGE_TIME: f"{DATETIME}.{DOMAIN}_{CONFIG_NAME_MARKER}_{DATETIME_NEXT_CHARGE_TIME}",
    SWITCH_START_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_START_CHARGE}",
    SWITCH_FAST_CHARGE_MODE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_FAST_CHARGE_MODE}",
    SWITCH_SCHEDULE_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SCHEDULE_CHARGE}",
    SWITCH_PLUGIN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_PLUGIN_TRIGGER}",
    SWITCH_SUN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SUN_TRIGGER}",
}

TESLA_TESSIE_ENTITIES: dict[str, str | None] = TESLA_FLEET_ENTITIES

USER_CUSTOM_ENTITIES: dict[str, str | None] = {
    OPTION_CHARGER_NAME: DEVICE_NAME_MARKER,
    OPTION_CHARGER_PLUGGED_IN_SENSOR: None,
    OPTION_CHARGER_CONNECT_TRIGGER_LIST: None,
    OPTION_CHARGER_CONNECT_STATE_LIST: None,
    OPTION_CHARGER_ON_OFF_SWITCH: None,
    OPTION_CHARGER_CHARGING_SENSOR: None,
    OPTION_CHARGER_CHARGING_STATE_LIST: None,
    OPTION_CHARGER_MAX_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{OPTION_CHARGER_MAX_CURRENT}",
    OPTION_CHARGER_GET_CHARGE_CURRENT: None,
    OPTION_CHARGER_SET_CHARGE_CURRENT: None,
    OPTION_CHARGEE_SOC_SENSOR: None,
    OPTION_CHARGEE_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{OPTION_CHARGEE_CHARGE_LIMIT}",
    OPTION_CHARGEE_LOCATION_SENSOR: None,
    OPTION_CHARGEE_LOCATION_STATE_LIST: None,
    OPTION_CHARGEE_WAKE_UP_BUTTON: None,
    OPTION_CHARGEE_UPDATE_HA_BUTTON: None,
    # Non-configurable entities: Device specific entities
    # Configurable entities: Extra device specific entities
    NUMBER_CHARGER_MAX_SPEED: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MAX_SPEED}",
    NUMBER_CHARGER_MIN_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_CURRENT}",
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_MIN_WORKABLE_CURRENT}",
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT}",
    NUMBER_CHARGER_ALLOCATED_POWER: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGER_ALLOCATED_POWER}",
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MIN_CHARGE_LIMIT}",
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT: f"{NUMBER}.{DOMAIN}_{CONFIG_NAME_MARKER}_{NUMBER_CHARGEE_MAX_CHARGE_LIMIT}",
    # Non-configurable entities: Local device internal control entities (not used here, FYI only)
    DATETIME_NEXT_CHARGE_TIME: f"{DATETIME}.{DOMAIN}_{CONFIG_NAME_MARKER}_{DATETIME_NEXT_CHARGE_TIME}",
    SWITCH_START_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_START_CHARGE}",
    SWITCH_FAST_CHARGE_MODE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_FAST_CHARGE_MODE}",
    SWITCH_SCHEDULE_CHARGE: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SCHEDULE_CHARGE}",
    SWITCH_PLUGIN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_PLUGIN_TRIGGER}",
    SWITCH_SUN_TRIGGER: f"{SWITCH}.{DOMAIN}_{CONFIG_NAME_MARKER}_{SWITCH_SUN_TRIGGER}",
}

CHARGE_API_ENTITIES: dict[str, dict[str, str | None]] = {
    CHARGER_DOMAIN_OCPP: OCPP_CHARGER_ENTITIES,
    CHARGER_DOMAIN_TESLA_CUSTOM: TESLA_CUSTOM_ENTITIES,
    CHARGER_DOMAIN_TESLA_MQTTBLE: TESLA_MQTTBLE_ENTITIES,
    CHARGER_DOMAIN_TESLA_FLEET: TESLA_FLEET_ENTITIES,
    CHARGER_DOMAIN_TESLA_TESSIE: TESLA_TESSIE_ENTITIES,
    DOMAIN: USER_CUSTOM_ENTITIES,
}

#######################################################
# Subscription callbacks
#######################################################
# Naming convention
# CALLBACK_<ACTION> OR CALLBACK_<EVENT>_<ACTION>
CALLBACK_SUN_ELEVATION_UPDATE = "callback_sun_elevation_update"
CALLBACK_CHANGE_SUNRISE_ELEVATION_TRIGGER = "callback_change_sunrise_elevation_trigger"
CALLBACK_PLUG_IN_CHARGER = "callback_plug_in_charger"
CALLBACK_SUNRISE_START_CHARGE = "callback_sunrise_start_charge"
CALLBACK_SUNSET_DAILY_MAINTENANCE = "callback_sunset_daily_maintenance"
CALLBACK_ALLOCATE_POWER = "callback_allocate_power"
CALLBACK_NEXT_CHARGE_TIME_UPDATE = "callback_next_charge_time_update"
CALLBACK_NEXT_CHARGE_TIME_TRIGGER = "callback_next_charge_time_trigger"
CALLBACK_SOC_UPDATE = "callback_soc_update"


#######################################################
# Misc
#######################################################
class ChargeControlApi(Enum):
    """Enumeration of supported ChargeControl APIs."""

    OCPP_CHARGER_API = "ocpp_charger_api"
    TESLA_CUSTOM_API = "tesla_custom_api"
    TESLA_MQTTBLE_API = "tesla_mqtt_ble_api"
    TESLA_FLEET_API = "tesla_fleet_api"
    TESLA_TESSIE_API = "tesla_tessie_api"
    USER_CUSTOM_API = "user_custom_api"


CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE = 0.833

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
