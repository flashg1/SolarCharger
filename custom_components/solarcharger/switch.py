"""SolarCharger button platform."""

from typing import TYPE_CHECKING, Any

from homeassistant import config_entries, core
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_ON
from homeassistant.core import State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from .const import DOMAIN, ENTITY_KEY_CHARGE_SWITCH, SUBENTRY_TYPE_CHARGER, SWITCH
from .entity import SolarChargerEntity

if TYPE_CHECKING:
    from .coordinator import SolarChargerCoordinator


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    # async_add_entities: Callable,
) -> None:
    """Set up buttons based on config entry."""
    coordinator: "SolarChargerCoordinator" = hass.data[DOMAIN][config_entry.entry_id]

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
            switches: dict[str, SolarChargerSwitchEntity] = {}
            switches[ENTITY_KEY_CHARGE_SWITCH] = SolarChargerSwitchCharge(
                subentry, coordinator
            )
            coordinator.charge_controls[subentry.subentry_id].switches = switches

            async_add_entities(
                switches.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# class SolarChargerSwitchEntity(SolarChargerEntity, SwitchEntity, RestoreEntity):
class SolarChargerSwitchEntity(SolarChargerEntity, SwitchEntity, RestoreEntity):
    """SolarCharger switch base entity."""

    def __init__(
        self,
        subentry: ConfigSubentry,
        coordinator: "SolarChargerCoordinator",
        is_restore_state: bool = True,
    ) -> None:
        """Initialize the SolarCharger switch entity."""

        super().__init__(subentry)
        self._coordinator = coordinator
        self._is_restore_state = is_restore_state

        # id_name = self._entity_key.replace("_", "").lower()
        # self._attr_unique_id = f"{subentry.subentry_id}.{SWITCH}.{id_name}"
        id_name = slugify(f"{self._entity_key}")
        self._attr_unique_id = (
            f"{subentry.subentry_id}.{subentry.unique_id}.{SWITCH}.{id_name}"
        )

        self.set_entity_id(SWITCH, self._entity_key)

    # ----------------------------------------------------------------------------
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        if self._is_restore_state:
            restored: State | None = await self.async_get_last_state()
            if restored is not None:
                if restored.state == STATE_ON:
                    await self.async_turn_on()
                else:
                    await self.async_turn_off()


# ----------------------------------------------------------------------------
# Do not restore switch setting on reboot, otherwise can hold up startup until charging is completed.
# ----------------------------------------------------------------------------
class SolarChargerSwitchCharge(SolarChargerSwitchEntity):
    """Representation of a SolarCharger start switch."""

    _entity_key = ENTITY_KEY_CHARGE_SWITCH

    def __init__(
        self,
        subentry: ConfigSubentry,
        coordinator: "SolarChargerCoordinator",
    ) -> None:
        """Initialize the switch."""
        super().__init__(subentry, coordinator, is_restore_state=False)
        if self.is_on is None:
            self._attr_is_on = False
            self.update_ha_state()

        self._coordinator.charge_controls[
            self._subentry.subentry_id
        ].switch_charge = self.is_on

    # ----------------------------------------------------------------------------
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await super().async_turn_on(**kwargs)
        await self._coordinator.switch_charge_update(
            self._coordinator.charge_controls[self._subentry.subentry_id], True
        )

    # ----------------------------------------------------------------------------
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await super().async_turn_off(**kwargs)
        await self._coordinator.switch_charge_update(
            self._coordinator.charge_controls[self._subentry.subentry_id], False
        )
