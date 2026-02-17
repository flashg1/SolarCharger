"""SolarCharger sensor platform."""

from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    COORDINATOR_STATES,
    DOMAIN,
    SENSOR,
    SENSOR_LAST_CHECK,
    SENSOR_RUN_STATE,
    SUBENTRY_CHARGER_TYPES,
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
class SolarChargerSensorRunState(SolarChargerSensorEntity):
    """Solar Charger run state sensor class."""

    # _entity_key = ENTITY_KEY_RUN_STATE_SENSOR
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(COORDINATOR_STATES)
    # _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SensorEntityDescription,
    ) -> None:
        """Initialise sensor."""
        super().__init__(config_item, subentry, entity_type, desc)


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
    ) -> None:
        """Initialise sensor."""
        super().__init__(config_item, subentry, entity_type, desc)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_SENSOR_LIST: tuple[
    tuple[str, Any, SolarChargerEntityType, SensorEntityDescription], ...
] = (
    #####################################
    # Sensor entities
    # entity_category=None
    #####################################
    (
        SENSOR_RUN_STATE,
        SolarChargerSensorRunState,
        SolarChargerEntityType.LOCAL_DEFAULT,
        SensorEntityDescription(
            key=SENSOR_RUN_STATE,
        ),
    ),
    (
        SENSOR_LAST_CHECK,
        SolarChargerSensorLastCheck,
        SolarChargerEntityType.HIDDEN_DEFAULT,
        SensorEntityDescription(
            key=SENSOR_LAST_CHECK,
        ),
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
        if subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
            sensors: dict[str, SolarChargerSensorEntity] = {}

            for (
                config_item,
                cls,
                entity_type,
                entity_description,
            ) in CONFIG_SENSOR_LIST:
                if is_create_entity(subentry, entity_type):
                    sensors[config_item] = cls(
                        config_item,
                        subentry,
                        entity_type,
                        entity_description,
                    )

            if len(sensors) > 0:
                coordinator.device_controls[
                    subentry.subentry_id
                ].controller.charge_control.sensors = sensors
                async_add_entities(
                    sensors.values(),
                    update_before_add=False,
                    config_subentry_id=subentry.subentry_id,
                )
                # await coordinator.init_sensors(
                #     coordinator.charge_controls[subentry.subentry_id]
                # )
