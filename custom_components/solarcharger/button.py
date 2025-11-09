"""SolarCharger button platform."""

from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    BUTTON,
    CONTROL_CHARGE_BUTTON,
    DOMAIN,
    ICON_START,
    SUBENTRY_TYPE_CHARGER,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerButtonEntity(SolarChargerEntity, ButtonEntity):
    """SolarCharger button entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        desc: ButtonEntityDescription,
        coordinator: SolarChargerCoordinator,
    ) -> None:
        """Initialize the SolarCharger button entity."""
        super().__init__(config_item, subentry)
        self.entity_description = desc

        self.set_entity_unique_id(BUTTON, config_item)
        self.set_entity_id(BUTTON, config_item)

        self._coordinator = coordinator


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerButtonCharge(SolarChargerButtonEntity):
    """Representation of a SolarCharger start button."""

    # _entity_key = CONTROL_CHARGE_BUTTON
    # _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = ICON_START
    _attr_entity_registry_enabled_default = False

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.async_start_charger(
            self._coordinator.charge_controls[self._subentry.subentry_id]
        )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
CONFIG_BUTTON_LIST: tuple[tuple[str, Any, ButtonEntityDescription], ...] = (
    #####################################
    # Button entities
    # entity_category=None
    #####################################
    (
        CONTROL_CHARGE_BUTTON,
        SolarChargerButtonCharge,
        ButtonEntityDescription(
            key=CONTROL_CHARGE_BUTTON,
        ),
    ),
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    # async_add_entities: Callable,
) -> None:
    """Set up buttons based on config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
            buttons: dict[str, SolarChargerButtonEntity] = {}

            for (
                config_item,
                cls,
                entity_description,
            ) in CONFIG_BUTTON_LIST:
                buttons[config_item] = cls(
                    config_item,
                    subentry,
                    entity_description,
                    coordinator,
                )
            coordinator.charge_controls[subentry.subentry_id].buttons = buttons

            async_add_entities(
                buttons.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
