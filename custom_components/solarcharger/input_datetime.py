"""SolarCharger time platform."""

from datetime import datetime, time
import logging

from homeassistant import config_entries, core
from homeassistant.components.input_datetime import (
    CONF_HAS_DATE,
    CONF_HAS_TIME,
    CONF_INITIAL,
    InputDatetime,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    ATTR_DATE,
    ATTR_EDITABLE,
    ATTR_TIME,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    INPUT_TIME,
    TIME_CHARGE_ENDTIME_FRIDAY,
    TIME_CHARGE_ENDTIME_MONDAY,
    TIME_CHARGE_ENDTIME_SATURDAY,
    TIME_CHARGE_ENDTIME_SUNDAY,
    TIME_CHARGE_ENDTIME_THURSDAY,
    TIME_CHARGE_ENDTIME_TUESDAY,
    TIME_CHARGE_ENDTIME_WEDNESDAY,
    TIME_DEFAULT_STR,
)
from .coordinator import SolarChargerCoordinator
from .entity import (
    SolarChargerEntity,
    SolarChargerEntityType,
    compose_entity_id,
    compose_entity_unique_id,
    is_create_entity,
)

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# class SolarChargerInputTimeEntity(SolarChargerInputDatetimeEntity):
class SolarChargerInputTimeEntity(SolarChargerEntity, InputDatetime):
    """SolarCharger input datetime entity class. Could not get this to work."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        conf_type: ConfigType,
    ) -> None:
        """Initialize the datetime."""

        # Unique id of the entity.
        # conf_type[CONF_ID] = compose_entity_unique_id(INPUT_TIME, subentry, config_item)
        # Entity id
        conf_type[CONF_ID] = compose_entity_id(
            INPUT_TIME, subentry.unique_id, config_item
        )
        InputDatetime.__init__(self, conf_type)
        self.editable = True

        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)

        self.set_entity_id(INPUT_TIME, config_item)
        self.set_entity_unique_id(INPUT_TIME, config_item)

    # ----------------------------------------------------------------------------
    async def async_set_value(self, value: datetime) -> None:
        """Set new value."""
        self._attr_native_value = value
        self.update_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerInputTimeConfigEntity(SolarChargerInputTimeEntity):
    """SolarCharger configurable time entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        conf_type: ConfigType,
        default_val: time = time.min,
    ) -> None:
        """Initialise datetime."""
        super().__init__(config_item, subentry, entity_type, conf_type)

        self._attr_has_entity_name = True
        self._attr_native_value = default_val

    # ----------------------------------------------------------------------------
    async def async_set_value(self, value: datetime) -> None:
        """Set new value."""
        await super().async_set_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_TIME_LIST: tuple[tuple[str, SolarChargerEntityType, ConfigType], ...] = (
    #####################################
    # Control entities
    # Must haves, ie. not hidden for all
    # entity_category=None
    #####################################
    #####################################
    # Config entities
    # Hidden except for global defaults
    # entity_category=EntityCategory.CONFIG
    #####################################
    (
        TIME_CHARGE_ENDTIME_MONDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        {
            CONF_NAME: TIME_CHARGE_ENDTIME_MONDAY,
            CONF_HAS_DATE: False,
            CONF_HAS_TIME: True,
            CONF_INITIAL: TIME_DEFAULT_STR,
        },
    ),
    (
        TIME_CHARGE_ENDTIME_TUESDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        {
            CONF_NAME: TIME_CHARGE_ENDTIME_TUESDAY,
            CONF_HAS_DATE: False,
            CONF_HAS_TIME: True,
            CONF_INITIAL: TIME_DEFAULT_STR,
        },
    ),
    (
        TIME_CHARGE_ENDTIME_WEDNESDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        {
            CONF_NAME: TIME_CHARGE_ENDTIME_WEDNESDAY,
            CONF_HAS_DATE: False,
            CONF_HAS_TIME: True,
            CONF_INITIAL: TIME_DEFAULT_STR,
        },
    ),
    (
        TIME_CHARGE_ENDTIME_THURSDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        {
            CONF_NAME: TIME_CHARGE_ENDTIME_THURSDAY,
            CONF_HAS_DATE: False,
            CONF_HAS_TIME: True,
            CONF_INITIAL: TIME_DEFAULT_STR,
        },
    ),
    (
        TIME_CHARGE_ENDTIME_FRIDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        {
            CONF_NAME: TIME_CHARGE_ENDTIME_FRIDAY,
            CONF_HAS_DATE: False,
            CONF_HAS_TIME: True,
            CONF_INITIAL: TIME_DEFAULT_STR,
        },
    ),
    (
        TIME_CHARGE_ENDTIME_SATURDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        {
            CONF_NAME: TIME_CHARGE_ENDTIME_SATURDAY,
            CONF_HAS_DATE: False,
            CONF_HAS_TIME: True,
            CONF_INITIAL: TIME_DEFAULT_STR,
        },
    ),
    (
        TIME_CHARGE_ENDTIME_SUNDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        {
            CONF_NAME: TIME_CHARGE_ENDTIME_SUNDAY,
            CONF_HAS_DATE: False,
            CONF_HAS_TIME: True,
            CONF_INITIAL: TIME_DEFAULT_STR,
        },
    ),
    #####################################
    # Diagnostic entities
    # entity_category=EntityCategory.DIAGNOSTIC
    #####################################
)


# ----------------------------------------------------------------------------
# input_datetime only has async_setup(hass: HomeAssistant, config: ConfigType),
# not async_setup_entry().  ConfigType has complete list of entities to create.


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up times based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    _LOGGER.warning("Creating input_datetime entities")

    for subentry in config_entry.subentries.values():
        # For both global default and charger subentries
        input_times: dict[str, SolarChargerInputTimeConfigEntity] = {}
        for config_item, entity_type, conf_type in CONFIG_TIME_LIST:
            if is_create_entity(subentry, entity_type):
                input_times[config_item] = SolarChargerInputTimeConfigEntity(
                    config_item, subentry, entity_type, conf_type
                )

        if len(input_times) > 0:
            coordinator.charge_controls[subentry.subentry_id].input_times = input_times
            async_add_entities(
                input_times.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
