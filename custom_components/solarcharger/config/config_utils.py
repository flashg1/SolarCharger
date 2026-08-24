# ruff: noqa: TID252
"""Common config utils."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
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
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from ..const import (
    CHARGE_API_DEFAULT_VALUES,
    CHARGE_API_ENTITIES,
    CONFIG_DEVICE_DOMAIN,
    CONFIG_DEVICE_ID,
    CONFIG_DEVICE_LIST,
    CONFIG_DEVICE_NAME,
    CONFIG_FILE_DEVICE,
    CONFIG_NAME_MARKER,
    CONFIG_WITH_NO_DEFAULTS,
    DELETE_ENTITY_MARKER,
    DELETE_STRING_MARKER,
    DEVICE_NAME_MARKER,
    DOMAIN,
    DOMAIN_WITH_SUBDOMAINS,
    ENTITY_DEVICE_GET_CHARGE_LIMIT,
    ENTITY_DEVICE_LOCATION_SENSOR,
    ENTITY_DEVICE_SET_CHARGE_LIMIT,
    ENTITY_DEVICE_SOC_SENSOR,
    ENTITY_DEVICE_UPDATE_HA_BUTTON,
    ENTITY_DEVICE_WAKE_UP_BUTTON,
    NON_ENTITY_CONFIGS,
    NUMBER_DEVICE_CHARGE_LIMIT,
    NUMBER_DEVICE_MAX_CHARGE_LIMIT,
    NUMBER_DEVICE_MIN_CHARGE_LIMIT,
    NUMBER_WAIT_DEVICE_LIMIT_CHANGE,
    NUMBER_WAIT_DEVICE_UPDATE_HA,
    NUMBER_WAIT_DEVICE_WAKEUP,
    OPTION_CHARGER_NAME,
    OPTION_DEVICE_LOCATION_STATE_LIST,
    OPTION_GLOBAL_DEFAULTS_ID,
    STORAGE_VERSION,
    SUBENTRY_CHARGER_DEVICE_DOMAIN,
    SUBENTRY_CHARGER_DEVICE_SUBDOMAIN,
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
# Number selectors
#####################################
PERCENT_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=0, max=100, unit_of_measurement="%"
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
BINARY_SENSOR_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["binary_sensor"],
    )
)
BINARY_SENSOR_ENTITY_SELECTOR_READ_ONLY = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["binary_sensor"],
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

WEATHER_ENTITY_SELECTOR = EntitySelector(
    EntitySelectorConfig(
        multiple=False,
        domain=["weather"],
    )
)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
def _is_solarcharger_entity(entity_id: str) -> bool:
    """Entity with solarcharger prefix is a solarcharger entity."""

    # return config_item in entity_id
    # Local device entity must contain .solarcharger_ in entity_id.
    return DOMAIN in entity_id


# ----------------------------------------------------------------------------
def choose_selector(
    api_entities: dict[str, str | None] | None,
    config_item: str,
    read_only_selector: EntitySelector,
    default_selector: EntitySelector,
    modifiable_if_solarcharger_entity: bool = False,
) -> EntitySelector:
    """Entity selector is readonly if API entity is a local device entity, ie. user cannot change it.

    Local device entities are not modifiable. Local config entities are modifiable is modifiable_if_local=True.
    eg. chargee_charge_limit is modifiable for OCPP because it is a local config entity.
    """

    if api_entities:
        entity_id = api_entities.get(config_item)
        if entity_id is not None:
            if _is_solarcharger_entity(entity_id):
                if not modifiable_if_solarcharger_entity:
                    return read_only_selector
            else:
                # Local device entity, ie. non-configurable.
                return read_only_selector

    return default_selector


# ----------------------------------------------------------------------------
# Config storage utils
# ----------------------------------------------------------------------------
def _ha_store_get_key(config_name: str) -> str:
    """Get config storage key."""

    name = slugify(config_name.strip())
    return f"{DOMAIN}.{name}"


# ----------------------------------------------------------------------------
def ha_store_open(hass: HomeAssistant, config_name: str) -> Store:
    """Open device settings file storage."""

    storage_key = _ha_store_get_key(config_name)
    return Store(hass, STORAGE_VERSION, storage_key)


# ----------------------------------------------------------------------------
async def _async_ha_store_get_device_list(store: Store) -> list[dict[str, str]]:
    """Load device list from file storage."""

    data = await store.async_load()
    if data is None:
        return []

    device_list: list[dict[str, str]] = data.get(CONFIG_DEVICE_LIST, [])
    return device_list


# ----------------------------------------------------------------------------
async def async_ha_store_load_device_list(
    hass: HomeAssistant,
) -> list[dict[str, str]]:
    """Load device list from file storage."""

    store = ha_store_open(hass, CONFIG_FILE_DEVICE)
    return await _async_ha_store_get_device_list(store)


# ----------------------------------------------------------------------------
async def async_ha_store_update_device_list(
    hass: HomeAssistant, device_domain: str, device_name: str, device_id: str
) -> None:
    """Update device list in file storage."""

    store = ha_store_open(hass, CONFIG_FILE_DEVICE)
    device_list = await _async_ha_store_get_device_list(store)
    new_device = {
        CONFIG_DEVICE_DOMAIN: device_domain,
        CONFIG_DEVICE_NAME: device_name,
        CONFIG_DEVICE_ID: device_id,
    }

    found = False
    for index, device in enumerate(device_list):
        if (
            device[CONFIG_DEVICE_DOMAIN] == device_domain
            and device[CONFIG_DEVICE_NAME] == device_name
        ):
            device_list[index] = new_device
            found = True
            break

    if not found:
        device_list.append(new_device)

    await store.async_save({CONFIG_DEVICE_LIST: device_list})

    #######################################################
    # Problem with HA storing list[tuples[str,str,str]]. It stores it as list[list[str]].
    # So need to use list instead of tuples.
    # It is stored as,
    # "device_list": [["ocpp","charger1","5a75634604b1af16993777353f385926"],["ocpp","charger2","ee354487291c4dc05f9d86ae3b8cab70"]]
    # It needs to be stored as,
    # "device_list": [("ocpp","charger1","5a75634604b1af16993777353f385926"),("ocpp","charger2","ee354487291c4dc05f9d86ae3b8cab70")]
    # Hence cannot match.
    #######################################################
    # if new_item not in device_list:
    #     device_list.append(new_item)
    #     await store.async_save({CONFIG_DEVICE_LIST: device_list})


# ----------------------------------------------------------------------------
def _delete_member_not_in_new_list(
    old_list: list[dict[str, str]], new_list: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Delete member not in new list."""

    # Create a lookup dictionary of {(domain, name): new_list_device}
    new_lookup = {(d[CONFIG_DEVICE_DOMAIN], d[CONFIG_DEVICE_NAME]): d for d in new_list}

    # Filter and update elements safely using a list comprehension
    return [
        new_lookup[(device[CONFIG_DEVICE_DOMAIN], device[CONFIG_DEVICE_NAME])]
        for device in old_list
        if (device[CONFIG_DEVICE_DOMAIN], device[CONFIG_DEVICE_NAME]) in new_lookup
    ]


