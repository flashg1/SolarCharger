"""Common config utils."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
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
    CHARGE_API_DEFAULT_VALUES,
    CHARGE_API_ENTITIES,
    CONFIG_NAME_MARKER,
    DEVICE_NAME_MARKER,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    OPTION_CHARGER_MAX_CURRENT,
    OPTION_CHARGER_NAME,
    OPTION_DELETE_ENTITY,
    OPTION_GLOBAL_DEFAULTS_ID,
    SUBENTRY_CHARGER_DEVICE_DOMAIN,
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

#####################################
# Entity selectors
#####################################
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

POWER_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["sensor", "number", "input_number"],
        device_class=[SensorDeviceClass.POWER],
    )
)

TIME_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["time", "input_datetime"],
    )
)

#####################################
# Number selectors
#####################################
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
    modifiable_if_local_config_entity: bool = False,
) -> EntitySelector:
    """Entity selector is readonly if API entity is a local device entity, ie. user cannot change it.

    Local device entities are not modifiable. Local config entities are modifiable is modifiable_if_local=True.
    eg. chargee_charge_limit is modifiable for OCPP because it is a local config entity.
    """

    if api_entities:
        entity_id = api_entities.get(config_item)
        if entity_id is not None:
            if config_item in entity_id:
                # Local config entity
                if not modifiable_if_local_config_entity:
                    return read_only_selector
            else:
                # Local device entity, ie. non-configurable.
                return read_only_selector

    return default_selector


# ----------------------------------------------------------------------------
# Subentry options utils
# ----------------------------------------------------------------------------
def get_device_domain(subentry: ConfigSubentry) -> str | None:
    """Get device domain from subentry. Return None for global defaults subentry."""

    if subentry.unique_id is None:
        raise SystemError(
            "Failed to get device domain because subentry unique_id is None"
        )

    if subentry.unique_id == OPTION_GLOBAL_DEFAULTS_ID:
        device_domain = None
    else:
        device_domain = subentry.data.get(SUBENTRY_CHARGER_DEVICE_DOMAIN)
        if device_domain is None:
            raise SystemError(
                f"Subentry {subentry.subentry_id}: Failed to get device domain"
            )

    return device_domain


# ----------------------------------------------------------------------------
def get_device_api_entities(subentry: ConfigSubentry) -> dict[str, str | None] | None:
    """Get device API entities dictionary from subentry. Return None for global defaults subentry."""

    device_domain = get_device_domain(subentry)
    if device_domain is not None:
        return CHARGE_API_ENTITIES.get(device_domain)

    return None


# ----------------------------------------------------------------------------
def is_config_entity_used_as_local_device_entity(
    subentry: ConfigSubentry, config_item: str
) -> bool:
    """Entity with config name indicates local device entity and not a built-in entity."""
    used_as_local_device_entity = False

    api_entities = get_device_api_entities(subentry)
    if api_entities is not None:
        entity_id = api_entities.get(config_item)
        if entity_id is not None:
            used_as_local_device_entity = config_item in entity_id

    return used_as_local_device_entity


# ----------------------------------------------------------------------------
def _get_device_global_default_value(config_item: str) -> Any | None:
    """Get device global default value for config item."""

    global_defaults = CHARGE_API_DEFAULT_VALUES.get(OPTION_GLOBAL_DEFAULTS_ID)
    if global_defaults is None:
        raise SystemError(
            f"No global default dictionary found for subentry ID '{OPTION_GLOBAL_DEFAULTS_ID}'"
        )

    return global_defaults.get(config_item)


# ----------------------------------------------------------------------------
def _get_device_local_default_value(device_domain: str, config_item: str) -> Any | None:
    """Get device local default value for config item."""

    local_defaults = CHARGE_API_DEFAULT_VALUES.get(device_domain)
    if local_defaults is None:
        raise SystemError(
            f"No local default dictionary found for domain '{device_domain}'"
        )

    return local_defaults.get(config_item)


# ----------------------------------------------------------------------------
def get_device_config_default_value(subentry: ConfigSubentry, config_item: str) -> Any:
    """Try getting value from local default dictionary first, otherwise from global default dictionary."""

    device_domain = get_device_domain(subentry)

    if device_domain is None:
        val = _get_device_global_default_value(config_item)
    else:
        val = _get_device_local_default_value(device_domain, config_item)
        if val is None:
            val = _get_device_global_default_value(config_item)

    # Entities can have no default values, eg. charger effective voltage, charger max current.
    if val is None:
        if config_item not in [
            NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
            OPTION_CHARGER_MAX_CURRENT,
        ]:
            raise SystemError(
                f"No default value found for config item '{config_item}' in subentry ID '{subentry.unique_id}'"
            )

    return val


# ----------------------------------------------------------------------------
def get_device_entity_id_with_substitution(
    api_entities: dict[str, str | None] | None,
    config_item: str,
    device_name: str | None,
    config_name: str | None,
) -> str | None:
    """Get entity ID template for config item with string substitution for device name and config name (subentry.unique_id)."""

    entity_id: str | None = None

    # The test "if substr:" cannot distinguish between substr='' and substr=None.  Must explicitly test for None!
    if api_entities:
        entity_id = api_entities.get(config_item)
        if entity_id:
            if device_name is not None:
                if entity_id == DEVICE_NAME_MARKER:
                    entity_id = device_name
                elif device_name == "":
                    entity_id = entity_id.replace(DEVICE_NAME_MARKER, "")
                else:
                    entity_id = entity_id.replace(DEVICE_NAME_MARKER, f"{device_name}_")

            if config_name is not None:
                entity_id = entity_id.replace(CONFIG_NAME_MARKER, config_name)

    return entity_id


# ----------------------------------------------------------------------------
def get_device_entity_id(
    subentry: ConfigSubentry,
    config_item: str,
    device_name: str,
) -> str | None:
    """Get entity ID template from dictionary for string substitions."""

    api_entities = get_device_api_entities(subentry)
    if api_entities:
        return get_device_entity_id_with_substitution(
            api_entities,
            config_item,
            device_name,
            subentry.unique_id,
        )

    return None


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
def get_saved_local_option_value_or_abort(
    config_entry: ConfigEntry, subentry: ConfigSubentry | None, config_item: str
) -> Any:
    """Get saved option value if exist."""

    if subentry is None:
        raise SystemError(f"Cannot get {config_item} because subentry is None")

    saved_val = get_saved_local_option_value(config_entry, subentry, config_item)
    if saved_val is None:
        raise SystemError(f"Cannot get {config_item} for subentry {subentry.unique_id}")

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
        "%s: %s: final=%s, local=%s, global=%s",
        subentry.unique_id,
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
) -> dict[str, Any]:
    """Reset entity names using new device name."""

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
                if OPTION_CHARGER_NAME in data:
                    device_name = data.get(OPTION_CHARGER_NAME, "")
                    device_name = slugify(device_name.strip())
                    data[OPTION_CHARGER_NAME] = device_name

                    api_entities = get_device_api_entities(subentry)
                    if api_entities:
                        key_list = list(api_entities.keys())
                        for config_item in key_list:
                            entity_name = get_device_entity_id_with_substitution(
                                api_entities,
                                config_item,
                                device_name,
                                subentry.unique_id,
                            )
                            if entity_name:
                                data[config_item] = entity_name
    return data
