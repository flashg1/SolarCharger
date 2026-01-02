"""SolarCharger button platform."""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries, core
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_ON
from homeassistant.core import State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .config_utils import get_device_config_default_value
from .const import (
    DOMAIN,
    RESTORE_ON_START_FALSE,
    RESTORE_ON_START_TRUE,
    SUBENTRY_TYPE_CHARGER,
    SWITCH,
    SWITCH_FAST_CHARGE_MODE,
    SWITCH_PLUGIN_TRIGGER,
    SWITCH_SCHEDULE_CHARGE,
    SWITCH_START_CHARGE,
    SWITCH_SUN_TRIGGER,
)
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity
from .model_control import ChargeControl

type SWITCH_ACTION_TYPE = Callable[[ChargeControl, bool], Coroutine[Any, Any, None]]

if TYPE_CHECKING:
    from .coordinator import SolarChargerCoordinator

# Examples:
# homeassistant/components/netgear/switch.py
# homeassistant/components/ring/switch.py
# homeassistant/components/sun/sensor.py


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSwitchEntity(SolarChargerEntity, SwitchEntity, RestoreEntity):
    """SolarCharger switch base entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SwitchEntityDescription,
        coordinator: "SolarChargerCoordinator",
        default_val: bool,
        is_restore_state: bool,
        action: SWITCH_ACTION_TYPE,
    ) -> None:
        """Initialize the SolarCharger switch entity."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(SWITCH, config_item)
        self.set_entity_unique_id(SWITCH, config_item)
        self.entity_description = desc

        # self._attr_has_entity_name = True
        self._coordinator = coordinator
        self._default_val = default_val
        self._is_restore_state = is_restore_state
        self._action = action

    # ----------------------------------------------------------------------------
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True

    # ----------------------------------------------------------------------------
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False

    # ----------------------------------------------------------------------------
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True

    # ----------------------------------------------------------------------------
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False

    # ----------------------------------------------------------------------------
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        turn_on = self._default_val

        if self._is_restore_state:
            restored: State | None = await self.async_get_last_state()
            if restored is not None:
                turn_on = restored.state == STATE_ON

        if turn_on:
            await self.async_turn_on()
        else:
            await self.async_turn_off()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerSwitchAction(SolarChargerSwitchEntity):
    """Representation of a SolarCharger switch."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SwitchEntityDescription,
        coordinator: "SolarChargerCoordinator",
        default_val: bool,
        is_restore_state: bool,
        action: SWITCH_ACTION_TYPE,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            config_item,
            subentry,
            entity_type,
            desc,
            coordinator,
            default_val,
            is_restore_state,
            action,
        )

    # ----------------------------------------------------------------------------
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""

        if not self.is_on:
            await super().async_turn_on(**kwargs)
            await self._action(
                self._coordinator.charge_controls[self._subentry.subentry_id], True
            )

    # ----------------------------------------------------------------------------
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""

        if self.is_on:
            await super().async_turn_off(**kwargs)
            await self._action(
                self._coordinator.charge_controls[self._subentry.subentry_id], False
            )


# ----------------------------------------------------------------------------
# Do not restore switch setting on reboot, otherwise can hold up startup until charging is completed.
# ----------------------------------------------------------------------------
class SolarChargerSwitchCharge(SolarChargerSwitchEntity):
    """Representation of a SolarCharger start switch."""

    # _entity_key = ENTITY_KEY_CHARGE_SWITCH

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: SwitchEntityDescription,
        coordinator: "SolarChargerCoordinator",
        default_val: bool,
        is_restore_state: bool,
        action: SWITCH_ACTION_TYPE,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            config_item,
            subentry,
            entity_type,
            desc,
            coordinator,
            default_val,
            is_restore_state,
            action,
        )

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

    CONFIG_SWITCH_LIST: tuple[
        tuple[
            str,
            Any,
            bool,
            SWITCH_ACTION_TYPE,
            SolarChargerEntityType,
            SwitchEntityDescription,
        ],
        ...,
    ] = (
        #####################################
        # Control entities
        # Must haves, ie. not hidden for all
        # entity_category=None
        #####################################
        # Control switches - calls coordinator to perform action
        #####################################
        (
            SWITCH_START_CHARGE,
            SolarChargerSwitchCharge,
            RESTORE_ON_START_FALSE,
            coordinator.switch_charge_update,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_START_CHARGE,
            ),
        ),
        #####################################
        # Boolean switches
        #####################################
        (
            SWITCH_FAST_CHARGE_MODE,
            SolarChargerSwitchEntity,
            RESTORE_ON_START_TRUE,
            coordinator.dummy_switch,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_FAST_CHARGE_MODE,
            ),
        ),
        (
            SWITCH_SCHEDULE_CHARGE,
            SolarChargerSwitchEntity,
            RESTORE_ON_START_TRUE,
            coordinator.dummy_switch,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_SCHEDULE_CHARGE,
            ),
        ),
        #####################################
        # Action switches
        #####################################
        (
            SWITCH_PLUGIN_TRIGGER,
            SolarChargerSwitchAction,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_plugin_trigger,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_PLUGIN_TRIGGER,
            ),
        ),
        (
            SWITCH_SUN_TRIGGER,
            SolarChargerSwitchAction,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_sun_elevation_trigger,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_SUN_TRIGGER,
            ),
        ),
    )

    for subentry in config_entry.subentries.values():
        # For charger subentries only
        if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
            switches: dict[str, SolarChargerSwitchEntity] = {}

            for (
                config_item,
                cls,
                is_restore_state,
                action,
                entity_type,
                entity_description,
            ) in CONFIG_SWITCH_LIST:
                if is_create_entity(subentry, entity_type):
                    switches[config_item] = cls(
                        config_item,
                        subentry,
                        entity_type,
                        entity_description,
                        coordinator,
                        get_device_config_default_value(subentry, config_item),
                        is_restore_state,
                        action,
                    )

            if len(switches) > 0:
                coordinator.charge_controls[subentry.subentry_id].switches = switches
                async_add_entities(
                    switches.values(),
                    update_before_add=False,
                    config_subentry_id=subentry.subentry_id,
                )