# ----------------------------------------------------------------------------
def _add_new_member_from_new_list(
    old_list: list[dict[str, str]], new_list: list[dict[str, str]], merge: bool
) -> list[dict[str, str]]:
    """Add or update member from new list keeping old list order. Delete member not in new list if not merging."""

    # Create a lookup dictionary of {(domain, name): new_list_device}
    new_lookup = {(d[CONFIG_DEVICE_DOMAIN], d[CONFIG_DEVICE_NAME]): d for d in new_list}
    updated_list = []
    updated_list_keys = set()

    # 1. Update existing matches in 'old_list' and track what we've processed.
    for old_device in old_list:
        old_key = (old_device[CONFIG_DEVICE_DOMAIN], old_device[CONFIG_DEVICE_NAME])
        if old_key in new_lookup:
            # Match found: update with a shallow copy from new_list.
            updated_list.append(new_lookup[old_key])
            updated_list_keys.add(old_key)
        elif merge:
            # No match: keep the original item as-is if merging.
            updated_list.append(old_device)
            updated_list_keys.add(old_key)

    # 2. Append elements from 'new_list' that were never found in 'old_list'.
    for new_device in new_list:
        new_key = (new_device[CONFIG_DEVICE_DOMAIN], new_device[CONFIG_DEVICE_NAME])
        if new_key not in updated_list_keys:
            # Safe shallow copy.
            updated_list.append(new_device)
            # Prevents duplicates if new_list has duplicates.
            updated_list_keys.add(new_key)

    return updated_list


# ----------------------------------------------------------------------------
async def async_ha_store_replace_device_list(
    hass: HomeAssistant, new_list: list[dict[str, str]]
) -> None:
    """Replace device list."""

    store = ha_store_open(hass, CONFIG_FILE_DEVICE)
    device_list = await _async_ha_store_get_device_list(store)
    device_list = _add_new_member_from_new_list(device_list, new_list, merge=False)
    await store.async_save({CONFIG_DEVICE_LIST: device_list})


