"""SolarCharger sensor platform."""

from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_local

from .const import (
    DOMAIN,
    MEDIAN_DATA_STATE_LIST,
    RESTORE_ON_START_FALSE,
    RESTORE_ON_START_TRUE,
    RUN_STATE_LIST,
    SENSOR,
    SENSOR_AVERAGE_PAUSE_DURATION,
    SENSOR_CONSUMED_ENERGY_TODAY,
    SENSOR_CONSUMED_POWER,
    SENSOR_DELTA_ALLOCATED_POWER,
    SENSOR_INSTANCE_COUNT,
    SENSOR_LAST_CHECK,
    SENSOR_LAST_PAUSE_DURATION,
    SENSOR_MEDIAN_NET_ALLOCATED_POWER,
    SENSOR_MEDIAN_NET_ALLOCATED_POWER_PERIOD,
    SENSOR_NET_ALLOCATED_POWER,
    SENSOR_NET_ALLOCATED_POWER_DATA_SET,
    SENSOR_NET_ALLOCATED_POWER_SAMPLE_SIZE,
    SENSOR_PAUSE_COUNT,
    SENSOR_RUN_STATE,
    SENSOR_SELF_PAUSED_TODAY,
    SENSOR_SHARE_ALLOCATION,
    SENSOR_SMA_NET_ALLOCATED_POWER,
    SENSOR_SYNC_UPDATE,
    MedianDataState,
    RunState,
)
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity
from .modules.coordinator import SolarChargerCoordinator

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorEntity(SolarChargerEntity, SensorEntity, RestoreEntity):
    """SolarCharger sensor entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SensorEntityDescription,
        starting_state: StateType | date | datetime | Decimal,
        is_restore_state: bool,
    ) -> None:
        """Initialize the sensor."""

        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)

        self.set_entity_id(SENSOR, config_item)
        self.set_entity_unique_id(SENSOR, config_item)
        self.entity_description = desc
        self._starting_state = starting_state
        self._is_restore_state = is_restore_state

    # ----------------------------------------------------------------------------
    def set_state(self, new_state: StateType | date | datetime | Decimal):
        """Set new status."""

        self._attr_native_value = new_state
        self.update_ha_state()

    # ----------------------------------------------------------------------------
    def get_state(self) -> StateType | date | datetime | Decimal:
        """Get sensor state."""

        return self._attr_native_value

    # ----------------------------------------------------------------------------
    # See https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-event-setup/
    async def async_added_to_hass(self) -> None:
        """Entity about to be added to hass. Restore state and subscribe for events here if needed."""

        await super().async_added_to_hass()

        if self._is_restore_state:
            if (
                last_state := await self.async_get_last_state()
            ) is not None and last_state.state not in (
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                try:
                    # Must keep type the same if entity is used in code for calculation or comparison.
                    # Otherwise will cause runtime exception.
                    self.set_state(type(self._starting_state)(last_state.state))

                except ValueError, TypeError:
                    _LOGGER.error(
                        "Failed to restore state for %s. Setting to default %s.",
                        self.entity_id,
                        self._starting_state,
                    )
                    self.set_state(self._starting_state)
            else:
                self.set_state(self._starting_state)
        else:
            self.set_state(self._starting_state)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorStateEntity(SolarChargerSensorEntity):
    """Solar Charger state sensor class."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SensorEntityDescription,
        starting_state: StateType | date | datetime | Decimal,
        is_restore_state: bool,
    ) -> None:
        """Initialise sensor."""

        super().__init__(
            config_item, subentry, entity_type, desc, starting_state, is_restore_state
        )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorResetAtMidnightEntity(SolarChargerSensorEntity):
    """Solar Charger reset at midnight sensor class."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SensorEntityDescription,
        starting_state: StateType | date | datetime | Decimal,
        is_restore_state: bool,
    ) -> None:
        """Initialise sensor."""

        super().__init__(
            config_item, subentry, entity_type, desc, starting_state, is_restore_state
        )

    # ----------------------------------------------------------------------------
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        await super().async_added_to_hass()

        # Register a listener to call _async_midnight_reset exactly at 00:00:00.
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight_reset, hour=0, minute=0, second=0
            )
        )

    # ----------------------------------------------------------------------------
    async def _async_midnight_reset(self, now_time: datetime) -> None:
        """Reset value to starting state at midnight. Confirmed now_time is in local time."""

        _LOGGER.debug(
            "Resetting %s to %s at %s.", self.entity_id, self._starting_state, now_time
        )
        self.set_state(self._starting_state)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorLastCheck(SolarChargerSensorEntity):
    """Solar Charger last check sensor class."""

    # _entity_key = ENTITY_KEY_LAST_CHECK_SENSOR
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    # _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SensorEntityDescription,
        starting_state: StateType | date | datetime | Decimal,
        is_restore_state: bool,
    ) -> None:
        """Initialise sensor."""

        super().__init__(
            config_item, subentry, entity_type, desc, starting_state, is_restore_state
        )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_SENSOR_LIST: tuple[
    tuple[
        str,
        Any,
        SolarChargerEntityType,
        SensorEntityDescription,
        StateType | date | datetime | Decimal,
        bool,
    ],
    ...,
] = (
    #####################################
    # Sensor entities
    # entity_category=None
    #####################################
    (
        SENSOR_RUN_STATE,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_RUN_STATE,
            device_class=SensorDeviceClass.ENUM,
            options=RUN_STATE_LIST,
        ),
        RunState.ENDED.value,  # str
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_DELTA_ALLOCATED_POWER,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL_GLOBAL,
        SensorEntityDescription(
            key=SENSOR_DELTA_ALLOCATED_POWER,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
            # Always force update when setting value even if value is same.
            force_update=True,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_NET_ALLOCATED_POWER,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_NET_ALLOCATED_POWER,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_NET_ALLOCATED_POWER_SAMPLE_SIZE,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_NET_ALLOCATED_POWER_SAMPLE_SIZE,
            state_class=SensorStateClass.TOTAL,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0,  # int
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_NET_ALLOCATED_POWER_DATA_SET,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_NET_ALLOCATED_POWER_DATA_SET,
            device_class=SensorDeviceClass.ENUM,
            options=MEDIAN_DATA_STATE_LIST,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        MedianDataState.NOT_READY.value,  # str
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_MEDIAN_NET_ALLOCATED_POWER,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_MEDIAN_NET_ALLOCATED_POWER,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_MEDIAN_NET_ALLOCATED_POWER_PERIOD,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_MEDIAN_NET_ALLOCATED_POWER_PERIOD,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_SMA_NET_ALLOCATED_POWER,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCALHIDDEN,
        SensorEntityDescription(
            key=SENSOR_SMA_NET_ALLOCATED_POWER,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_CONSUMED_POWER,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_CONSUMED_POWER,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_CONSUMED_ENERGY_TODAY,
        SolarChargerSensorResetAtMidnightEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_CONSUMED_ENERGY_TODAY,
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            state_class=SensorStateClass.TOTAL,
        ),
        0.0,  # float
        RESTORE_ON_START_TRUE,
    ),
    (
        SENSOR_SYNC_UPDATE,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_GLOBAL,
        SensorEntityDescription(
            key=SENSOR_SYNC_UPDATE,
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        as_local(datetime.now()),  # datetime
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_LAST_CHECK,
        SolarChargerSensorLastCheck,
        SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBALHIDDEN,
        SensorEntityDescription(
            key=SENSOR_LAST_CHECK,
        ),
        as_local(datetime.now()),  # datetime
        RESTORE_ON_START_FALSE,
    ),
    #####################################
    # Diagnostic entities
    # entity_category=EntityCategory.DIAGNOSTIC
    #####################################
    (
        SENSOR_INSTANCE_COUNT,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_INSTANCE_COUNT,
            state_class=SensorStateClass.TOTAL,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0,  # int
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_SHARE_ALLOCATION,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_SHARE_ALLOCATION,
            state_class=SensorStateClass.TOTAL,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0,  # int
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_SELF_PAUSED_TODAY,
        SolarChargerSensorResetAtMidnightEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_SELF_PAUSED_TODAY,
            state_class=SensorStateClass.TOTAL,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0,  # int
        RESTORE_ON_START_TRUE,
    ),
    (
        SENSOR_PAUSE_COUNT,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_PAUSE_COUNT,
            state_class=SensorStateClass.TOTAL,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0,  # int
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_AVERAGE_PAUSE_DURATION,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_AVERAGE_PAUSE_DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
    (
        SENSOR_LAST_PAUSE_DURATION,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL,
        SensorEntityDescription(
            key=SENSOR_LAST_PAUSE_DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        0.0,  # float
        RESTORE_ON_START_FALSE,
    ),
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        # For charger subentries only
        # if subentry.subentry_type in SUBENTRY_CHARGER_TYPES:

        # For both global default and charger subentries
        sensors: dict[str, SolarChargerSensorEntity] = {}

        for (
            config_item,
            cls,
            entity_type,
            entity_description,
            starting_state,
            is_restore_state,
        ) in CONFIG_SENSOR_LIST:
            if is_create_entity(subentry, entity_type):
                sensors[config_item] = cls(
                    config_item,
                    subentry,
                    entity_type,
                    entity_description,
                    starting_state,
                    is_restore_state,
                )

        if len(sensors) > 0:
            coordinator.device_controls[
                subentry.subentry_id
            ].controller.charge_control.entities.sensors = sensors
            async_add_entities(
                sensors.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
