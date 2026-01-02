"""SolarCharger time platform."""

from datetime import time
import logging

from homeassistant import config_entries, core
from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    OPTION_CHARGE_ENDTIME_FRIDAY,
    OPTION_CHARGE_ENDTIME_MONDAY,
    OPTION_CHARGE_ENDTIME_SATURDAY,
    OPTION_CHARGE_ENDTIME_SUNDAY,
    OPTION_CHARGE_ENDTIME_THURSDAY,
    OPTION_CHARGE_ENDTIME_TUESDAY,
    OPTION_CHARGE_ENDTIME_WEDNESDAY,
    TIME,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerTimeEntity(SolarChargerEntity, TimeEntity, RestoreEntity):
    """SolarCharger time entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: TimeEntityDescription,
    ) -> None:
        """Initialize the time."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(TIME, config_item)
        self.set_entity_unique_id(TIME, config_item)
        self.entity_description = desc

    # ----------------------------------------------------------------------------
    async def async_set_value(self, value: time) -> None:
        """Set new value."""
        self._attr_native_value = value
        self.update_ha_state()

    # ----------------------------------------------------------------------------
    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            last_state := await self.async_get_last_state()
        ) is not None and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            await self.async_set_value(time.fromisoformat(last_state.state))


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerTimeConfigEntity(SolarChargerTimeEntity):
    """SolarCharger configurable time entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: TimeEntityDescription,
        default_val: time = time.min,
    ) -> None:
        """Initialise datetime."""
        super().__init__(config_item, subentry, entity_type, desc)

        self._attr_has_entity_name = True
        self._attr_native_value = default_val

    # ----------------------------------------------------------------------------
    async def async_set_value(self, value: time) -> None:
        """Set new value."""
        await super().async_set_value(value)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_TIME_LIST: tuple[
    tuple[str, SolarChargerEntityType, TimeEntityDescription], ...
] = (
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
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_MONDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_TUESDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_TUESDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_WEDNESDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_WEDNESDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_THURSDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_THURSDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_FRIDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_FRIDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_SATURDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
        TimeEntityDescription(
            key=OPTION_CHARGE_ENDTIME_SATURDAY,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    (
        OPTION_CHARGE_ENDTIME_SUNDAY,
        SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
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
        # For both global default and charger subentries
        times: dict[str, SolarChargerTimeConfigEntity] = {}
        for config_item, entity_type, entity_description in CONFIG_TIME_LIST:
            if is_create_entity(subentry, entity_type):
                times[config_item] = SolarChargerTimeConfigEntity(
                    config_item, subentry, entity_type, entity_description
                )

        if len(times) > 0:
            coordinator.charge_controls[subentry.subentry_id].times = times
            async_add_entities(
                times.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
