"""Solar Charger Integration."""

import asyncio
import logging
from types import MappingProxyType
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .chargers import Charger, charger_factory
from .chargers.chargeable import Chargeable
from .config.config_subentry_charger import async_create_charger_device
from .config.config_subentry_custom import async_create_custom_device
from .config.config_utils import (
    async_ha_store_load,
    async_ha_store_load_device_list,
    async_ha_store_replace_device_list,
    async_ha_store_save,
    get_subentry,
    ha_store_open,
)
from .const import (
    CONFIG_DEVICE_DOMAIN,
    CONFIG_DEVICE_ID,
    CONFIG_DEVICE_NAME,
    DOMAIN,
    OPTION_GLOBAL_DEFAULT_ENTITIES,
    OPTION_GLOBAL_DEFAULTS_ID,
    OPTION_GLOBAL_DEFAULTS_NAME,
    PLATFORMS,
    SUBENTRY_CHARGER_DEVICE_DOMAIN,
    SUBENTRY_CHARGER_DEVICE_ID,
    SUBENTRY_CHARGER_DEVICE_NAME,
    SUBENTRY_CHARGER_TYPES,
    SUBENTRY_TYPE_DEFAULTS,
)
from .models.model_charge_control import ChargeControl, ControlEntities
from .models.model_device_control import DeviceControl
from .modules.controller import ChargeController
from .modules.coordinator import SolarChargerCoordinator

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Solar Charger integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


