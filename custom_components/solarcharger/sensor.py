"""SolarCharger sensor platform."""

from homeassistant import config_entries, core
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_subentry_flow import SUBENTRY_TYPE_CHARGER
from .const import (
    COORDINATOR_STATES,
    DOMAIN,
    ENTITY_KEY_LAST_CHECK_SENSOR,
    ENTITY_KEY_RUN_STATE_SENSOR,
    SENSOR,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    # async_add_entities: Callable,
) -> None:
    """Set up sensors based on config entry."""
    # coordinator = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
            sensors: dict[str, SolarChargerSensorEntity] = {}
            sensors[ENTITY_KEY_RUN_STATE_SENSOR] = SolarChargerSensorRunState(subentry)
            sensors[ENTITY_KEY_LAST_CHECK_SENSOR] = SolarChargerSensorLastCheck(
                subentry
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


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorEntity(SolarChargerEntity, SensorEntity):
    """SolarCharger sensor entity."""

    def __init__(
        self,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(subentry)
        id_name = self._entity_key.replace("_", "").lower()
        self._attr_unique_id = f"{subentry.subentry_id}.{SENSOR}.{id_name}"
        self.set_entity_id(SENSOR, self._entity_key)

    def set_state(self, new_status):
        """Set new status."""
        self._attr_native_value = new_status
        self.update_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorRunState(SolarChargerSensorEntity):
    """Solar Charger run state sensor class."""

    _entity_key = ENTITY_KEY_RUN_STATE_SENSOR
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(COORDINATOR_STATES)
    _attr_entity_registry_enabled_default = True

    def __init__(self, subentry) -> None:
        """Initialise sensor."""
        super().__init__(subentry)

    # def set_run_state(self, new_status):
    #     """Set new status."""
    #     self._attr_native_value = new_status
    #     self.update_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSensorLastCheck(SolarChargerSensorEntity):
    """Solar Charger last check sensor class."""

    _entity_key = ENTITY_KEY_LAST_CHECK_SENSOR
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, subentry) -> None:
        """Initialise sensor."""
        super().__init__(subentry)

    # def set_last_check(self, new_status):
    #     """Set new status."""
    #     self._attr_native_value = new_status
    #     self.update_ha_state()
