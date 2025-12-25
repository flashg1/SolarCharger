"""SolarCharger datetime platform."""

from datetime import datetime, timezone
import logging

from homeassistant import config_entries, core
from homeassistant.components.datetime import DateTimeEntity, DateTimeEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_utils import is_config_entity_used_as_local_device_entity
from .const import (
    DATETIME,
    DOMAIN,
    OPTION_GLOBAL_DEFAULTS_ID,
    OPTION_NEXT_CHARGE_TIME_TRIGGER,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerDateTimeEntity(SolarChargerEntity, DateTimeEntity):
    """SolarCharger datetime entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: DateTimeEntityDescription,
    ) -> None:
        """Initialize the datetime."""
        SolarChargerEntity.__init__(self, config_item, subentry)
        self.set_entity_id(DATETIME, config_item)
        self.set_entity_unique_id(DATETIME, config_item)
        self.entity_description = desc

    # ----------------------------------------------------------------------------
    async def async_set_value(self, value: datetime) -> None:
        """Set new value."""
        self._attr_native_value = value
        self.update_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerDateTimeConfigEntity(SolarChargerDateTimeEntity):
    """SolarCharger configurable datetime entity.

    See https://developers.home-assistant.io/docs/core/entity/datetime
    """

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: DateTimeEntityDescription,
        default_val: datetime = datetime.min.replace(tzinfo=timezone.utc),
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
    async def async_set_native_value(self, value: datetime) -> None:
        """Set new value."""
        await super().async_set_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_DATETIME_LIST: tuple[tuple[str, DateTimeEntityDescription], ...] = (
    #####################################
    # Control entities
    # Must haves, ie. not hidden for all
    # entity_category=None
    #####################################
    (
        OPTION_NEXT_CHARGE_TIME_TRIGGER,
        DateTimeEntityDescription(
            key=OPTION_NEXT_CHARGE_TIME_TRIGGER,
        ),
    ),
    #####################################
    # Config entities
    # Hidden except for global defaults
    # entity_category=EntityCategory.CONFIG
    #####################################
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
    """Set up datetimes based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        datetimes = {}
        for config_item, entity_description in CONFIG_DATETIME_LIST:
            datetimes[config_item] = SolarChargerDateTimeConfigEntity(
                config_item, subentry, entity_description
            )
        coordinator.charge_controls[subentry.subentry_id].datetimes = datetimes

        async_add_entities(
            datetimes.values(),
            update_before_add=False,
            config_subentry_id=subentry.subentry_id,
        )
