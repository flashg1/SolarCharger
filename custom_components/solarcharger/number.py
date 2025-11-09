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

from .const import (
    CONTROL_CHARGER_ALLOCATED_POWER,
    DOMAIN,
    NUMBER,
    OPTION_CHARGEE_CHARGE_LIMIT,
    OPTION_CHARGER_EFFECTIVE_VOLTAGE,
    OPTION_CHARGER_MAX_CURRENT,
    OPTION_CHARGER_MAX_SPEED,
    OPTION_CHARGER_MIN_CURRENT,
    OPTION_CHARGER_MIN_WORKABLE_CURRENT,
    OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
    OPTION_GLOBAL_DEFAULT_VALUES,
    OPTION_GLOBAL_DEFAULTS_ID,
    OPTION_SUNRISE_ELEVATION_START_TRIGGER,
    OPTION_SUNSET_ELEVATION_END_TRIGGER,
    OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
    OPTION_WAIT_CHARGEE_UPDATE_HA,
    OPTION_WAIT_CHARGEE_WAKEUP,
    OPTION_WAIT_CHARGER_AMP_CHANGE,
    OPTION_WAIT_CHARGER_OFF,
    OPTION_WAIT_CHARGER_ON,
    OPTION_WAIT_NET_POWER_UPDATE,
    SUBENTRY_THIRDPARTY_DOMAIN,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity
from .helpers.general import is_config_entity_used_as_local_device_entity

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
CONFIG_NUMBER_LIST: tuple[tuple[str, NumberEntityDescription], ...] = (
    #####################################
    # Control entities
    # Must haves, ie. not hidden for all
    # entity_category=None
    #####################################
    (
        CONTROL_CHARGER_ALLOCATED_POWER,
        NumberEntityDescription(
            key=CONTROL_CHARGER_ALLOCATED_POWER,
            device_class=NumberDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.WATT,
            native_min_value=-23000.0,
            native_max_value=+23000.0,
        ),
    ),
    #####################################
    # Config entities, or device entities
    # Hidden if not device entities, except for global defaults.
    # entity_category=EntityCategory.CONFIG
    #####################################
    (
        OPTION_CHARGEE_CHARGE_LIMIT,
        NumberEntityDescription(
            key=OPTION_CHARGEE_CHARGE_LIMIT,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=PERCENTAGE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_MAX_CURRENT,
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
    # Config entities
    # Hidden except for global defaults
    # entity_category=EntityCategory.CONFIG
    #####################################
    (
        OPTION_CHARGER_EFFECTIVE_VOLTAGE,
        NumberEntityDescription(
            key=OPTION_CHARGER_EFFECTIVE_VOLTAGE,
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
        OPTION_CHARGER_MAX_SPEED,
        NumberEntityDescription(
            key=OPTION_CHARGER_MAX_SPEED,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement="%/hr",
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_MIN_CURRENT,
        NumberEntityDescription(
            key=OPTION_CHARGER_MIN_CURRENT,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_MIN_WORKABLE_CURRENT,
        NumberEntityDescription(
            key=OPTION_CHARGER_MIN_WORKABLE_CURRENT,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
        NumberEntityDescription(
            key=OPTION_CHARGER_POWER_ALLOCATION_WEIGHT,
            entity_category=EntityCategory.CONFIG,
            native_min_value=0.0,
            native_max_value=100.0,
        ),
    ),
    (
        OPTION_SUNRISE_ELEVATION_START_TRIGGER,
        NumberEntityDescription(
            key=OPTION_SUNRISE_ELEVATION_START_TRIGGER,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=DEGREE,
            native_min_value=-90.0,
            native_max_value=+90.0,
        ),
    ),
    (
        OPTION_SUNSET_ELEVATION_END_TRIGGER,
        NumberEntityDescription(
            key=OPTION_SUNSET_ELEVATION_END_TRIGGER,
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=DEGREE,
            native_min_value=-90.0,
            native_max_value=+90.0,
        ),
    ),
    (
        OPTION_WAIT_NET_POWER_UPDATE,
        NumberEntityDescription(
            key=OPTION_WAIT_NET_POWER_UPDATE,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGEE_WAKEUP,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGEE_WAKEUP,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGEE_UPDATE_HA,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGEE_UPDATE_HA,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGER_ON,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGER_ON,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGER_OFF,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGER_OFF,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGER_AMP_CHANGE,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGER_AMP_CHANGE,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    #####################################
    # Diagnostic entities
    # entity_category=EntityCategory.DIAGNOSTIC
    #####################################
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerNumberEntity(SolarChargerEntity, RestoreNumber):
    """SolarCharger number entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: NumberEntityDescription,
    ) -> None:
        """Initialize the number."""

        super().__init__(config_item, subentry)
        self.entity_description = desc

        self.set_entity_unique_id(NUMBER, self._entity_key)
        self.set_entity_id(NUMBER, self._entity_key)

    # ----------------------------------------------------------------------------
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        self._attr_native_value = value

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
        desc: NumberEntityDescription,
        default_val: float,
    ) -> None:
        """Initialise number."""
        super().__init__(config_item, subentry, desc)

        if desc.entity_category == EntityCategory.CONFIG:
            # Disable local device entities. User needs to manually enable if required.
            if subentry.unique_id != OPTION_GLOBAL_DEFAULTS_ID:
                if not is_config_entity_used_as_local_device_entity(
                    subentry.data.get(SUBENTRY_THIRDPARTY_DOMAIN), config_item
                ):
                    self._attr_entity_registry_enabled_default = False

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

        # TODO: Think about using dedicated coordinator to update values in local device.
        # Custom EntityDescrption can contain the key to update value in dictionary.
        # Coordinator need to determine if device is using local or global config.
        # self.coordinator.max_charging_current = value
        # await self.coordinator.update_configuration()


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
        # if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
        #     numbers = async_init_charger_numbers(coordinator, subentry)
        # elif subentry.subentry_type == SUBENTRY_TYPE_DEFAULTS:
        #     numbers = async_init_global_default_numbers(coordinator, subentry)
        # else:
        #     continue

        numbers = {}
        for config_item, entity_description in CONFIG_NUMBER_LIST:
            numbers[config_item] = SolarChargerNumberConfigEntity(
                config_item,
                subentry,
                entity_description,
                # TODO: Set default value using CHARGE_API_DEFAULT_VALUES
                OPTION_GLOBAL_DEFAULT_VALUES[config_item],
            )
        coordinator.charge_controls[subentry.subentry_id].numbers = numbers

        async_add_entities(
            numbers.values(),
            update_before_add=False,
            config_subentry_id=subentry.subentry_id,
        )
