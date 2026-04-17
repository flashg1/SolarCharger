"""SolarCharger select platform."""

from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.select import (
    ENTITY_ID_FORMAT,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .config_utils import get_device_config_default_value
from .const import (
    DOMAIN,
    # RESTORE_ON_START_FALSE,
    RESTORE_ON_START_TRUE,
    SELECT,
    SELECT_DEVICE_PRESENCE_SENSOR,
    SELECT_NONE,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSelectEntity(SolarChargerEntity, SelectEntity, RestoreEntity):
    """SolarCharger select base entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SelectEntityDescription,
        default_val: str,
        is_restore_state: bool,
    ) -> None:
        """Initialize the SolarCharger select entity."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(SELECT, config_item)
        self.set_entity_unique_id(SELECT, config_item)
        self.entity_description = desc

        self._default_val = default_val
        self._is_restore_state = is_restore_state

    # ----------------------------------------------------------------------------
    async def async_select_option(self, option: str) -> None:
        """Update the selected option and save it."""

        if option == SELECT_NONE:
            self._attr_current_option = None
        else:
            self._attr_current_option = option

        self.update_ha_state()

        # # Persist the choice to the Config Entry
        # # We copy the existing options and add/update our key
        # new_options = dict(self.config_entry.options)
        # new_options["selected_sensor"] = option

        # self.hass.config_entries.async_update_entry(
        #     self.config_entry,
        #     options=new_options
        # )

    # ----------------------------------------------------------------------------
    # See https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-event-setup/
    async def async_added_to_hass(self) -> None:
        """Entity about to be added to hass. Restore state and subscribe for events here if needed."""

        await super().async_added_to_hass()

        self._attr_current_option = self._default_val
        if self._is_restore_state:
            restored: State | None = await self.async_get_last_state()
            if restored is not None:
                self._attr_current_option = restored.state

        self.update_ha_state()

    #     # Listen for registry changes to refresh the list
    #     self.async_on_remove(
    #         self.hass.bus.async_listen(
    #             er.EVENT_ENTITY_REGISTRY_UPDATED,
    #             self._handle_registry_update
    #         )
    #     )

    # @callback
    # def _handle_registry_update(self, event) -> None:
    #     """Clear the cache and tell the UI to refresh."""
    #     # Check if the cache exists before trying to delete it
    #     if "options" in self.__dict__:
    #         del self.__dict__["options"]

    #     # This triggers Home Assistant to re-read the property
    #     self.async_write_ha_state()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSelectPresenceSensorEntity(SolarChargerSelectEntity):
    """Representation of a SolarCharger presence sensor selector."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SelectEntityDescription,
        default_val: str,
        is_restore_state: bool,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            config_item,
            subentry,
            entity_type,
            desc,
            default_val,
            is_restore_state,
        )

    # ----------------------------------------------------------------------------
    # More efficient to use @cached_property, but need to clear the cache when registry updates.
    # See above commented code.
    # OK for now since only get new list when changing config in GUI, so just override the options property without caching.
    # See https://developers.home-assistant.io/docs/core/entity/cached-property/
    @property
    def options(self) -> list[str]:  # type: ignore[override]
        """Return a filtered list of entity IDs."""

        registry = er.async_get(self.hass)

        # # Filter for sensors and return their entity_ids
        # return [
        #     entry.entity_id
        #     for entry in registry.entities.values()
        #     if entry.domain == "binary_sensor"
        # ]

        target_classes = {BinarySensorDeviceClass.CONNECTIVITY}
        filtered_entities = []

        for entry in registry.entities.values():
            # 1. Ensure it is a binary sensor
            if entry.domain != "binary_sensor":
                continue

            # 2. Check Device Class from the Registry (static configuration)
            reg_class = entry.device_class or entry.original_device_class

            # 3. Check Device Class from the State (live state)
            state = self.hass.states.get(entry.entity_id)
            state_class = state.attributes.get("device_class") if state else None

            if reg_class in target_classes or state_class in target_classes:
                filtered_entities.append(entry.entity_id)

        return [SELECT_NONE, *sorted(filtered_entities)]


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_SELECT_LIST: tuple[
    tuple[
        str,
        Any,
        bool,
        SolarChargerEntityType,
        SelectEntityDescription,
    ],
    ...,
] = (
    #####################################
    # Control:  entity_category=None
    # Config:   entity_category=EntityCategory.CONFIG
    # Diagnostic: entity_category=EntityCategory.DIAGNOSTIC
    #####################################
    (
        SELECT_DEVICE_PRESENCE_SENSOR,
        SolarChargerSelectPresenceSensorEntity,
        RESTORE_ON_START_TRUE,
        SolarChargerEntityType.TYPE_LOCAL,
        SelectEntityDescription(
            key=SELECT_DEVICE_PRESENCE_SENSOR,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
)


# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        # For global defaults and charger subentries
        selects: dict[str, SolarChargerSelectEntity] = {}

        for (
            config_item,
            cls,
            is_restore_state,
            entity_type,
            entity_description,
        ) in CONFIG_SELECT_LIST:
            if is_create_entity(subentry, entity_type):
                selects[config_item] = cls(
                    config_item,
                    subentry,
                    entity_type,
                    entity_description,
                    get_device_config_default_value(subentry, config_item),
                    is_restore_state,
                )

        if len(selects) > 0:
            coordinator.device_controls[
                subentry.subentry_id
            ].controller.charge_control.entities.selects = selects
            async_add_entities(
                selects.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
