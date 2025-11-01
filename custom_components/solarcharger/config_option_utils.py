"""Common option utils."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TemplateSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import (
    CHARGE_API_ENTITIES,
    CONFIG_NAME_MARKER,
    DEVICE_NAME_MARKER,
    OPTION_CHARGER_DEVICE_NAME,
    OPTION_DELETE_ENTITY,
    OPTION_DEVICE_ENTITY_LIST,
    OPTION_GLOBAL_DEFAULTS_ID,
    SUBENTRY_THIRDPARTY_DOMAIN,
)

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
#####################################
# Common selectors
#####################################
BOOLEAN_SELECTOR = BooleanSelector()
TEMPLATE_SELECTOR = TemplateSelector(TemplateSelectorConfig())
TEMPLATE_SELECTOR_READ_ONLY = TemplateSelector(TemplateSelectorConfig(read_only=True))
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
TEXT_SELECTOR_READ_ONLY = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, read_only=True)
)
OPTIONS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[],
        custom_value=True,
        multiple=True,
    )
)
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))

TARGET_TEMPERATURE_FEATURE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["single", "high_low", "none"],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="target_temperature_feature",
    )
)

NUMBER_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["number", "input_number", "sensor"],
    )
)
NUMBER_ENTITY_SELECTOR_READ_ONLY = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["number", "input_number", "sensor"],
        read_only=True,
    )
)
SENSOR_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["sensor", "binary_sensor"],
    )
)
SENSOR_ENTITY_SELECTOR_READ_ONLY = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["sensor", "binary_sensor"],
        read_only=True,
    )
)
SWITCH_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["switch"],
    )
)
SWITCH_ENTITY_SELECTOR_READ_ONLY = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["switch"],
        read_only=True,
    )
)
BUTTON_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["button"],
    )
)
BUTTON_ENTITY_SELECTOR_READ_ONLY = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["button"],
        read_only=True,
    )
)
LOCATION_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["device_tracker", "binary_sensor"],
    )
)
LOCATION_ENTITY_SELECTOR_READ_ONLY = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["device_tracker", "binary_sensor"],
        read_only=True,
    )
)


ELECTRIC_CURRENT_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=0, max=100, unit_of_measurement="A"
    )
)
WAIT_TIME_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=1, max=600, unit_of_measurement="sec"
    )
)
SUN_ELEVATION_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=-90, max=+90, unit_of_measurement="degree"
    )
)
ALLOCATION_WEIGHT_SELECTOR = NumberSelector(
    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=100)
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
def entity_selector(
    api_entities: dict[str, str | None] | None,
    config_item: str,
    read_only_selector: EntitySelector,
    default_selector: EntitySelector,
) -> EntitySelector:
    """Entity selector is readonly if API entity is set, ie. user cannot change it."""

    if api_entities:
        if api_entities.get(config_item):
            return read_only_selector

    return default_selector


# ----------------------------------------------------------------------------
def get_default_entity(
    api_entities: dict[str, str | None] | None,
    config_item: str,
    device_name: str | None,
    config_name: str | None,
) -> str | None:
    """Get default value from dictionary with substition."""
    entity_str: str | None = None

    # The test "if substr:" cannot distinguish between substr='' and substr=None.  Must explicitly test for None!
    if api_entities:
        entity_str = api_entities.get(config_item)
        if entity_str:
            if device_name is not None:
                if entity_str == DEVICE_NAME_MARKER:
                    entity_str = device_name
                elif device_name == "":
                    entity_str = entity_str.replace(DEVICE_NAME_MARKER, "")
                else:
                    entity_str = entity_str.replace(
                        DEVICE_NAME_MARKER, f"{device_name}_"
                    )

            if config_name is not None:
                entity_str = entity_str.replace(CONFIG_NAME_MARKER, f"{config_name}")

    return entity_str


# ----------------------------------------------------------------------------
def get_entity_name(
    subentry: ConfigSubentry,
    config_item: str,
    device_name: str,
) -> str | None:
    """Get entity name for config item with string substitution for device name."""

    device_domain = subentry.data.get(SUBENTRY_THIRDPARTY_DOMAIN)
    if device_domain:
        api_entities = CHARGE_API_ENTITIES.get(device_domain)

        if api_entities:
            return get_default_entity(
                api_entities,
                config_item,
                device_name,
                subentry.unique_id,
            )

    return None


# ----------------------------------------------------------------------------
# def get_subentry_id(config_entry: ConfigEntry, config_name: str) -> str | None:
#     """Get subentry ID for device name."""
#     subentry_id: str | None = None

#     if config_name == OPTION_GLOBAL_DEFAULTS:
#         return GLOBAL_DEFAULTS_ID

#     if config_entry.subentries:
#         for subentry in config_entry.subentries.values():
#             if subentry.subentry_type == SUBENTRY_TYPE_CHARGER:
#                 if subentry.unique_id == config_name:
#                     subentry_id = subentry.subentry_id
#                     break

#     return subentry_id


# ----------------------------------------------------------------------------
def get_subentry_id(config_entry: ConfigEntry, config_name: str) -> str | None:
    """Get subentry ID for device name."""
    subentry_id: str | None = None

    # subentries is a dictionary accessed via subentry.subentry_id, not subentry.unique_id.
    if config_entry.subentries:
        for subentry in config_entry.subentries.values():
            if subentry.unique_id == config_name:
                subentry_id = subentry.subentry_id
                break

    return subentry_id


# ----------------------------------------------------------------------------
def get_subentry(config_entry: ConfigEntry, config_name: str) -> ConfigSubentry | None:
    """Get subentry ID for device name."""
    found_subentry: ConfigSubentry | None = None

    if config_entry.subentries:
        for subentry in config_entry.subentries.values():
            if subentry.unique_id == config_name:
                found_subentry = subentry
                break

    return found_subentry


# ----------------------------------------------------------------------------
def get_saved_local_option_value(
    config_entry: ConfigEntry, subentry: ConfigSubentry | None, config_item: str
) -> Any | None:
    """Get saved option value if exist."""
    saved_val = None

    if subentry and subentry.unique_id:
        device_options = config_entry.options.get(subentry.unique_id)
        if device_options:
            saved_val = device_options.get(config_item)

    return saved_val


# ----------------------------------------------------------------------------
def get_saved_global_option_value(
    config_entry: ConfigEntry, config_item: str
) -> Any | None:
    """Get saved option value if exist."""

    global_defaults_subentry = get_subentry(config_entry, OPTION_GLOBAL_DEFAULTS_ID)
    return get_saved_local_option_value(
        config_entry, global_defaults_subentry, config_item
    )


# ----------------------------------------------------------------------------
def get_saved_option_value(
    config_entry: ConfigEntry,
    subentry: ConfigSubentry,
    config_item: str,
    use_default: bool,
) -> Any | None:
    """Get saved option value if exist, else get from default if allowed."""
    saved_local_val = None
    saved_global_val = None

    if subentry is None:
        raise SystemError(f"Cannot get {config_item} because subentry is None")

    # Get saved local value
    saved_local_val = get_saved_local_option_value(config_entry, subentry, config_item)
    final_val = saved_local_val
    if saved_local_val is None and use_default:
        # Get saved global value if already global
        if subentry.unique_id != OPTION_GLOBAL_DEFAULTS_ID:
            saved_global_val = get_saved_global_option_value(config_entry, config_item)
            final_val = saved_global_val

    _LOGGER.debug(
        "Required option=%s, final=%s, local=%s, global=%s",
        config_item,
        final_val,
        saved_local_val,
        saved_global_val,
    )

    return final_val


# ----------------------------------------------------------------------------
def delete_marked_entities(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Delete entity strings marked for deletion."""

    for config_item, value in list(data.items()):
        # Leave existing value unless it is marked for deletion, eg.
        # sensor.deleteme, button.deleteme, etc.
        # No other way to detect that user wants to delete the entity.
        # User setting to None by deleting entity in user interface did not help
        # because vol.Optional() has been set to restore from saved options.
        if value and isinstance(value, str) and OPTION_DELETE_ENTITY in value:
            data[config_item] = None

    return data


