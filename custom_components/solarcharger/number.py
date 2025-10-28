"""SolarCharger number platform."""

import logging
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
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
from homeassistant.helpers import entity
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
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGER_EFFECTIVE_VOLTAGE,
    OPTION_CHARGER_MAX_CURRENT,
    OPTION_CHARGER_MAX_SPEED,
    OPTION_CHARGER_MIN_CURRENT,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT,
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER,
    OPTION_SUNSET_ELEVATION_END_TRIGGER,
    OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
    OPTION_WAIT_CHARGEE_UPDATE_HA,
    OPTION_WAIT_CHARGEE_WAKEUP,
    OPTION_WAIT_CHARGER_AMP_CHANGE,
    OPTION_WAIT_CHARGER_OFF,
    OPTION_WAIT_CHARGER_ON,
    OPTION_WAIT_NET_POWER_UPDATE,
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
class SolarChargerNumberConfigEntity(SolarChargerNumberEntity):
    """SolarCharger configurable number entity."""

    #     _entity_key = ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE
    #     _attr_entity_category = EntityCategory.CONFIG
    #     _attr_native_min_value = 100.0
    #     _attr_native_max_value = 700.0
    #     _attr_native_step = 1.0
    #     _attr_native_unit_of_measurement = "V"
    #     _attr_mode = NumberMode.BOX
    #     # _attr_mode = NumberMode.AUTO

    def __init__(
        self,
        name: str,
        subentry: ConfigSubentry,
        desc: NumberEntityDescription,
        default_val,
    ) -> None:
        """Initialise number."""
        self._entity_key = name
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.BOX

        super().__init__(subentry)
        self.entity_description = desc
        self._attr_should_poll = False
        self._attr_has_entity_name = True

        if self.value is None:
            self._attr_native_value = default_val
            self.update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await super().async_set_native_value(value)
        # self.coordinator.max_charging_current = value
        # await self.coordinator.update_configuration()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# class SolarChargerNumberChargerEffectiveVoltage(SolarChargerNumberEntity):
#     """Representation of charger effective voltage number."""

#     _entity_key = ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE
#     _attr_entity_category = EntityCategory.CONFIG
#     _attr_native_min_value = 100.0
#     _attr_native_max_value = 700.0
#     _attr_native_step = 1.0
#     _attr_native_unit_of_measurement = "V"
#     _attr_mode = NumberMode.BOX
#     # _attr_mode = NumberMode.AUTO

#     def __init__(self, subentry) -> None:
#         """Initialise number."""
#         super().__init__(subentry)
#         if self.value is None:
#             self._attr_native_value = 230.0
#             self.update_ha_state()

#     async def async_set_native_value(self, value: float) -> None:
#         """Set new value."""
#         await super().async_set_native_value(value)
#         # self.coordinator.max_charging_current = value
#         # await self.coordinator.update_configuration()


# # ----------------------------------------------------------------------------
# # ----------------------------------------------------------------------------
# class SolarChargerNumberChargerMinCurrent(SolarChargerNumberEntity):
#     """Representation of charger min current number."""

#     _entity_key = ENTITY_KEY_CHARGER_MIN_CURRENT
#     _attr_entity_category = EntityCategory.CONFIG
#     _attr_native_min_value = 0.0
#     _attr_native_max_value = 100.0
#     _attr_native_step = 1.0
#     _attr_native_unit_of_measurement = "A"
#     _attr_mode = NumberMode.BOX

#     def __init__(self, subentry) -> None:
#         """Initialise number."""
#         super().__init__(subentry)
#         if self.value is None:
#             self._attr_native_value = 1.0
#             self.update_ha_state()

#     async def async_set_native_value(self, value: float) -> None:
#         """Set new value."""
#         await super().async_set_native_value(value)


# # ----------------------------------------------------------------------------
# # ----------------------------------------------------------------------------
# class SolarChargerNumberChargerMaxSpeed(SolarChargerNumberEntity):
#     """Representation of charger max speed."""