# ----------------------------------------------------------------------------
async def async_ha_store_delete_device_list(
    hass: HomeAssistant, device_domain: str, device_name: str
) -> None:
    """Delete device from device list in file storage."""

    store = ha_store_open(hass, CONFIG_FILE_DEVICE)
    device_list = await _async_ha_store_get_device_list(store)

    # Remove device matching domain and name
    for index, device in enumerate(device_list):
        if (
            device[CONFIG_DEVICE_DOMAIN] == device_domain
            and device[CONFIG_DEVICE_NAME] == device_name
        ):
            device_list.pop(index)
            break

    await store.async_save({CONFIG_DEVICE_LIST: device_list})


# ----------------------------------------------------------------------------
def _ha_store_migrate_config(store_config: dict[str, Any]) -> None:
    """Migrate and delete old config settings."""

    # Since Python 3.7, standard dictionaries remember the order items were added.
    # Converting a dictionary to a list keeps that same order for version migrations.
    # old name (key): new name (value)
    migrate_list: dict[str, str] = {
        # Migrate from v0.9.0 to v0.10.0.
        "chargee_min_charge_limit": NUMBER_DEVICE_MIN_CHARGE_LIMIT,
        "chargee_max_charge_limit": NUMBER_DEVICE_MAX_CHARGE_LIMIT,
        "wait_chargee_wakeup": NUMBER_WAIT_DEVICE_WAKEUP,
        "wait_chargee_update_ha": NUMBER_WAIT_DEVICE_UPDATE_HA,
        "wait_chargee_limit_change": NUMBER_WAIT_DEVICE_LIMIT_CHANGE,
        "chargee_soc_sensor": ENTITY_DEVICE_SOC_SENSOR,
        "chargee_charge_limit": NUMBER_DEVICE_CHARGE_LIMIT,
        "chargee_get_charge_limit": ENTITY_DEVICE_GET_CHARGE_LIMIT,
        "chargee_set_charge_limit": ENTITY_DEVICE_SET_CHARGE_LIMIT,
        "chargee_location_sensor": ENTITY_DEVICE_LOCATION_SENSOR,
        "chargee_location_state_list": OPTION_DEVICE_LOCATION_STATE_LIST,  # string
        "chargee_wake_up_button": ENTITY_DEVICE_WAKE_UP_BUTTON,
        "chargee_update_ha_button": ENTITY_DEVICE_UPDATE_HA_BUTTON,
    }

    # Do not directly modify data map in loop, so put in list first.
    for old_name, old_config_val in list(store_config.items()):
        new_name = migrate_list.get(old_name)
        if new_name:
            # old_config_val = data.pop(old_name)
            del store_config[old_name]

            # Only remove old solar charger entity ID.
            # Need to handle separately for config string.
            if not _is_solarcharger_entity(old_config_val):
                # Keep non-solarcharger entity ID, string config or None.
                store_config[new_name] = old_config_val


# ----------------------------------------------------------------------------
async def async_ha_store_load(store: Store) -> dict[str, Any] | None:
    """Open device settings file storage."""

    store_config = await store.async_load()
    if store_config is not None:
        _ha_store_migrate_config(store_config)

    return store_config


# ----------------------------------------------------------------------------
async def async_ha_store_save(store: Store, data: dict[str, Any]) -> None:
    """Save device settings to file storage."""

    # sorted_by_key = {k: v for k, v in sorted(data.items())}
    sorted_by_key = dict(sorted(data.items()))
    await store.async_save(sorted_by_key)


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
        if device_domain in DOMAIN_WITH_SUBDOMAINS:
            device_domain = subentry.data.get(SUBENTRY_CHARGER_DEVICE_SUBDOMAIN)

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
def is_api_defined_solarcharger_entity(
    subentry: ConfigSubentry, config_item: str
) -> bool:
    """Is charger API defined a solarcharger entity or third-party entity for config item?"""
    defined_solarcharger_entity = False

    api_entities = get_device_api_entities(subentry)
    if api_entities is not None:
        entity_id = api_entities.get(config_item)
        if entity_id is not None:
            defined_solarcharger_entity = _is_solarcharger_entity(entity_id)

    return defined_solarcharger_entity


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
        # For global defaults subentry, get from global default dictionary only.
        val = _get_device_global_default_value(config_item)
    else:
        # For device subentry, get from local default dictionary first, then global default dictionary if not found in local.
        val = _get_device_local_default_value(device_domain, config_item)
        if val is None:
            val = _get_device_global_default_value(config_item)

    # Entities can have no default values, eg. charger effective voltage, charger max current.
    # This is for default value of the entity, ie. not for default entity name.
    if val is None:
        if config_item not in CONFIG_WITH_NO_DEFAULTS:
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

    # If config is not an entity, then try to get default value.
    if use_default and final_val is None and config_item in NON_ENTITY_CONFIGS:
        final_val = get_device_config_default_value(subentry, config_item)

    # _LOGGER.debug(
    #     "%s: %s: final=%s, local=%s, global=%s",
    #     subentry.unique_id,
    #     config_item,
    #     final_val,
    #     saved_local_val,
    #     saved_global_val,
    # )

    return final_val


