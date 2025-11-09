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
    ENTITY_KEY_LAST_CHECK_SENSOR,
    ENTITY_KEY_RUN_STATE_SENSOR,
    SENSOR,
    SUBENTRY_TYPE_CHARGER,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorEntity(SolarChargerEntity, SensorEntity):
    """SolarCharger sensor entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        SolarChargerEntity.__init__(self, config_item, subentry)
        self.set_entity_id(SENSOR, config_item)
        self.set_entity_unique_id(SENSOR, config_item)
        self.entity_description = desc

    # ----------------------------------------------------------------------------
    def set_state(self, new_status):
        """Set new status."""
        self._attr_native_value = new_status
        self.update_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorRunState(SolarChargerSensorEntity):
    """Solar Charger run state sensor class."""

    # _entity_key = ENTITY_KEY_RUN_STATE_SENSOR
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(COORDINATOR_STATES)
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: SensorEntityDescription,
    ) -> None:
        """Initialise sensor."""
        super().__init__(config_item, subentry, desc)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorLastCheck(SolarChargerSensorEntity):
    """Solar Charger last check sensor class."""

    # _entity_key = ENTITY_KEY_LAST_CHECK_SENSOR
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: SensorEntityDescription,
    ) -> None:
        """Initialise sensor."""
        super().__init__(config_item, subentry, desc)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_SENSOR_LIST: tuple[tuple[str, Any, SensorEntityDescription], ...] = (
    #####################################
    # Sensor entities
    # entity_category=None
    #####################################
    (
        ENTITY_KEY_RUN_STATE_SENSOR,
        SolarChargerSensorRunState,
        SensorEntityDescription(
            key=ENTITY_KEY_RUN_STATE_SENSOR,
        ),
    ),
    (
        ENTITY_KEY_LAST_CHECK_SENSOR,
        SolarChargerSensorLastCheck,
        SensorEntityDescription(
            key=ENTITY_KEY_LAST_CHECK_SENSOR,
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
        if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
            sensors: dict[str, SolarChargerSensorEntity] = {}

            for (
                config_item,
                cls,
                entity_description,
            ) in CONFIG_SENSOR_LIST:
                sensors[config_item] = cls(
                    config_item,
                    subentry,
                    entity_description,
                )
            coordinator.charge_controls[subentry.subentry_id].sensors = sensors

            async_add_entities(
                sensors.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
            # await coordinator.init_sensors(
            #     coordinator.charge_controls[subentry.subentry_id]
            # )