# ----------------------------------------------------------------------------
def reset_api_entities(
    config_entry: ConfigEntry,
    config_name: str,  # Same as subentry unique_id
    data: dict[str, Any],
    reset_all_entities: bool = False,
) -> dict[str, Any]:
    """Reset entity names using new device mname."""

    if config_name != OPTION_GLOBAL_DEFAULTS_ID:
        # Delete marked entities
        data = delete_marked_entities(data)

        # Reset API entity names due to device name change
        subentry_id = get_subentry_id(config_entry, config_name)
        if subentry_id:
            subentry = config_entry.subentries.get(subentry_id)
            if subentry:
                #####################################################################
                # OPTION_CHARGER_DEVICE_NAME and others are always present if restore from saved options is enabled
                #####################################################################
                if OPTION_CHARGER_DEVICE_NAME in data:
                    device_name = data.get(OPTION_CHARGER_DEVICE_NAME, "")
                    device_name = slugify(device_name.strip())
                    data[OPTION_CHARGER_DEVICE_NAME] = device_name

                    device_domain = subentry.data.get(SUBENTRY_THIRDPARTY_DOMAIN)
                    if device_domain:
                        api_entities = CHARGE_API_ENTITIES.get(device_domain)
                        if api_entities:
                            if reset_all_entities:
                                # Only reset all entities during subentry initial setup
                                key_list = list(api_entities.keys())
                            else:
                                # This will only reset dependent entities when device name is changed
                                key_list = OPTION_DEVICE_ENTITY_LIST

                            for config_item in key_list:
                                entity_name = get_default_entity(
                                    api_entities,
                                    config_item,
                                    device_name,
                                    subentry.unique_id,
                                )
                                if entity_name:
                                    data[config_item] = entity_name
    return data