# ----------------------------------------------------------------------------
def delete_marked_config(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Delete entity and config strings marked for deletion.

    To delete entity from options config, user need to select dummy entity with .deleteme name.
    To delete string from options config, user need to type in exactly 2 blanks.
    """

    for config_item, value in list(data.items()):
        # User request to delete config.
        # "" or None made no difference, options flow will remove the config from the data structure.
        # This is bad because I can't save a blank string in config.
        #
        # Leave existing value unless it is marked for deletion, eg.
        # sensor.deleteme, button.deleteme, etc.
        # No other way to detect that user wants to delete the entity.
        if (
            value is not None
            and isinstance(value, str)
            and (DELETE_ENTITY_MARKER in value or value == DELETE_STRING_MARKER)
        ):
            _LOGGER.warning("Delete config: %s = '%s'", config_item, value)
            data[config_item] = None

    return data


# ----------------------------------------------------------------------------
def create_entity_ids_from_templates(
    user_config_map: dict[str, Any],
    template_map: dict[str, str | None] | None,
    device_name: str | None,
    config_name: str | None,
    is_init_all: bool,
) -> None:
    """Create config from SolarCharger entity and config templates."""

    if template_map:
        # key_list = list(template_map.keys())
        # for config_item in key_list:
        for config_item, template in template_map.items():
            sc_config = get_device_entity_id_with_substitution(
                template_map,
                config_item,
                device_name,
                config_name,
            )

            # Confirmed config_item is not in dictionary by checking if dictionary key exists.
            # found_config = config_item in user_config_map
            user_config = user_config_map.get(config_item)
            is_api_entity = (
                False if template is None else DEVICE_NAME_MARKER in template
            )
            _LOGGER.debug(
                "%s: is_api_entity=%s, user_config='%s', sc_entity_id='%s'",
                config_item,
                is_api_entity,
                user_config,
                sc_config,
            )

            if sc_config is not None:
                #####################################
                # Process SolarCharger configs found in user_config_map.
                #####################################
                if config_item == OPTION_CHARGER_NAME:
                    # Special case, already handled in process_api_config()
                    pass

                elif user_config is None:
                    # Only add config if this is an initial setup.
                    # Otherwise config is destined for removal by HA.
                    if is_init_all:
                        user_config_map[config_item] = sc_config

                elif is_api_entity:
                    # An API entity, so must set it.
                    user_config_map[config_item] = sc_config

                else:
                    # Everything else that is **modifiable** can be overriden.
                    # So keep unchanged.
                    pass


# ----------------------------------------------------------------------------
def process_api_config(
    config_entry: ConfigEntry,
    config_name: str,  # Same as subentry unique_id
    data: dict[str, Any],
    is_init_all: bool,
) -> dict[str, Any]:
    """Reset entity names using new device name and config name substitutions. Delete marked entities."""

    if config_name != OPTION_GLOBAL_DEFAULTS_ID:
        # _LOGGER.warning("Original config: %s", data)
        # Delete marked entities and config strings
        data = delete_marked_config(data)

        # Reset API entity names due to device name change
        subentry_id = get_subentry_id(config_entry, config_name)
        if subentry_id:
            subentry = config_entry.subentries.get(subentry_id)
            if subentry:
                #####################################################################
                # Charger name must be in data.
                # For charger with blank name "", set charger name to single space, ie. " ".
                # If OPTION_CHARGER_NAME is "" or None, HA removes it from storage.
                # So store it as single blank, ie. " ", and then strip it before use.
                # Here will strip the space from charger name before use.
                #####################################################################
                device_name = data.get(OPTION_CHARGER_NAME, " ")
                device_name = slugify(device_name.strip())
                if device_name == "":
                    # HA will not save blank configs, so make it a single blank.
                    data[OPTION_CHARGER_NAME] = " "
                else:
                    data[OPTION_CHARGER_NAME] = device_name

                api_entities = get_device_api_entities(subentry)
                create_entity_ids_from_templates(
                    data, api_entities, device_name, subentry.unique_id, is_init_all
                )

        _LOGGER.warning("Device config: %s", data)

    return data