# ----------------------------------------------------------------------------
async def _async_create_global_defaults_subentry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Initialize global defaults subentry if none exist."""
    just_created_global_defaults_subentry = False

    global_defaults_subentry = get_subentry(config_entry, OPTION_GLOBAL_DEFAULTS_ID)
    if global_defaults_subentry is None:
        hass.config_entries.async_add_subentry(
            config_entry,
            ConfigSubentry(
                subentry_type=SUBENTRY_TYPE_DEFAULTS,
                title=OPTION_GLOBAL_DEFAULTS_NAME,
                unique_id=OPTION_GLOBAL_DEFAULTS_ID,
                data=MappingProxyType(  # make data immutable
                    {
                        SUBENTRY_CHARGER_DEVICE_DOMAIN: "N/A",  # Integration domain
                        SUBENTRY_CHARGER_DEVICE_NAME: "N/A",  # Integration-specific device name
                        SUBENTRY_CHARGER_DEVICE_ID: "N/A",  # Integration-specific device ID
                    }
                ),
            ),
        )

        data: dict[str, Any] = OPTION_GLOBAL_DEFAULT_ENTITIES

        # Look for historical config left behind by a previous installation.
        store = ha_store_open(hass, OPTION_GLOBAL_DEFAULTS_ID)
        store_config = await async_ha_store_load(store)
        if store_config is not None:
            data.update(store_config)

        # Save device settings to file storage.
        await async_ha_store_save(store, data)

        hass.config_entries.async_update_entry(
            config_entry,
            options=config_entry.options
            | {
                OPTION_GLOBAL_DEFAULTS_ID: data,
            },
        )

        just_created_global_defaults_subentry = True

    return just_created_global_defaults_subentry


# ----------------------------------------------------------------------------
async def _async_init_charger_subentry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    device_controls: dict[str, DeviceControl],
):
    """Initialize a charger for a given subentry."""

    # Initialize charger
    charger_device_id: str | None = subentry.data.get(SUBENTRY_CHARGER_DEVICE_ID)
    if not charger_device_id or not subentry.unique_id:
        _LOGGER.error(
            "No charger device ID found in subentry data: %s: %s",
            subentry.unique_id,
            subentry.subentry_id,
        )
        return

    # Initialize ChargeController
    charge_control = ChargeControl(
        subentry_id=subentry.subentry_id,
        config_name=subentry.unique_id,
        entities=ControlEntities(),
    )
    charger: Charger = await charger_factory(hass, entry, subentry, charger_device_id)
    chargeable: Chargeable = cast(Chargeable, charger)
    controller = ChargeController(
        hass, entry, subentry, charge_control, charger, chargeable
    )

    # Store in charge_controllers dictionary
    device_controls[subentry.subentry_id] = DeviceControl(
        subentry_id=subentry.subentry_id,
        config_name=subentry.unique_id,
        controller=controller,
    )

    _LOGGER.info(
        "Set up subentry charge control: class=%s, unique_id=%s, subentry_id=%s, subentry_type=%s, title=%s",
        charger.__class__.__name__,
        subentry.unique_id,
        subentry.subentry_id,
        subentry.subentry_type,
        subentry.title,
    )


# ----------------------------------------------------------------------------
async def _async_init_global_defaults_subentry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    device_controls: dict[str, DeviceControl],
):
    """Initialize global defaults subentry."""

    # Initialize charger
    charger_device_id: str | None = subentry.data.get(SUBENTRY_CHARGER_DEVICE_ID)
    if not charger_device_id or not subentry.unique_id:
        _LOGGER.error(
            "No global defaults ID found in subentry data: %s: %s",
            subentry.unique_id,
            subentry.subentry_id,
        )
        return

    # Initialize ChargeController
    charge_control = ChargeControl(
        subentry_id=subentry.subentry_id,
        config_name=subentry.unique_id,
        entities=ControlEntities(),
    )
    controller = ChargeController(hass, entry, subentry, charge_control, None, None)

    # Store in charge_controllers dictionary
    device_controls[subentry.subentry_id] = DeviceControl(
        subentry_id=subentry.subentry_id,
        config_name=subentry.unique_id,
        controller=controller,
    )

    _LOGGER.info(
        "Set up subentry global defaults: unique_id=%s, subentry_id=%s, subentry_type=%s, title=%s",
        subentry.unique_id,
        subentry.subentry_id,
        subentry.subentry_type,
        subentry.title,
    )


# ----------------------------------------------------------------------------
async def _async_init_subentries(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_controls: dict[str, DeviceControl],
    subentry_type_list: list[str],
) -> ConfigSubentry | None:
    """Initialise subentries depending on the subentry type."""

    global_defaults_subentry: ConfigSubentry | None = None

    for subentry in entry.subentries.values():
        if subentry.subentry_type in subentry_type_list:
            if subentry.subentry_type == SUBENTRY_TYPE_DEFAULTS:
                # Initialize global defaults
                global_defaults_subentry = subentry
                await _async_init_global_defaults_subentry(
                    hass,
                    entry,
                    subentry,
                    device_controls,
                )

            elif subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
                # Initialize charger
                await _async_init_charger_subentry(
                    hass,
                    entry,
                    subentry,
                    device_controls,
                )

    return global_defaults_subentry


# ----------------------------------------------------------------------------
async def _async_recreate_device_list(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    new_device_list: list[dict[str, str]] = []

    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_TYPE_DEFAULTS:
            continue

        if subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
            device_domain = subentry.data.get(SUBENTRY_CHARGER_DEVICE_DOMAIN)
            device_name = subentry.data.get(SUBENTRY_CHARGER_DEVICE_NAME)
            device_id = subentry.data.get(SUBENTRY_CHARGER_DEVICE_ID)
            device = {
                CONFIG_DEVICE_DOMAIN: device_domain,
                CONFIG_DEVICE_NAME: device_name,
                CONFIG_DEVICE_ID: device_id,
            }

            new_device_list.append(device)

    await async_ha_store_replace_device_list(hass, new_device_list)


# ----------------------------------------------------------------------------
async def _async_create_charger_subentries_from_config_file(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> int:
    """Create charger subentries from device list."""

    device_list = await async_ha_store_load_device_list(hass)
    device_count = len(device_list)

    if device_count > 0:
        for device in device_list:
            if device[CONFIG_DEVICE_DOMAIN] == DOMAIN:
                # Global defaults device must exists before custom chargers can be created.
                error_msg = await async_create_custom_device(
                    hass,
                    config_entry,
                    {SUBENTRY_CHARGER_DEVICE_NAME: device[CONFIG_DEVICE_NAME]},
                )
            else:
                # Third-party charger devices already exits, so can create SC charger device.
                error_msg = await async_create_charger_device(
                    hass,
                    config_entry,
                    {SUBENTRY_CHARGER_DEVICE_ID: device[CONFIG_DEVICE_ID]},
                )

            if error_msg is not None:
                _LOGGER.error(
                    "%s %s: %s",
                    device[CONFIG_DEVICE_DOMAIN],
                    device[CONFIG_DEVICE_NAME],
                    error_msg,
                )

    return device_count


# ----------------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar Charger from a config entry."""

    device_controls: dict[str, DeviceControl] = {}

    #####################################
    # Object creation order and initialisation order are important.
    # Create global defaults subentry
    #####################################
    just_created_global_defaults_subentry = (
        await _async_create_global_defaults_subentry(hass, entry)
    )
    global_defaults_subentry = await _async_init_subentries(
        hass, entry, device_controls, [SUBENTRY_TYPE_DEFAULTS]
    )
    if global_defaults_subentry is None:
        raise RuntimeError("Global defaults subentry not found")

    #####################################
    # Do not init custom chargers until global defaults device exists.
    #####################################
    if not just_created_global_defaults_subentry:
        # Global defaults device already exists, so init other subentries.
        await _async_init_subentries(
            hass, entry, device_controls, SUBENTRY_CHARGER_TYPES
        )

        # async_setup_entry() is called when HA re-initialise all subentries
        # after addition/deletion. So deleted subentries can be found by
        # comparing old and new list.
        # CAUTION: If add or delete device, can lose original device list here
        # if there were errors creating devices after reboot.
        await _async_recreate_device_list(hass, entry)

    #####################################
    # Create the coordinator and charge controls but not initialized.
    #####################################
    coordinator = SolarChargerCoordinator(
        hass=hass,
        entry=entry,
        global_defaults_subentry=global_defaults_subentry,
    )
    coordinator.device_controls = device_controls
    hass.data[DOMAIN][entry.entry_id] = coordinator

    #####################################
    # Create entites for each platform with dependency on coordinator.
    # Initially for global defaults device only if created for the first time.
    #####################################
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Must wait for entities to be created, otherwise will fail after adding
    # Tesla or OCPP charger, eg.
    # ValueError: tesla_custom_tesla23m3: charger_plugged_in_sensor: Failed to get entity ID
    # Most likely coordinator init had fail, or init had failed causing
    # entities not to be available on first run. Restart for second run and
    # SolarCharger spinned up without issue.
    await asyncio.sleep(3)

    #####################################
    # If created global defaults device for first time, now can create chargers
    # and custom devices. Won't be able to create custom devices until global
    # defaults device has been created.
    #####################################
    if just_created_global_defaults_subentry:
        device_count = await _async_create_charger_subentries_from_config_file(
            hass, entry
        )
        if device_count > 0:
            await _async_init_subentries(
                hass, entry, device_controls, SUBENTRY_CHARGER_TYPES
            )

            await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
            await asyncio.sleep(3)

            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            await asyncio.sleep(3)

    #####################################
    # Initialise coordinator and charge control after _PLATFORMS entities
    #####################################
    await coordinator.async_setup()

    # Registers update listener to update config entry when options are updated.
    # entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("SolarCharger initialized (config_entry_id=%s)", entry.entry_id)
    return True


# ----------------------------------------------------------------------------
# async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
#     """Handle options update."""
#     await hass.config_entries.async_schedule_reload(config_entry.entry_id)


# ----------------------------------------------------------------------------
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: SolarChargerCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    await coordinator.async_unload()  # Call coordinator's own unload method

    # Unload platforms
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded and coordinator:  # Ensure coordinator was found before trying to pop
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unloaded  # Return the result of unloading platforms
