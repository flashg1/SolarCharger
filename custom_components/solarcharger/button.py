"""SolarCharger button platform."""

from homeassistant import config_entries, core
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .const import (
    BUTTON,
    DOMAIN,
    ENTITY_KEY_CHARGE_BUTTON,
    ICON_START,
    SUBENTRY_TYPE_CHARGER,
)
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity


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
            entities = []
            entities.append(SolarChargerButtonCharge(subentry, coordinator))
            async_add_entities(
                entities,
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerButtonEntity(SolarChargerEntity, ButtonEntity):
    """SolarCharger button entity."""

    def __init__(
        self,
        subentry: ConfigSubentry,
        coordinator: SolarChargerCoordinator,
    ) -> None:
        """Initialize the SolarCharger button entity."""

        super().__init__(subentry)
        self._coordinator = coordinator
        # id_name = self._entity_key.replace("_", "").lower()
        id_name = slugify(f"{self._entity_key}")
        self._attr_unique_id = (
            f"{subentry.subentry_id}.{subentry.unique_id}.{BUTTON}.{id_name}"
        )
        self.set_entity_id(BUTTON, self._entity_key)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerButtonCharge(SolarChargerButtonEntity):
    """Representation of a SolarCharger start button."""

    _entity_key = ENTITY_KEY_CHARGE_BUTTON
    _attr_icon = ICON_START
    # _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Press the button."""
        await self._coordinator.async_start_charger(
            self._coordinator.charge_controls[self._subentry.subentry_id]
        )
