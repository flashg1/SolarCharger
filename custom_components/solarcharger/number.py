"""SolarCharger number platform."""

import logging

from homeassistant import config_entries, core
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberExtraStoredData,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    ENTITY_KEY_CHARGEE_CHARGE_LIMIT,
    ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE,
    ENTITY_KEY_CHARGER_MAX_SPEED,
    ENTITY_KEY_CHARGER_MIN_CURRENT,
    NUMBER,
    SUBENTRY_TYPE_CHARGER,
    SUBENTRY_TYPE_DEFAULTS,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# class SolarChargerNumberEntity(SolarChargerEntity, NumberEntity):
class SolarChargerNumberEntity(SolarChargerEntity, RestoreNumber):
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

    # def set_state(self, new_status):
    #     """Set new status."""
    #     self._attr_native_value = new_status
    #     self.update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = value

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        restore_num: (
            NumberExtraStoredData | None
        ) = await self.async_get_last_number_data()
        if restore_num is not None and restore_num.native_value is not None:
            await self.async_set_native_value(restore_num.native_value)
            _LOGGER.debug(
                "Restored %s: %s",
                self.entity_id,
                self._attr_native_value,
            )
        else:
            _LOGGER.debug("No restored data for %s", self.entity_id)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberChargerEffectiveVoltage(SolarChargerNumberEntity):
    """Representation of charger effective voltage number."""

    _entity_key = ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 100.0
    _attr_native_max_value = 700.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "V"
    _attr_mode = NumberMode.BOX

    def __init__(self, subentry) -> None:
        """Initialise number."""
        super().__init__(subentry)
        if self.value is None:
            self._attr_native_value = 230.0
            self.update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await super().async_set_native_value(value)
        # self.coordinator.max_charging_current = value
        # await self.coordinator.update_configuration()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberChargerMinCurrent(SolarChargerNumberEntity):
    """Representation of charger min current number."""

    _entity_key = ENTITY_KEY_CHARGER_MIN_CURRENT
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "A"
    _attr_mode = NumberMode.BOX
    # _attr_mode = NumberMode.AUTO

    def __init__(self, subentry) -> None:
        """Initialise number."""
        super().__init__(subentry)
        if self.value is None:
            self._attr_native_value = 1.0
            self.update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await super().async_set_native_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberChargerMaxSpeed(SolarChargerNumberEntity):
    """Representation of charger max speed."""

    _entity_key = ENTITY_KEY_CHARGER_MAX_SPEED
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "%/hr"
    _attr_mode = NumberMode.BOX

    def __init__(self, subentry) -> None:
        """Initialise number."""
        super().__init__(subentry)
        if self.value is None:
            self._attr_native_value = 6.1448
            self.update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await super().async_set_native_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberChargeeChargeLimit(SolarChargerNumberEntity):
    """Representation of a Tesla car charge limit number."""

    _entity_key = ENTITY_KEY_CHARGEE_CHARGE_LIMIT
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.BOX
    # _attr_mode = NumberMode.AUTO

    def __init__(self, subentry) -> None:
        """Initialise number."""
        super().__init__(subentry)
        if self.value is None:
            self._attr_native_value = 60.0
            self.update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await super().async_set_native_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
def async_init_charger_numbers(
    coordinator: SolarChargerCoordinator, subentry: ConfigSubentry
) -> dict[str, SolarChargerNumberEntity]:
    """Initialize charger numbers."""

    numbers: dict[str, SolarChargerNumberEntity] = {
        ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE: SolarChargerNumberChargerEffectiveVoltage(
            subentry
        ),
        ENTITY_KEY_CHARGER_MIN_CURRENT: SolarChargerNumberChargerMinCurrent(subentry),
        ENTITY_KEY_CHARGER_MAX_SPEED: SolarChargerNumberChargerMaxSpeed(subentry),
        ENTITY_KEY_CHARGEE_CHARGE_LIMIT: SolarChargerNumberChargeeChargeLimit(subentry),
    }

    coordinator.charge_controls[subentry.subentry_id].numbers = numbers

    return numbers


# ----------------------------------------------------------------------------
def async_init_global_default_numbers(
    coordinator: SolarChargerCoordinator, subentry: ConfigSubentry
) -> dict[str, SolarChargerNumberEntity]:
    """Initialize charger numbers."""

    numbers: dict[str, SolarChargerNumberEntity] = {
        ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE: SolarChargerNumberChargerEffectiveVoltage(
            subentry
        ),
        ENTITY_KEY_CHARGER_MIN_CURRENT: SolarChargerNumberChargerMinCurrent(subentry),
        ENTITY_KEY_CHARGER_MAX_SPEED: SolarChargerNumberChargerMaxSpeed(subentry),
    }

    coordinator.charge_controls[subentry.subentry_id].numbers = numbers

    return numbers


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
            numbers = async_init_charger_numbers(coordinator, subentry)
        elif subentry.subentry_type == SUBENTRY_TYPE_DEFAULTS:
            numbers = async_init_global_default_numbers(coordinator, subentry)
        else:
            continue

        async_add_entities(
            numbers.values(),
            update_before_add=False,
            config_subentry_id=subentry.subentry_id,
        )
