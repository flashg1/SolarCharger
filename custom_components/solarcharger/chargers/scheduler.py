"""Module to manage the solar charging."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import date, datetime, time, timedelta
import inspect
import logging
from typing import Any

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers import device_registry as dr

# Might be of help in the future.
# from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.util.dt import as_local, utcnow

from ..const import (  # noqa: TID252
    CALIBRATE_MAX_SOC,
    CALIBRATE_SOC_INCREASE,
    CENTRE_OF_SUN_DEGREE_BELOW_HORIZON_AT_SUNRISE,
    CONF_WAIT_NET_POWER_UPDATE,
    DATETIME,
    DATETIME_NEXT_CHARGE_TIME,
    DOMAIN,
    EVENT_ACTION_NEW_CHARGE_CURRENT,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MAX_SPEED,
    NUMBER_CHARGER_MIN_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
    NUMBER_WAIT_CHARGEE_UPDATE_HA,
    NUMBER_WAIT_CHARGEE_WAKEUP,
    NUMBER_WAIT_CHARGER_AMP_CHANGE,
    NUMBER_WAIT_CHARGER_OFF,
    NUMBER_WAIT_CHARGER_ON,
    OPTION_CHARGEE_LOCATION_SENSOR,
    OPTION_CHARGEE_SOC_SENSOR,
    OPTION_CHARGEE_UPDATE_HA_BUTTON,
    OPTION_CHARGEE_WAKE_UP_BUTTON,
    OPTION_CHARGER_CHARGING_SENSOR,
    OPTION_CHARGER_ON_OFF_SWITCH,
    OPTION_CHARGER_PLUGGED_IN_SENSOR,
    SWITCH,
    SWITCH_CALIBRATE_MAX_CHARGE_SPEED,
    SWITCH_CHARGE,
    SWITCH_FAST_CHARGE_MODE,
    SWITCH_PLUGIN_TRIGGER,
    SWITCH_POLL_CHARGER_UPDATE,
    SWITCH_SCHEDULE_CHARGE,
    SWITCH_SUN_TRIGGER,
)
from ..entity import compose_entity_id  # noqa: TID252
from ..exceptions.entity_exception import EntityExceptionError  # noqa: TID252
from ..model_config import ConfigValueDict  # noqa: TID252
from ..sc_option_state import (  # noqa: TID252
    ChargeSchedule,
    ScheduleData,
    ScOptionState,
    StateOfCharge,
)
from ..utils import (  # noqa: TID252
    get_next_sunrise_time,
    get_sec_per_degree_sun_elevation,
    get_sun_elevation,
    log_is_event_loop,
)
from .chargeable import Chargeable
from .charger import Charger
from .tracker import Tracker

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

type SWITCH_ACTION = Callable[[bool], Coroutine[Any, Any, None]]


INITIAL_CHARGE_CURRENT = 6  # Initial charge current in Amps
MIN_TIME_BETWEEN_UPDATE = 10  # Minimum seconds between charger current updates

# Look ahead charge limit list including today.
# Use MAX_CHARGE_LIMIT_DIFF to calculate charge limit for all days except one day before maximum charge limit day.
# The day before maximum charge limit day will use MIN_CHARGE_LIMIT_DIFF to minimise charge limit difference for the next day.
MIN_CHARGE_LIMIT_DIFF = 5
MAX_CHARGE_LIMIT_DIFF = 10
LOOK_AHEAD_CHARGE_LIMIT_DAYS = 4


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class Scheduler(ScOptionState):
    """Class to manage the charge scheduling."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        tracker: Tracker,
        charger: Any,
        chargeable: Any,
        # charger: Charger,
        # chargeable: Chargeable,
    ) -> None:
        """Initialize the Charge instance."""

        caller = subentry.unique_id
        if caller is None:
            caller = __name__
        ScOptionState.__init__(self, hass, entry, subentry, caller)

        self._tracker = tracker
        self._charger = charger
        self._chargeable = chargeable

        # Non-modifiable local device entities, ie.
        # not defined in config_options_flow _charger_control_entities_schema().
        # These entities are also defined in config options, but not created until
        # after first initialisation (see above).
        self._next_charge_time_trigger = compose_entity_id(
            DATETIME, subentry.unique_id, DATETIME_NEXT_CHARGE_TIME
        )

        self._fast_charge_mode_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_FAST_CHARGE_MODE
        )
        self._poll_charger_update_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_POLL_CHARGER_UPDATE
        )

        self._charge_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_CHARGE
        )
        self._schedule_charge_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_SCHEDULE_CHARGE
        )
        self._plugin_trigger_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_PLUGIN_TRIGGER
        )
        self._sun_trigger_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_SUN_TRIGGER
        )
        self._calibrate_max_charge_speed_switch = compose_entity_id(
            SWITCH, subentry.unique_id, SWITCH_CALIBRATE_MAX_CHARGE_SPEED
        )

        self._history_date = datetime(2026, 1, 1, 0, 0, 0)

        self._session_triggered_by_timer = False
        self._starting_goal: ScheduleData
        self._running_goal: ScheduleData

        self._started_calibrate_max_charge_speed = False
        self._charge_current_updatetime: float = 0
        self._soc_updates: list[StateOfCharge] = []
        self._calibrate_max_charge_limit: float
