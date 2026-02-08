"""SolarCharger button platform."""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries, core
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_ON
from homeassistant.core import State
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .config_utils import get_device_config_default_value
from .const import (
    DOMAIN,
    RESTORE_ON_START_FALSE,
    RESTORE_ON_START_TRUE,
    SWITCH,
    SWITCH_CALIBRATE_MAX_CHARGE_SPEED,
    SWITCH_CHARGE,
    SWITCH_FAST_CHARGE_MODE,
    SWITCH_PLUGIN_TRIGGER,
    SWITCH_POLL_CHARGER_UPDATE,
    SWITCH_REDUCE_CHARGE_LIMIT_DIFFERENCE,
    SWITCH_SCHEDULE_CHARGE,
    SWITCH_SUN_TRIGGER,
)
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity
from .model_device_control import DeviceControl

type SWITCH_ACTION_TYPE = Callable[[DeviceControl, bool], Coroutine[Any, Any, None]]

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
        self.update_ha_state()

    # ----------------------------------------------------------------------------
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        self.update_ha_state()

    # ----------------------------------------------------------------------------
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        # self._attr_is_on = True
        self.turn_on()

    # ----------------------------------------------------------------------------
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        # self._attr_is_on = False
        self.turn_off()

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
class SolarChargerSwitchActionEntity(SolarChargerSwitchEntity):
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
                self._coordinator.device_controls[self._subentry.subentry_id],
                True,
            )

    # ----------------------------------------------------------------------------
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""

        if self.is_on:
            await super().async_turn_off(**kwargs)
            await self._action(
                self._coordinator.device_controls[self._subentry.subentry_id],
                False,
            )


# ----------------------------------------------------------------------------
# Do not restore switch setting on reboot, otherwise can hold up startup until charging is completed.
# ----------------------------------------------------------------------------
class SolarChargerSwitchChargeEntity(SolarChargerSwitchEntity):
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

        self._coordinator.device_controls[
            self._subentry.subentry_id
        ].controller.charge_control.switch_charge = self.is_on

    # ----------------------------------------------------------------------------
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await super().async_turn_on(**kwargs)
        await self._coordinator.async_switch_charger(
            self._coordinator.device_controls[self._subentry.subentry_id],
            True,
        )

    # ----------------------------------------------------------------------------
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await super().async_turn_off(**kwargs)
        await self._coordinator.async_switch_charger(
            self._coordinator.device_controls[self._subentry.subentry_id],
            False,
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
            SWITCH_CHARGE,
            SolarChargerSwitchChargeEntity,
            # RESTORE_ON_START_FALSE,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_charger,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_CHARGE,
            ),
        ),
        #####################################
        # Boolean switches
        #####################################
        (
            SWITCH_REDUCE_CHARGE_LIMIT_DIFFERENCE,
            SolarChargerSwitchEntity,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_dummy,
            SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
            SwitchEntityDescription(
                key=SWITCH_REDUCE_CHARGE_LIMIT_DIFFERENCE,
                entity_category=EntityCategory.CONFIG,
            ),
        ),
        (
            SWITCH_FAST_CHARGE_MODE,
            SolarChargerSwitchEntity,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_dummy,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_FAST_CHARGE_MODE,
            ),
        ),
        (
            SWITCH_POLL_CHARGER_UPDATE,
            SolarChargerSwitchEntity,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_dummy,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_POLL_CHARGER_UPDATE,
                entity_category=EntityCategory.CONFIG,
            ),
        ),
        #####################################
        # Action switches
        #####################################
        (
            SWITCH_SCHEDULE_CHARGE,
            SolarChargerSwitchActionEntity,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_schedule_charge,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_SCHEDULE_CHARGE,
                entity_category=EntityCategory.CONFIG,
            ),
        ),
        (
            SWITCH_PLUGIN_TRIGGER,
            SolarChargerSwitchActionEntity,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_plugin_trigger,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_PLUGIN_TRIGGER,
                entity_category=EntityCategory.CONFIG,
            ),
        ),
        (
            SWITCH_SUN_TRIGGER,
            SolarChargerSwitchActionEntity,
            RESTORE_ON_START_TRUE,
            coordinator.async_switch_sun_elevation_trigger,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_SUN_TRIGGER,
                entity_category=EntityCategory.CONFIG,
            ),
        ),
        (
            SWITCH_CALIBRATE_MAX_CHARGE_SPEED,
            SolarChargerSwitchActionEntity,
            RESTORE_ON_START_FALSE,
            coordinator.async_switch_calibrate_max_charge_speed,
            SolarChargerEntityType.LOCAL_DEFAULT,
            SwitchEntityDescription(
                key=SWITCH_CALIBRATE_MAX_CHARGE_SPEED,
                entity_category=EntityCategory.CONFIG,
            ),
        ),
    )

    for subentry in config_entry.subentries.values():
        # For global defaults and charger subentries
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
            coordinator.device_controls[
                subentry.subentry_id
            ].controller.charge_control.switches = switches
            async_add_entities(
                switches.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