#     _entity_key = ENTITY_KEY_CHARGER_MAX_SPEED
#     _attr_entity_category = EntityCategory.CONFIG
#     _attr_native_min_value = 0.0
#     _attr_native_max_value = 100.0
#     _attr_native_step = 1.0
#     _attr_native_unit_of_measurement = "%/hr"
#     _attr_mode = NumberMode.BOX

#     def __init__(self, subentry) -> None:
#         """Initialise number."""
#         super().__init__(subentry)
#         if self.value is None:
#             self._attr_native_value = 6.1448
#             self.update_ha_state()

#     async def async_set_native_value(self, value: float) -> None:
#         """Set new value."""
#         await super().async_set_native_value(value)


# # ----------------------------------------------------------------------------
# # ----------------------------------------------------------------------------
# class SolarChargerNumberChargeeChargeLimit(SolarChargerNumberEntity):
#     """Representation of a Tesla car charge limit number."""

#     _entity_key = ENTITY_KEY_CHARGEE_CHARGE_LIMIT
#     _attr_entity_category = EntityCategory.CONFIG
#     _attr_native_min_value = 0.0
#     _attr_native_max_value = 100.0
#     _attr_native_step = 1.0
#     _attr_native_unit_of_measurement = "%"
#     _attr_mode = NumberMode.BOX

#     def __init__(self, subentry) -> None:
#         """Initialise number."""
#         super().__init__(subentry)
#         if self.value is None:
#             self._attr_native_value = 60.0
#             self.update_ha_state()

#     async def async_set_native_value(self, value: float) -> None:
#         """Set new value."""
#         await super().async_set_native_value(value)


# # ----------------------------------------------------------------------------
# # ----------------------------------------------------------------------------
# def async_init_charger_numbers(
#     coordinator: SolarChargerCoordinator, subentry: ConfigSubentry
# ) -> dict[str, SolarChargerNumberEntity]:
#     """Initialize charger numbers."""

#     numbers: dict[str, SolarChargerNumberEntity] = {
#         ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE: SolarChargerNumberChargerEffectiveVoltage(
#             subentry
#         ),
#         ENTITY_KEY_CHARGER_MIN_CURRENT: SolarChargerNumberChargerMinCurrent(subentry),
#         ENTITY_KEY_CHARGER_MAX_SPEED: SolarChargerNumberChargerMaxSpeed(subentry),
#         ENTITY_KEY_CHARGEE_CHARGE_LIMIT: SolarChargerNumberChargeeChargeLimit(subentry),
#     }

#     coordinator.charge_controls[subentry.subentry_id].numbers = numbers

#     return numbers


# # ----------------------------------------------------------------------------
# def async_init_global_default_numbers(
#     coordinator: SolarChargerCoordinator, subentry: ConfigSubentry
# ) -> dict[str, SolarChargerNumberEntity]:
#     """Initialize charger numbers."""

#     numbers: dict[str, SolarChargerNumberEntity] = {
#         ENTITY_KEY_CHARGER_EFFECTIVE_VOLTAGE: SolarChargerNumberChargerEffectiveVoltage(
#             subentry
#         ),
#         ENTITY_KEY_CHARGER_MIN_CURRENT: SolarChargerNumberChargerMinCurrent(subentry),
#         ENTITY_KEY_CHARGER_MAX_SPEED: SolarChargerNumberChargerMaxSpeed(subentry),
#     }

#     coordinator.charge_controls[subentry.subentry_id].numbers = numbers

#     return numbers


# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        # if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
        #     numbers = async_init_charger_numbers(coordinator, subentry)
        # elif subentry.subentry_type == SUBENTRY_TYPE_DEFAULTS:
        #     numbers = async_init_global_default_numbers(coordinator, subentry)
        # else:
        #     continue

        numbers = {}
        for config_item, default_val, entity_description in CONFIG_NUMBER_LIST:
            numbers[config_item] = SolarChargerNumberConfigEntity(
                config_item, subentry, entity_description, default_val
            )
        coordinator.charge_controls[subentry.subentry_id].numbers = numbers

        async_add_entities(
            numbers.values(),
            update_before_add=False,
            config_subentry_id=subentry.subentry_id,
        )

    # sensors = [
    #     SensorCls(coordinator, entity_description)
    #     for SensorCls, entity_description in SENSORS
    # ]
    # async_add_entities(sensors, update_before_add=False)


