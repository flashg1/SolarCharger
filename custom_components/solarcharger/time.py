"""SolarCharger time platform."""

from datetime import time
import logging

from homeassistant import config_entries, core
from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_utils import is_config_entity_used_as_local_device_entity
from .const import (
    DOMAIN,
    OPTION_CHARGE_ENDTIME_FRIDAY,
    OPTION_CHARGE_ENDTIME_MONDAY,
    OPTION_CHARGE_ENDTIME_SATURDAY,
    OPTION_CHARGE_ENDTIME_SUNDAY,
    OPTION_CHARGE_ENDTIME_THURSDAY,
    OPTION_CHARGE_ENDTIME_TUESDAY,
    OPTION_CHARGE_ENDTIME_WEDNESDAY,
    OPTION_GLOBAL_DEFAULTS_ID,
    TIME,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerTimeEntity(SolarChargerEntity, TimeEntity):
    """SolarCharger time entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: TimeEntityDescription,
    ) -> None:
        """Initialize the time."""
        SolarChargerEntity.__init__(self, config_item, subentry)
        self.set_entity_id(TIME, config_item)
        self.set_entity_unique_id(TIME, config_item)
        self.entity_description = desc

    # ----------------------------------------------------------------------------
    async def async_set_value(self, value: time) -> None:
        """Set new value."""
        self._attr_native_value = value
        self.update_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerTimeConfigEntity(SolarChargerTimeEntity):
    """SolarCharger configurable time entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: TimeEntityDescription,
        default_val: time = time.min,
    ) -> None:
        """Initialise datetime."""
        super().__init__(config_item, subentry, desc)

        if desc.entity_category == EntityCategory.CONFIG:
            # Disable local device entities. User needs to manually enable if required.
            if subentry.unique_id != OPTION_GLOBAL_DEFAULTS_ID:
                if not is_config_entity_used_as_local_device_entity(
                    subentry, config_item
                ):
                    self._attr_entity_registry_enabled_default = False

        self._attr_has_entity_name = True
        self._attr_native_value = default_val

    # ----------------------------------------------------------------------------
    async def async_set_native_value(self, value: time) -> None:
        """Set new value."""
        await super().async_set_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_DATETIME_LIST: tuple[tuple[str, TimeEntityDescription], ...] = (
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
        OPTION_CHARGE_ENDTIME_MONDAY,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_MONDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_TUESDAY,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_TUESDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_WEDNESDAY,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_WEDNESDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_THURSDAY,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_THURSDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_FRIDAY,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_FRIDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_SATURDAY,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_SATURDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_SUNDAY,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_SUNDAY,
            entity_category=EntityCategory.CONFIG,
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
    """Set up times based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        times = {}
        for config_item, entity_description in CONFIG_DATETIME_LIST:
            times[config_item] = SolarChargerTimeConfigEntity(
                config_item, subentry, entity_description
            )
        coordinator.charge_controls[subentry.subentry_id].times = times

        async_add_entities(
            times.values(),
            update_before_add=False,
            config_subentry_id=subentry.subentry_id,
        )
