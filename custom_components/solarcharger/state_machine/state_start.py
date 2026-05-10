# ruff: noqa: TRY401, TID252
"""State machine state."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import Event, EventStateChangedData
from homeassistant.util.dt import as_local, utcnow

from ..config.config_utils import create_entity_ids_from_templates
from ..const import (
    CONFIG_ENTITY_ID_LIST,
    CONFIG_LOCAL_OPTION_LIST,
    CONFIG_NET_POWER_SENSOR,
    NUMBER_POWER_MONITOR_DURATION,
    OPTION_CHARGER_NAME,
    OPTION_LOCAL_INTERNAL_ENTITIES,
    SENSOR_CONSUMED_POWER,
    SENSOR_MEDIAN_NET_ALLOCATED_POWER,
    SENSOR_MEDIAN_NET_POWER_PERIOD,
    SENSOR_NET_ALLOCATED_POWER,
    SENSOR_SMA_NET_ALLOCATED_POWER,
    RunState,
)
from ..models.model_charge_stats import ChargeStats
from ..models.model_config import ConfigValueDict
from ..models.model_median_data import MedianData, MedianDataPoint
from .solar_charge_state import SolarChargeState
from .state_initialise import StateInitialise

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateStart(SolarChargeState):
    """Starting state: Set up session variables."""

    def __init__(
        self,
    ) -> None:
        """Start machine state."""
        self.state = RunState.STARTING

    # ----------------------------------------------------------------------------
    # Subscriptions
    # ----------------------------------------------------------------------------
    def _update_sensor(self, config_item: str, value: float) -> None:
        """Update sensor."""

        assert self.solarcharge.entities.sensors is not None
        self.solarcharge.entities.sensors[config_item].set_state(value)

    # ----------------------------------------------------------------------------
    def _calculate_median_value(self, data: MedianData) -> None:
        """Calculate median value."""

        sample_size = len(data.sequence)
        ascending_list = sorted(data.sequence, key=lambda x: x.value)

        if sample_size % 2 == 0:
            # Even
            index = round(sample_size / 2)
            data.median_value = (
                ascending_list[index - 1].value + ascending_list[index].value
            ) / 2
        else:
            # Odd
            index = round((sample_size + 1) / 2)
            data.median_value = ascending_list[index - 1].value

    # ----------------------------------------------------------------------------
    def _calculate_median_period(self, data: MedianData) -> None:
        """Calculate median period."""

        sample_size = len(data.sequence)
        ascending_list = sorted(data.sequence, key=lambda x: x.period)

        if sample_size % 2 == 0:
            # Even
            index = round(sample_size / 2)
            data.median_period = (
                ascending_list[index - 1].period + ascending_list[index].period
            ) / 2
        else:
            # Odd
            index = round((sample_size + 1) / 2)
            data.median_period = ascending_list[index - 1].period

    # ----------------------------------------------------------------------------
    def _calculate_sma_value(self, data: MedianData) -> None:
        """Calculate simple moving average value."""

        data.sma_value = sum(x.value for x in data.sequence) / data.sample_size

    # ----------------------------------------------------------------------------
    def _update_net_allocated_power(
        self, data: MedianData, new_data_point: MedianDataPoint
    ) -> None:
        """Update net allocated power."""

        data.sequence.append(new_data_point)
        data.now_time = self.solarcharge.get_local_datetime()

        # Removes old data
        cut_off_time = data.now_time - data.window
        while data.sequence and data.sequence[0].time < cut_off_time:
            data.sequence.pop(0)

        data.sample_size = len(data.sequence)
        data.sample_duration = (
            timedelta(seconds=0)
            if data.sample_size == 0
            else data.sequence[data.sample_size - 1].time - data.sequence[0].time
        )
        data.median_value = 0.0
        data.median_period = 0.0
        data.sma_value = 0.0

        if data.sample_size > 0:
            # Calculate median from net power allocations.
            self._calculate_median_value(data)
            self._calculate_median_period(data)
            self._calculate_sma_value(data)

        self._update_sensor(SENSOR_MEDIAN_NET_POWER_PERIOD, data.median_period)
        self._update_sensor(SENSOR_NET_ALLOCATED_POWER, new_data_point.value)
        self._update_sensor(SENSOR_MEDIAN_NET_ALLOCATED_POWER, data.median_value)
        self._update_sensor(SENSOR_SMA_NET_ALLOCATED_POWER, data.sma_value)

    # ----------------------------------------------------------------------------
    # 2025-11-02 09:01:48.009 INFO (MainThread) [custom_components.solarcharger.chargers.controller] tesla_custom_tesla23m3:
    # entity_id=number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power,
    #
    # old_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-500.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:00:32.962356+11:00>,
    #
    # new_state=<state number.solarcharger_tesla_custom_tesla23m3_charger_allocated_power=-200.0; min=-23000.0, max=23000.0, step=1.0, mode=box,
    # unit_of_measurement=W, device_class=power, icon=mdi:flash, friendly_name=tesla_custom Tesla23m3 Allocated power @ 2025-11-02T20:01:48.008211+11:00>
    async def _async_handle_delta_allocated_power_update(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Fetch and process state change event.

        From Google AI:

        This function defines the last_reported_timestamp in Home Assistant, which tracks the
        exact time a device "checks in" or reports its status to Home Assistant, even if the
        actual state (e.g., 'on'/'off') or attributes (e.g., brightness) have not changed.

        This was introduced (circa Core 2024.3) to distinguish between when a sensor actually
        changed state versus when it simply sent an update, enabling better troubleshooting
        of dead sensors and accurate time-series analysis.

        Here is a breakdown of the technical note provided:

        1. "When the state is set and neither the state nor attributes are changed, the existing
        state will be mutated with an updated last_reported."

        -   What it means: If a temperature sensor sends 20°C and nothing else has changed,
        Home Assistant updates the existing State object in memory. It updates
        last_reported to now, but last_changed remains the same, because the value
        didn't actually change.
        -   Key Behavior: The object is "mutated" (modified in place) to reflect the heart-beat,
        rather than creating a new state entry in the database.

        2. "When handling a state change event, the last_reported_timestamp attribute of the old
        state will not be modified and can safely be used."

        -   What it means: When a state actually changes (e.g., 'off' -> 'on'), Home Assistant
        triggers a state_changed event.
        -   Safety: The old_state object in this event is a snapshot from before the change.
        Its last_reported timestamp is frozen. It is safe to use old_state.last_reported
        for calculating how long it took from the last check-in to the current change.

        3. "The last_reported_timestamp attribute of the new state may be modified and the
        last_updated_timestamp attribute should be used instead."

        -   What it means: When a state changes, the new_state object is created and then
        immediately updated with the new last_reported time.
        -   What to use: Because the new state's last_reported might be updated again
        immediately, if you need to know exactly when the change occurred in the
        database, use last_updated_timestamp (which indicates when the state object was
        updated) or last_changed (which indicates when the state value actually changed).

        4. "When handling a state report event, the last_reported_timestamp attribute may be
        modified and last_reported from the event data should be used instead."

        -   What it means: This refers specifically to the state_reported event—a high-volume
        event fired when a device reports data, but nothing has changed.
        -   What to use: Because the state object's last_reported might change while you are
        processing it, the safest way to get the true, precise report time is to look at the
        last_reported field within the actual Event data, rather than checking the state
        object itself.

        Summary of Key Timestamps

        Property		Description
        last_changed	When the state value (e.g., 'on' to 'off') changed.
        last_updated	When the state value or attributes changed.
        last_reported	When the integration/device sent data, regardless of changes.

        When to use last_reported

        -   Troubleshooting: Seeing if a motion sensor or zigbee device is still checking in,
        even if it hasn't detected motion.
        -   Stale Data: Identifying sensors that haven't reported in over X minutes.

        Note: last_reported is generally used in automation templates and backend logic,
        rather than on Lovelace cards, although it can be enabled via customization.
        """

        data = event.data
        entity_id = data["entity_id"]
        old_state = data["old_state"]
        new_state = data["new_state"]

        if new_state is not None:
            # duration_since_last_change = (
            #     new_state.last_changed_timestamp  # UTC
            #     - self.solarcharge.charge_current_updatetime
            # )

            try:
                allocated_power = float(new_state.state)
                old_updatetime = as_local(old_state.last_reported)
                new_updatetime = as_local(new_state.last_updated)
                period = (new_updatetime - old_updatetime).total_seconds()

                _LOGGER.debug(
                    "%s: entity_id=%s, old_state=%s, new_state=%s, period=%s",
                    self.solarcharge.caller,
                    entity_id,
                    old_state.state,
                    new_state.state,
                    period,
                )

                # Save allocated power to calculate moving average.
                if self.solarcharge.max_allocation_count > 0:
                    # if (
                    #     len(self.solarcharge.net_allocations)
                    #     >= self.solarcharge.max_allocation_count
                    # ):
                    #     self.solarcharge.net_allocations.pop(0)

                    assert self.solarcharge.entities.sensors is not None
                    consumed_power = float(
                        self.solarcharge.entities.sensors[SENSOR_CONSUMED_POWER].state
                    )

                    net_allocated_power = allocated_power - consumed_power
                    new_data_point = MedianDataPoint(
                        value=net_allocated_power,
                        period=period,
                        time=new_updatetime,
                    )
                    self._update_net_allocated_power(
                        self.solarcharge.net_allocations, new_data_point
                    )

            except Exception as e:
                _LOGGER.exception(
                    "%s: Failed to adjust current for net power %s W: %s",
                    self.solarcharge.caller,
                    new_state.state,
                    e,
                )

    # ----------------------------------------------------------------------------
    def _subscribe_allocated_power_update(self) -> None:
        """Subscribe for allocated power update."""

        self.solarcharge.give_up_real_power_allocation()
        self.solarcharge.tracker.track_delta_allocated_power_update(
            self._async_handle_delta_allocated_power_update
        )

    # ----------------------------------------------------------------------------
    # Log configuration for debugging
    # ----------------------------------------------------------------------------
    def _log_net_power_configs(self) -> None:

        net_power_entity_id = self.solarcharge.config_get_id(CONFIG_NET_POWER_SENSOR)
        net_power = self.solarcharge.get_net_power()

        _LOGGER.debug(
            "%s: %s=%s, wait_net_power_update=%s",
            self.solarcharge.caller,
            net_power_entity_id,
            net_power,
            self.solarcharge.wait_net_power_update,
        )

    # ----------------------------------------------------------------------------
    def _log_config_entities(self, entity_list: list[str]) -> None:
        """Log config entities."""

        val_dict = ConfigValueDict("Config entities", {})
        for config_item in entity_list:
            self.solarcharge.option_get_entity_string(config_item, val_dict)

        _LOGGER.debug("%s: %s", self.solarcharge.caller, val_dict)

    # ----------------------------------------------------------------------------
    def _log_local_options(self, option_list: list[str]) -> None:
        """Log local option values."""

        val_dict = ConfigValueDict("Local options", {})
        for config_item in option_list:
            self.solarcharge.option_get_string(config_item, val_dict)

        _LOGGER.debug("%s: %s", self.solarcharge.caller, val_dict)

    # ----------------------------------------------------------------------------
    def _log_internal_entities(self, template_map: dict[str, str]) -> None:
        """Log internal non-configurable entities."""

        entity_map: dict[str, Any] = {}
        device_name = self.solarcharge.option_get_string(OPTION_CHARGER_NAME)
        # config_name = self.solarcharge._subentry.unique_id
        config_name = self.solarcharge.caller
        create_entity_ids_from_templates(
            entity_map, template_map, device_name, config_name
        )

        val_dict = ConfigValueDict("Internal entities", {})
        for config_item, entity_id in list(entity_map.items()):
            self.solarcharge.option_get_entity_string_direct(
                config_item, entity_id, val_dict
            )

        _LOGGER.debug("%s: %s", self.solarcharge.caller, val_dict)

    # ----------------------------------------------------------------------------
    def log_configuration(self) -> None:
        """Log all configuration settings."""

        if _LOGGER.isEnabledFor(logging.DEBUG):
            self._log_net_power_configs()
            self._log_config_entities(CONFIG_ENTITY_ID_LIST)
            self._log_local_options(CONFIG_LOCAL_OPTION_LIST)
            self._log_internal_entities(OPTION_LOCAL_INTERNAL_ENTITIES)

    # ----------------------------------------------------------------------------
    # Main code
    # ----------------------------------------------------------------------------
    # Estimation only.
    # Run this first thing before starting session.
    def _is_session_triggered_by_timer(self) -> bool:
        """Trigger by timer?"""
        triggered_by_timer = False
        time_diff = timedelta(seconds=0)

        charge_start_time = self.solarcharge.get_local_datetime()
        next_charge_time = self.solarcharge.get_datetime(
            self.solarcharge.next_charge_time_trigger_entity_id
        )
        if next_charge_time is not None:
            if charge_start_time > next_charge_time:
                time_diff = charge_start_time - next_charge_time
            else:
                time_diff = next_charge_time - charge_start_time
            if time_diff < timedelta(seconds=30):
                triggered_by_timer = True

        _LOGGER.info(
            "%s: charge_start_time=%s, next_charge_time=%s, time_diff=%s, triggered_by_timer=%s",
            self.solarcharge.caller,
            charge_start_time,
            next_charge_time,
            time_diff,
            triggered_by_timer,
        )

        return triggered_by_timer

    # ----------------------------------------------------------------------------
    def _set_max_allocation_count(self, wait_net_power_update: float) -> None:
        """Initialize max allocation count."""

        monitor_duration = self.solarcharge.option_get_entity_number_or_abort(
            NUMBER_POWER_MONITOR_DURATION
        )
        monitor_duration_seconds = monitor_duration * 60

        self.solarcharge.net_allocations = MedianData(
            window=timedelta(minutes=monitor_duration), sequence=[]
        )

        # Set to 0 to disable power monitoring by default.
        self.solarcharge.max_allocation_count = 0

        if monitor_duration > 0:
            max_allocation_count = round(
                monitor_duration_seconds / wait_net_power_update
            )

            if max_allocation_count >= 5:
                self.solarcharge.max_allocation_count = max_allocation_count
            else:
                # Power monitor duration needs to be longer to reliably determine when to pause charger.
                _LOGGER.error(
                    "%s: Sample size %s is too small to reliably determine when to pause charger. "
                    "Sample size = Power monitor duration %s / wait net power update interval %s",
                    self.solarcharge.caller,
                    max_allocation_count,
                    monitor_duration_seconds,
                    wait_net_power_update,
                )

    # ----------------------------------------------------------------------------
    def _init_power_monitor_window(self, seconds_between_update: int) -> None:

        self._set_max_allocation_count(seconds_between_update)

    # ----------------------------------------------------------------------------
    def _init_instance_variables(self) -> None:
        """Set up instance variables once per session."""

        # Must run this first thing to estimate if session started by timer
        self.solarcharge.session_triggered_by_timer = (
            self._is_session_triggered_by_timer()
        )
        self.solarcharge.started_max_charge = 0
        self.solarcharge.started_calibrate_max_charge_speed = False

        # Init power monitor duration
        self._init_power_monitor_window(self.solarcharge.wait_net_power_update)

    # ----------------------------------------------------------------------------
    async def _async_start_session(self) -> None:
        """Start the charging session."""

        # Init instance variables
        self._init_instance_variables()

        # Init stats
        self.solarcharge.stats = ChargeStats()
        self.solarcharge.set_pause_stats(self.solarcharge.stats)

        self.log_configuration()

        # Subscribe for power allocation
        self._subscribe_allocated_power_update()

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Session starting state."""

        self.solarcharge.set_run_state(self.state)

        await self._async_start_session()

        self.solarcharge.set_machine_state(StateInitialise())