# XX: dict[str, str] = {
#     OPTION_CHARGER_EFFECTIVE_VOLTAGE: "number.solarcharger_global_defaults_charger_effective_voltage",
#     OPTION_CHARGER_MAX_CURRENT: "number.solarcharger_global_defaults_charger_max_current",
#     OPTION_CHARGER_MAX_SPEED: "number.solarcharger_global_defaults_charger_max_speed",
#     OPTION_CHARGER_MIN_CURRENT: "number.solarcharger_global_defaults_charger_min_current",
#     OPTION_CHARGER_MIN_WORKABLE_CURRENT: "number.solarcharger_global_defaults_charger_min_workable_current",
#     OPTION_CHARGER_POWER_ALLOCATION_WEIGHT: "number.solarcharger_global_defaults_charger_power_allocation_weight",
#     OPTION_SUNRISE_ELEVATION_START_TRIGGER: "number.solarcharger_global_defaults_sunrise_elevation_start_trigger",
#     OPTION_SUNSET_ELEVATION_END_TRIGGER: "number.solarcharger_global_defaults_sunset_elevation_end_trigger",
#     OPTION_WAIT_NET_POWER_UPDATE: "number.solarcharger_global_defaults_wait_net_power_update",
#     OPTION_WAIT_CHARGEE_WAKEUP: "number.solarcharger_global_defaults_wait_chargee_wakeup",
#     OPTION_WAIT_CHARGEE_UPDATE_HA: "number.solarcharger_global_defaults_wait_chargee_update_ha",
#     OPTION_WAIT_CHARGEE_LIMIT_CHANGE: "number.solarcharger_global_defaults_wait_chargee_limit_change",
#     OPTION_WAIT_CHARGER_ON: "number.solarcharger_global_defaults_wait_charger_on",
#     OPTION_WAIT_CHARGER_OFF: "number.solarcharger_global_defaults_wait_charger_off",
#     OPTION_WAIT_CHARGER_AMP_CHANGE: "number.solarcharger_global_defaults_wait_charger_amp_change",
# }

# _entity_key = ENTITY_KEY_CHARGEE_CHARGE_LIMIT
# _attr_entity_category = EntityCategory.CONFIG
# _attr_native_min_value = 0.0
# _attr_native_max_value = 100.0
# _attr_native_step = 1.0
# _attr_native_unit_of_measurement = "%"
# _attr_mode = NumberMode.BOX


CONFIG_NUMBER_LIST: tuple[
    # tuple[str, SolarChargerNumberConfigEntity, NumberEntityDescription], ...
    tuple[str, float, NumberEntityDescription], ...
] = (
    (
        OPTION_CHARGER_EFFECTIVE_VOLTAGE,
        230,
        NumberEntityDescription(
            key=OPTION_CHARGER_EFFECTIVE_VOLTAGE,
            # translation_key=OPTION_CHARGER_EFFECTIVE_VOLTAGE,
            # entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            native_min_value=100.0,
            native_max_value=700.0,
            # native_step=1.0,
            # mode=NumberMode.BOX,
            # entity_registry_enabled_default=True,
        ),
    ),
    (
        OPTION_CHARGER_MAX_CURRENT,
        15,
        NumberEntityDescription(
            key=OPTION_CHARGER_MAX_CURRENT,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_MAX_SPEED,
        6.1448,
        NumberEntityDescription(
            key=OPTION_CHARGER_MAX_SPEED,
            native_unit_of_measurement="%/hr",
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_MIN_CURRENT,
        1,
        NumberEntityDescription(
            key=OPTION_CHARGER_MIN_CURRENT,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_MIN_WORKABLE_CURRENT,
        0,
        NumberEntityDescription(
            key=OPTION_CHARGER_MIN_WORKABLE_CURRENT,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
        1,
        NumberEntityDescription(
            key=OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGEE_CHARGE_LIMIT,
        60,
        NumberEntityDescription(
            key=OPTION_CHARGEE_CHARGE_LIMIT,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
)
