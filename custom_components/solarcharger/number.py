"""SolarCharger number platform."""

import logging

from homeassistant import config_entries, core
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberExtraStoredData,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_utils import get_device_config_default_value
from .const import (
    DOMAIN,
    NUMBER,
    NUMBER_CHARGE_LIMIT_FRIDAY,
    NUMBER_CHARGE_LIMIT_MONDAY,
    NUMBER_CHARGE_LIMIT_SATURDAY,
    NUMBER_CHARGE_LIMIT_SUNDAY,
    NUMBER_CHARGE_LIMIT_THURSDAY,
    NUMBER_CHARGE_LIMIT_TUESDAY,
    NUMBER_CHARGE_LIMIT_WEDNESDAY,
    NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
    NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
    NUMBER_CHARGER_ALLOCATED_POWER,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MAX_SPEED,
    NUMBER_CHARGER_MIN_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
    NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT,
    NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
    NUMBER_SUNSET_ELEVATION_END_TRIGGER,
    NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
    NUMBER_WAIT_CHARGEE_UPDATE_HA,
    NUMBER_WAIT_CHARGEE_WAKEUP,
    NUMBER_WAIT_CHARGER_AMP_CHANGE,
    NUMBER_WAIT_CHARGER_OFF,
    NUMBER_WAIT_CHARGER_ON,
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGER_MAX_CURRENT,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberEntity(SolarChargerEntity, RestoreNumber):
    """SolarCharger number entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: NumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(NUMBER, config_item)
        self.set_entity_unique_id(NUMBER, config_item)
        self.entity_description = desc

    # ----------------------------------------------------------------------------
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = value

        # Should force state update here, otherwise update by polling only and be delayed by few seconds.
        self.update_ha_state()

    # ----------------------------------------------------------------------------
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
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: NumberEntityDescription,
        default_val: float,
    ) -> None:
        """Initialise number."""
        super().__init__(config_item, subentry, entity_type, desc)

        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.BOX

        self._attr_has_entity_name = True
        # Must set _attr_should_poll=True (default) for HA to register value changes
        # self._attr_should_poll = False

        if self.value is None:
            self._attr_native_value = default_val
            self.update_ha_state()

    # ----------------------------------------------------------------------------
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await super().async_set_native_value(value)

    # ----------------------------------------------------------------------------
    # TODO: Think about using dedicated coordinator to update values in local device.
    # Custom EntityDescrption can contain the key to update value in dictionary.
    # Coordinator need to determine if device is using local or global config.
    # self.coordinator.max_charging_current = value
    # await self.coordinator.update_configuration()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_NUMBER_LIST: tuple[
    tuple[str, SolarChargerEntityType, NumberEntityDescription], ...
] = (
    #####################################
    # Global defaults or local device entities
    # Hidden if not device entities, except for global defaults.
    # entity_category=EntityCategory.CONFIG
    #####################################
    # Used as local device entity for OCPP only. Others come with own entity.
    (
        OPTION_CHARGEE_CHARGE_LIMIT,
        SolarChargerEntityType.LOCAL_HIDDEN,
        NumberEntityDescription(
            key=OPTION_CHARGEE_CHARGE_LIMIT,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    # Used as local device entity for all except for OCPP. OCPP comes with own entity.
    (
        OPTION_CHARGER_MAX_CURRENT,
        SolarChargerEntityType.LOCAL_HIDDEN,
        NumberEntityDescription(
            key=OPTION_CHARGER_MAX_CURRENT,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    #####################################
    # Local device config or control entities
    # Must haves, ie. not hidden for all
    # entity_category=None
    # entity_category=EntityCategory.CONFIG
    #####################################
    (
        NUMBER_CHARGER_ALLOCATED_POWER,
        SolarChargerEntityType.LOCAL_AND_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGER_ALLOCATED_POWER,
            device_class=NumberDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            native_min_value=-23000.0,
            native_max_value=+23000.0,
        ),
    ),
    (
        NUMBER_CHARGER_MAX_SPEED,
        SolarChargerEntityType.LOCAL_DEFAULT,
        NumberEntityDescription(
            key=NUMBER_CHARGER_MAX_SPEED,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement="%/hr",
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGER_MIN_CURRENT,
        SolarChargerEntityType.LOCAL_DEFAULT,
        NumberEntityDescription(
            key=NUMBER_CHARGER_MIN_CURRENT,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
        SolarChargerEntityType.LOCAL_DEFAULT,
        NumberEntityDescription(
            key=NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    # Control entity
    (
        NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT,
        SolarChargerEntityType.LOCAL_DEFAULT,
        NumberEntityDescription(
            key=NUMBER_CHARGER_POWER_ALLOCATION_WEIGHT,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
        SolarChargerEntityType.LOCAL_DEFAULT,
        NumberEntityDescription(
            key=NUMBER_CHARGEE_MIN_CHARGE_LIMIT,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
        SolarChargerEntityType.LOCAL_DEFAULT,
        NumberEntityDescription(
            key=NUMBER_CHARGEE_MAX_CHARGE_LIMIT,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    #####################################
    # Global default config entities
    # Hidden except for global defaults
    # entity_category=EntityCategory.CONFIG
    #####################################
    (
        NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
            # translation_key=OPTION_CHARGER_EFFECTIVE_VOLTAGE,
            entity_category=EntityCategory.CONFIG,
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
        NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_SUNRISE_ELEVATION_START_TRIGGER,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=DEGREE,
            native_min_value=-90.0,
            native_max_value=+90.0,
        ),
    ),
    (
        NUMBER_SUNSET_ELEVATION_END_TRIGGER,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_SUNSET_ELEVATION_END_TRIGGER,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=DEGREE,
            native_min_value=-90.0,
            native_max_value=+90.0,
        ),
    ),
    (
        NUMBER_WAIT_CHARGEE_WAKEUP,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_WAIT_CHARGEE_WAKEUP,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        NUMBER_WAIT_CHARGEE_UPDATE_HA,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_WAIT_CHARGEE_UPDATE_HA,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_WAIT_CHARGEE_LIMIT_CHANGE,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        NUMBER_WAIT_CHARGER_ON,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_WAIT_CHARGER_ON,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        NUMBER_WAIT_CHARGER_OFF,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_WAIT_CHARGER_OFF,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        NUMBER_WAIT_CHARGER_AMP_CHANGE,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_WAIT_CHARGER_AMP_CHANGE,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    #####################################
    # Charge limits and end times
    #####################################
    (
        NUMBER_CHARGE_LIMIT_MONDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGE_LIMIT_MONDAY,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGE_LIMIT_TUESDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGE_LIMIT_TUESDAY,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGE_LIMIT_WEDNESDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGE_LIMIT_WEDNESDAY,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGE_LIMIT_THURSDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGE_LIMIT_THURSDAY,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGE_LIMIT_FRIDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGE_LIMIT_FRIDAY,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGE_LIMIT_SATURDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGE_LIMIT_SATURDAY,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        NUMBER_CHARGE_LIMIT_SUNDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        NumberEntityDescription(
            key=NUMBER_CHARGE_LIMIT_SUNDAY,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    #####################################
    # Diagnostic entities
    # entity_category=EntityCategory.DIAGNOSTIC
    #####################################
)


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

        # For both global default and charger subentries
        numbers: dict[str, SolarChargerNumberConfigEntity] = {}
        for config_item, entity_type, entity_description in CONFIG_NUMBER_LIST:
            if is_create_entity(subentry, entity_type):
                numbers[config_item] = SolarChargerNumberConfigEntity(
                    config_item,
                    subentry,
                    entity_type,
                    entity_description,
                    get_device_config_default_value(subentry, config_item),
                )

        if len(numbers) > 0:
            coordinator.charge_controls[subentry.subentry_id].numbers = numbers
            async_add_entities(
                numbers.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
