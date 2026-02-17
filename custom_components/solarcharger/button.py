"""SolarCharger button platform."""

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant import config_entries, core
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BUTTON, BUTTON_RESET_CHARGE_LIMIT_AND_TIME, DOMAIN, ICON_START
from .coordinator import SolarChargerCoordinator
from .entity import SolarChargerEntity, SolarChargerEntityType, is_create_entity
from .model_device_control import DeviceControl

# type BUTTON_ACTION_TYPE = Callable[[ChargeControl], Coroutine[Any, Any, None] | None]
# type BUTTON_ACTION_TYPE = (
#     core.HassJob[[ChargeControl], Coroutine[Any, Any, None] | None]
#     | Callable[[ChargeControl], Coroutine[Any, Any, None] | None]
# )
type BUTTON_ACTION_TYPE = Callable[[DeviceControl], Coroutine[Any, Any, None]]


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerButtonEntity(SolarChargerEntity, ButtonEntity):
    """SolarCharger button entity."""

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: ButtonEntityDescription,
        coordinator: SolarChargerCoordinator,
    ) -> None:
        """Initialize the SolarCharger button entity."""
        SolarChargerEntity.__init__(self, config_item, subentry, entity_type)
        self.set_entity_id(BUTTON, config_item)
        self.set_entity_unique_id(BUTTON, config_item)

        self.entity_description = desc

        self._coordinator = coordinator

    # ----------------------------------------------------------------------------
    # See https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-event-setup/
    async def async_added_to_hass(self) -> None:
        """Entity about to be added to hass. Restore state and subscribe for events here if needed."""

        await super().async_added_to_hass()


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerButtonActionEntity(SolarChargerButtonEntity):
    """SolarCharger button action on button press."""

    # _entity_key = CONTROL_CHARGE_BUTTON
    # _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = ICON_START
    # _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
        desc: ButtonEntityDescription,
        coordinator: SolarChargerCoordinator,
        action: BUTTON_ACTION_TYPE,
    ) -> None:
        """Initialize the button."""

        SolarChargerButtonEntity.__init__(
            self, config_item, subentry, entity_type, desc, coordinator
        )
        self._action = action

    # ----------------------------------------------------------------------------
    async def async_press(self) -> None:
        """Press the button."""

        # await self._coordinator.async_start_charger(
        #     self._coordinator.charge_controls[self._subentry.subentry_id]
        # )
        await self._action(
            self._coordinator.device_controls[self._subentry.subentry_id]
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

    # ----------------------------------------------------------------------------
    CONFIG_BUTTON_LIST: tuple[
        tuple[
            str,
            Any,
            BUTTON_ACTION_TYPE,
            SolarChargerEntityType,
            ButtonEntityDescription,
        ],
        ...,
    ] = (
        #####################################
        # Button entities
        # entity_category=None
        #####################################
        (
            BUTTON_RESET_CHARGE_LIMIT_AND_TIME,
            SolarChargerButtonActionEntity,
            coordinator.async_reset_charge_limit_default,
            SolarChargerEntityType.LOCAL_HIDDEN_OR_GLOBAL,
            ButtonEntityDescription(
                key=BUTTON_RESET_CHARGE_LIMIT_AND_TIME,
            ),
        ),
    )

    # ----------------------------------------------------------------------------
    for subentry in config_entry.subentries.values():
        # For both global default and charger subentries
        buttons: dict[str, SolarChargerButtonActionEntity] = {}

        for (
            config_item,
            cls,
            action,
            entity_type,
            entity_description,
        ) in CONFIG_BUTTON_LIST:
            if is_create_entity(subentry, entity_type):
                buttons[config_item] = cls(
                    config_item,
                    subentry,
                    entity_type,
                    entity_description,
                    coordinator,
                    action,
                )

        if len(buttons) > 0:
            coordinator.device_controls[
                subentry.subentry_id
            ].controller.charge_control.buttons = buttons
            async_add_entities(
                buttons.values(),
                update_before_add=False,
                config_subentry_id=subentry.subentry_id,
            )
