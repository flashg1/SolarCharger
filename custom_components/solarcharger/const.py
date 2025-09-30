"""Constants for the Solar Charger integration."""

from enum import Enum

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
