"""SolarCharger datetime platform."""

from datetime import datetime, timezone
import logging
from zoneinfo import ZoneInfo

from homeassistant import config_entries, core
from homeassistant.components.datetime import DateTimeEntity, DateTimeEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

# from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATETIME, DATETIME_NEXT_CHARGE_TIME, DOMAIN
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerDateTimeEntity(SolarChargerEntity, DateTimeEntity, RestoreEntity):
    """SolarCharger datetime entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: DateTimeEntityDescription,
    ) -> None:
        """Initialize the datetime."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(DATETIME, config_item)
        self.set_entity_unique_id(DATETIME, config_item)
        self.entity_description = desc

    # ----------------------------------------------------------------------------
    async def async_set_value(self, value: datetime) -> None:
        """Set new value."""
        self._attr_native_value = value
        self.update_ha_state()

    # ----------------------------------------------------------------------------
    # See https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-event-setup/
    async def async_added_to_hass(self) -> None:
        """Entity about to be added to hass. Restore state and subscribe for events here if needed."""

        await super().async_added_to_hass()

        if (
            last_state := await self.async_get_last_state()
        ) is not None and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            # Stored string is in ISO format UTC (eg. 2025-12-28T05:51:05+00:00).
            # Convert to local timezone (eg. 2025-12-28 16:51:05+11:00)
            await self.async_set_value(
                datetime.fromisoformat(last_state.state).astimezone(
                    ZoneInfo(self.hass.config.time_zone)
                )
            )


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
        entity_type: SolarChargerEntityType,
        desc: DateTimeEntityDescription,
        default_val: datetime = datetime.min.replace(tzinfo=timezone.utc),
        # default_val: datetime = datetime.min.astimezone(),
        # default_val: datetime = datetime.min.replace(tzinfo=ZoneInfo(self._hass.config.time_zone))
    ) -> None:
        """Initialise datetime."""
        super().__init__(config_item, subentry, entity_type, desc)

        # if desc.entity_category == EntityCategory.CONFIG:
        #     # Disable local device entities. User needs to manually enable if required.
        #     if subentry.unique_id != OPTION_GLOBAL_DEFAULTS_ID:
        #         if not is_config_entity_used_as_local_device_entity(
        #             subentry, config_item
        #         ):
        #             self._attr_entity_registry_enabled_default = False

        self._attr_has_entity_name = True
        self._attr_native_value = default_val

    # ----------------------------------------------------------------------------
    async def async_set_native_value(self, value: datetime) -> None:
        """Set new value."""
        await super().async_set_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_DATETIME_LIST: tuple[
    tuple[str, SolarChargerEntityType, DateTimeEntityDescription], ...
] = (
    #####################################
    # Control entities
    # Must haves, ie. not hidden for all
    # entity_category=None
    #####################################
    (
        DATETIME_NEXT_CHARGE_TIME,
        SolarChargerEntityType.TYPE_LOCAL,
        DateTimeEntityDescription(
            key=DATETIME_NEXT_CHARGE_TIME,
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
        # For both global default and charger subentries
        datetimes: dict[str, SolarChargerDateTimeConfigEntity] = {}
        for config_item, entity_type, entity_description in CONFIG_DATETIME_LIST:
            if is_create_entity(subentry, entity_type):
                datetimes[config_item] = SolarChargerDateTimeConfigEntity(
                    config_item, subentry, entity_type, entity_description
                )

        if len(datetimes) > 0:
            coordinator.device_controls[
                subentry.subentry_id
            ].controller.charge_control.datetimes = datetimes
            async_add_entities(
                datetimes.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
