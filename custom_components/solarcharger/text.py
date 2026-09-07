"""SolarCharger text platform."""

import logging

from homeassistant.components.text import RestoreText, TextEntityDescription
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .config.config_utils import get_device_config_default_value
from .const import DOMAIN, ENTITY_CHARGER_STEP_CURRENT_LIST, TEXT
from .entity import (
    SolarChargerEntity,
    SolarChargerEntityType,
    get_single_entity_type,
    is_create_entity,
)
from .modules.coordinator import SolarChargerCoordinator

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerTextEntity(SolarChargerEntity, RestoreText):
    """SolarCharger text entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: TextEntityDescription,
        default_val: str | None,
    ) -> None:
        """Initialize the text."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(TEXT, config_item)
        self.set_entity_unique_id(TEXT, config_item)
        self.entity_description = desc

        # Fallback value if no restored data exists
        self._current_value = default_val

    # ----------------------------------------------------------------------------
    @property
    def native_value(self) -> str:
        """Return the current value stored in the text entity."""
        return self._current_value

    # ----------------------------------------------------------------------------
    def set_value(self, value: str) -> None:
        """Update the stored string value from a UI or service interaction."""

        self._current_value = value

        # Should force state update here, otherwise update by polling only and be delayed by few seconds.
        # self.schedule_update_ha_state()
        self.update_ha_state()

    # ----------------------------------------------------------------------------
    # Note: If your backend updates asynchronously (e.g., via HTTP client), use:
    # async def async_set_value(self, value: str) -> None:
    #     self._current_value = value
    #     self.async_write_ha_state()

    # ----------------------------------------------------------------------------
    async def async_added_to_hass(self) -> None:
        """Handle entity which is about to be added to Home Assistant."""

        await super().async_added_to_hass()

        # Check the Home Assistant storage registry for previous state data
        if (old_text_data := await self.async_get_last_text_data()) is not None:
            # Safely restore the native value string
            self._current_value = old_text_data.native_value


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_TEXT_LIST: tuple[
    tuple[
        str,
        SolarChargerEntityType | list[SolarChargerEntityType],
        TextEntityDescription,
    ],
    ...,
] = (
    #####################################
    # Local non-overridable entities
    # Must haves, ie. not hidden for all
    # entity_category=EntityCategory.CONFIG
    #####################################
    #####################################
    # Global defaults or local device entities
    # Hidden if not device entities, except for global defaults.
    # entity_category=EntityCategory.CONFIG
    #####################################
    # Used as local device entity for OCPP only. Others come with own entity.
    (
        ENTITY_CHARGER_STEP_CURRENT_LIST,
        [
            SolarChargerEntityType.TYPE_LOCAL_BYD_VEHICLE,
            SolarChargerEntityType.TYPE_LOCAL_GWM_ORA,
            SolarChargerEntityType.TYPE_LOCAL_GEELY_CONNECT,
            SolarChargerEntityType.TYPE_LOCAL_VOLVO,
            SolarChargerEntityType.TYPE_LOCAL_MG_SAIC,
            SolarChargerEntityType.TYPE_LOCAL_USER_CUSTOM,
        ],
        TextEntityDescription(
            key=ENTITY_CHARGER_STEP_CURRENT_LIST,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up texts based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        # For both global default and charger subentries
        texts: dict[str, SolarChargerTextEntity] = {}
        for config_item, entity_type_or_list, entity_description in CONFIG_TEXT_LIST:
            if is_create_entity(subentry, entity_type_or_list):
                single_entity_type = get_single_entity_type(
                    subentry, entity_type_or_list
                )
                texts[config_item] = SolarChargerTextEntity(
                    config_item,
                    subentry,
                    single_entity_type,
                    entity_description,
                    get_device_config_default_value(subentry, config_item),
                )

        if len(texts) > 0:
            coordinator.device_controls[
                subentry.subentry_id
            ].controller.charge_control.entities.texts = texts
            async_add_entities(
                texts.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
