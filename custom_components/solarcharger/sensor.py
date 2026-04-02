"""SolarCharger sensor platform."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_UNKNOWN, UnitOfPower
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    DOMAIN,
    RUN_STATE_LIST,
    SENSOR,
    SENSOR_CHARGER_ALLOCATED_POWER,
    SENSOR_CONSUMED_POWER,
    SENSOR_INSTANCE_COUNT,
    SENSOR_LAST_CHECK,
    SENSOR_RUN_STATE,
    SENSOR_SHARE_ALLOCATION,
    RunState,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorEntity(SolarChargerEntity, SensorEntity):
    """SolarCharger sensor entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(SENSOR, config_item)
        self.set_entity_unique_id(SENSOR, config_item)
        self.entity_description = desc

    # ----------------------------------------------------------------------------
    def set_state(self, new_status):
        """Set new status."""
        self._attr_native_value = new_status
        self.update_ha_state()

    # ----------------------------------------------------------------------------
    # See https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-event-setup/
    async def async_added_to_hass(self) -> None:
        """Entity about to be added to hass. Restore state and subscribe for events here if needed."""

        await super().async_added_to_hass()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorStateEntity(SolarChargerSensorEntity):
    """Solar Charger last check sensor class."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SensorEntityDescription,
        starting_state: StateType | date | datetime | Decimal = None,
    ) -> None:
        """Initialise sensor."""
        super().__init__(config_item, subentry, entity_type, desc)

        self._attr_native_value = starting_state


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
        starting_state: StateType | date | datetime | Decimal = None,
    ) -> None:
        """Initialise sensor."""
        super().__init__(config_item, subentry, entity_type, desc)

        self._attr_native_value = starting_state


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_SENSOR_LIST: tuple[
    tuple[
        str,
        Any,
        SolarChargerEntityType,
        SensorEntityDescription,
        StateType | date | datetime | Decimal,
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
        RunState.STATE_ENDED.value,
    ),
    (
        SENSOR_CHARGER_ALLOCATED_POWER,
        SolarChargerSensorStateEntity,
        SolarChargerEntityType.TYPE_LOCAL_GLOBAL,
        SensorEntityDescription(
            key=SENSOR_CHARGER_ALLOCATED_POWER,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
            # Always force update when setting value even if value is same.
            force_update=True,
        ),
        0,
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
        0,
    ),
    (
        SENSOR_LAST_CHECK,
        SolarChargerSensorLastCheck,
        SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBALHIDDEN,
        SensorEntityDescription(
            key=SENSOR_LAST_CHECK,
        ),
        STATE_UNKNOWN,
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
        0,
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
        1,
    ),
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    # async_add_entities: Callable,
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
        ) in CONFIG_SENSOR_LIST:
            if is_create_entity(subentry, entity_type):
                sensors[config_item] = cls(
                    config_item,
                    subentry,
                    entity_type,
                    entity_description,
                    starting_state,
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
            # await coordinator.init_sensors(
            #     coordinator.charge_controls[subentry.subentry_id]
            # )
