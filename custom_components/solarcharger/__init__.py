"""Solar Charger Integration."""

import asyncio
import logging
from types import MappingProxyType
from typing import cast

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .chargers import Charger, charger_factory
from .chargers.chargeable import Chargeable
from .chargers.controller import ChargeController
from .config_utils import get_subentry
from .const import (
    DOMAIN,
    OPTION_GLOBAL_DEFAULT_ENTITIES,
    OPTION_GLOBAL_DEFAULTS_ID,
    PLATFORMS,
    SUBENTRY_CHARGER_DEVICE_DOMAIN,
    SUBENTRY_CHARGER_DEVICE_ID,
    SUBENTRY_CHARGER_DEVICE_NAME,
    SUBENTRY_CHARGER_TYPES,
    SUBENTRY_TYPE_DEFAULTS,
)
from .coordinator import SolarChargerCoordinator
from .model_control import ChargeControl

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
async def async_create_global_defaults_subentry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Initialize global defaults subentry if none exist."""

    global_defaults_subentry = get_subentry(config_entry, OPTION_GLOBAL_DEFAULTS_ID)
    if global_defaults_subentry is None:
        hass.config_entries.async_add_subentry(
            config_entry,
            ConfigSubentry(
                subentry_type=SUBENTRY_TYPE_DEFAULTS,
                title="Global defaults",
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

        hass.config_entries.async_update_entry(
            config_entry,
            options=config_entry.options
            | {
                OPTION_GLOBAL_DEFAULTS_ID: OPTION_GLOBAL_DEFAULT_ENTITIES,
            },
        )


# ----------------------------------------------------------------------------
async def async_init_charger_subentry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    charge_controls: dict[str, ChargeControl],
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
    charger: Charger = await charger_factory(hass, entry, subentry, charger_device_id)
    chargeable: Chargeable = cast(Chargeable, charger)

    # Initialize ChargeController
    controller: ChargeController = ChargeController(
        hass, entry, subentry, charger, chargeable
    )

    # Store in charge_controls dictionary
    charge_controls[subentry.subentry_id] = ChargeControl(
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
async def async_init_global_defaults_subentry(
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    charge_controls: dict[str, ChargeControl],
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

    # Store in charge_controls dictionary
    charge_controls[subentry.subentry_id] = ChargeControl(
        subentry_id=subentry.subentry_id,
        config_name=subentry.unique_id,
        controller=None,
    )

    _LOGGER.info(
        "Set up subentry global defaults: unique_id=%s, subentry_id=%s, subentry_type=%s, title=%s",
        subentry.unique_id,
        subentry.subentry_id,
        subentry.subentry_type,
        subentry.title,
    )


# ----------------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar Charger from a config entry."""

    #####################################
    # Object creation order and initialisation order are important.
    # Create global defaults subentry
    #####################################
    await async_create_global_defaults_subentry(hass, entry)

    #####################################
    # Initialise all subentries
    #####################################
    global_defaults_subentry = None
    charge_controls: dict[str, ChargeControl] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
            # Initialize charger
            await async_init_charger_subentry(
                hass,
                entry,
                subentry,
                charge_controls,
            )
        elif subentry.subentry_type == SUBENTRY_TYPE_DEFAULTS:
            # Initialize global defaults
            global_defaults_subentry = subentry
            await async_init_global_defaults_subentry(
                entry,
                subentry,
                charge_controls,
            )

    # There are no subentries on first start
    if global_defaults_subentry is None:
        raise RuntimeError("Global defaults subentry not found")

    #####################################
    # Create the coordinator and charge controls but not initialized
    #####################################
    coordinator = SolarChargerCoordinator(
        hass=hass,
        entry=entry,
        global_defaults_subentry=global_defaults_subentry,
    )
    coordinator.charge_controls = charge_controls
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Registers update listener to update config entry when options are updated.
    # entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    #####################################
    # Create entites for each platform with dependency on coordinator
    #####################################
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Must wait for entities to be created, otherwise will fail after adding Tesla or OCPP charger, eg.
    # ValueError: tesla_custom_tesla23m3: charger_plugged_in_sensor: Failed to get entity ID
    # Most likely coordinator init had fail, or init had failed causing entities not to be available on first run.
    # Restart for second run and SolarCharger spinned up without issue.
    await asyncio.sleep(3)

    #####################################
    # Initialise coordinator and charge control after _PLATFORMS entities
    #####################################
    await coordinator.async_setup()

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
