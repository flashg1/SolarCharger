"""SolarCharger number platform."""

from homeassistant import config_entries, core
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    ENTITY_KEY_CHARGEE_CHARGE_LIMIT,
    ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE,
    ENTITY_KEY_CHARGER_MIN_CURRENT,
    NUMBER,
    SUBENTRY_TYPE_CHARGER,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
            numbers: dict[str, SolarChargerNumberEntity] = {}
            numbers[ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE] = (
                SolarChargerNumberChargerEffectiveVoltage(subentry)
            )
            numbers[ENTITY_KEY_CHARGER_MIN_CURRENT] = (
                SolarChargerNumberChargerMinCurrent(subentry)
            )
            numbers[ENTITY_KEY_CHARGEE_CHARGE_LIMIT] = (
                SolarChargerNumberChargeeChargeLimit(subentry)
            )
            coordinator.charge_controls[subentry.subentry_id].numbers = numbers

            async_add_entities(
                numbers.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberEntity(SolarChargerEntity, NumberEntity):
    """SolarCharger number entity."""

    def __init__(
        self,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the number."""

        super().__init__(subentry)
        id_name = slugify(f"{self._entity_key}")
        self._attr_unique_id = (
            f"{subentry.subentry_id}.{subentry.unique_id}.{NUMBER}.{id_name}"
        )
        self.set_entity_id(NUMBER, self._entity_key)

    def set_state(self, new_status):
        """Set new status."""
        self._attr_native_value = new_status
        self.update_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberChargerEffectiveVoltage(SolarChargerNumberEntity):
    """Representation of charger effective voltage number."""

    _entity_key = ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE
    _attr_device_class = NumberDeviceClass.VOLTAGE
    _attr_entity_registry_enabled_default = True
    _attr_icon = "mdi:ev-station"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1

    def __init__(self, subentry) -> None:
        """Initialise number."""
        super().__init__(subentry)

    # async def async_set_native_value(self, value: int) -> None:
    #     """Update charging amps."""
    #     await self._car.set_charging_amps(value)
    #     self.async_write_ha_state()

    # @property
    # def native_value(self) -> int:
    #     """Return charging amps."""
    #     return self._car.charge_current_request

    # @property
    # def native_min_value(self) -> int:
    #     """Return min charging ampst."""
    #     return CHARGE_CURRENT_MIN

    # @property
    # def native_max_value(self) -> int:
    #     """Return max charging amps."""
    #     return self._car.charge_current_request_max

    # @property
    # def native_unit_of_measurement(self) -> str:
    #     """Return percentage."""
    #     return UnitOfElectricPotential.VOLT


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberChargerMinCurrent(SolarChargerNumberEntity):
    """Representation of charger min current number."""

    _entity_key = ENTITY_KEY_CHARGER_MIN_CURRENT
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_entity_registry_enabled_default = True
    _attr_icon = "mdi:ev-station"
    _attr_mode = NumberMode.AUTO
    _attr_native_step = 1

    def __init__(self, subentry) -> None:
        """Initialise number."""
        super().__init__(subentry)

    # async def async_set_native_value(self, value: int) -> None:
    #     """Update charging amps."""
    #     await self._car.set_charging_amps(value)
    #     self.async_write_ha_state()

    # @property
    # def native_value(self) -> int:
    #     """Return charging amps."""
    #     return self._car.charge_current_request

    # @property
    # def native_min_value(self) -> int:
    #     """Return min charging ampst."""
    #     return CHARGE_CURRENT_MIN

    # @property
    # def native_max_value(self) -> int:
    #     """Return max charging amps."""
    #     return self._car.charge_current_request_max

    # @property
    # def native_unit_of_measurement(self) -> str:
    #     """Return percentage."""
    #     return UnitOfElectricCurrent.AMPERE


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberChargeeChargeLimit(SolarChargerNumberEntity):
    """Representation of a Tesla car charge limit number."""

    _entity_key = ENTITY_KEY_CHARGEE_CHARGE_LIMIT
    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_entity_registry_enabled_default = True
    _attr_icon = "mdi:ev-station"
    _attr_mode = NumberMode.AUTO
    _attr_native_step = 1

    def __init__(self, subentry) -> None:
        """Initialise number."""
        super().__init__(subentry)

    # async def async_set_native_value(self, value: int) -> None:
    #     """Update charge limit."""
    #     await self._car.change_charge_limit(value)
    #     self.async_write_ha_state()

    # @property
    # def native_value(self) -> int:
    #     """Return charge limit."""
    #     return self._car.charge_limit_soc

    # @property
    # def native_min_value(self) -> int:
    #     """Return min charge limit."""
    #     return (
    #         self._car.charge_limit_soc_min
    #         if self._car.charge_limit_soc_min is not None
    #         else 0
    #     )

    # @property
    # def native_max_value(self) -> int:
    #     """Return max charge limit."""
    #     return (
    #         self._car.charge_limit_soc_max
    #         if self._car.charge_limit_soc_max is not None
    #         else 100
    #     )

    # @property
    # def native_unit_of_measurement(self) -> str:
    #     """Return percentage."""
    #     return PERCENTAGE
