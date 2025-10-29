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
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    NUMBER,
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
CONFIG_NUMBER_LIST: tuple[tuple[str, float, NumberEntityDescription], ...] = (
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
        OPTION_SUNRISE_ELEVATION_START_TRIGGER,
        3,
        NumberEntityDescription(
            key=OPTION_SUNRISE_ELEVATION_START_TRIGGER,
            native_unit_of_measurement=DEGREE,
            native_min_value=-90.0,
            native_max_value=+90.0,
        ),
    ),
    (
        OPTION_SUNSET_ELEVATION_END_TRIGGER,
        6,
        NumberEntityDescription(
            key=OPTION_SUNSET_ELEVATION_END_TRIGGER,
            native_unit_of_measurement=DEGREE,
            native_min_value=-90.0,
            native_max_value=+90.0,
        ),
    ),
    (
        OPTION_WAIT_NET_POWER_UPDATE,
        60,
        NumberEntityDescription(
            key=OPTION_WAIT_NET_POWER_UPDATE,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGEE_WAKEUP,
        40,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGEE_WAKEUP,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGEE_UPDATE_HA,
        5,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGEE_UPDATE_HA,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
        5,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGEE_LIMIT_CHANGE,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGER_ON,
        11,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGER_ON,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGER_OFF,
        5,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGER_OFF,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
    (
        OPTION_WAIT_CHARGER_AMP_CHANGE,
        1,
        NumberEntityDescription(
            key=OPTION_WAIT_CHARGER_AMP_CHANGE,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=1.0,
            native_max_value=600.0,
        ),
    ),
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
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
        self._attr_has_entity_name = True
        # Must set _attr_should_poll=True (default) for HA to register value changes
        # self._attr_should_poll = False

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
