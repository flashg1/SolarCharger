"""Solar Charger Integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

# from . import config_flow as cf
from . import config_subentry_flow as csef
from .chargers import Charger, charger_factory
from .chargers.controller import ChargeController
from .const import DOMAIN
from .coordinator import SolarChargerCoordinator
from .models import ChargeControl

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    # Platform.NUMBER,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Solar Charger integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


# ----------------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar Charger from a config entry."""

    # Initialize coordinator
    coordinator = SolarChargerCoordinator(
        hass=hass,
        config_entry=entry,
    )
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up subentries (e.g., chargers)
    charge_controls: dict[str, ChargeControl] = {}
    coordinator.charge_controls = charge_controls

    for subentry in entry.subentries.values():
        if subentry.subentry_type == csef.SUBENTRY_TYPE_CHARGER:
            # Initialize charger
            charger_device_id: str | None = subentry.data.get(
                csef.SUBENTRY_CHARGER_DEVICE
            )
            if not charger_device_id or not subentry.unique_id:
                _LOGGER.error(
                    "No charger device ID found in subentry data: %s: %s",
                    subentry.unique_id,
                    subentry.subentry_id,
                )
                continue
            charger: Charger = await charger_factory(
                hass, entry, subentry, charger_device_id
            )

            # Initialize ChargeController
            controller: ChargeController = ChargeController(
                hass, entry, subentry, charger
            )

            # Store in charge_controls dictionary
            charge_controls[subentry.subentry_id] = ChargeControl(
                subentry_id=subentry.subentry_id,
                device_name=subentry.unique_id,
                charger=charger,
                controller=controller,
            )

            _LOGGER.info(
                "Setting up entry with charger '%s'",
                charger.__class__.__name__,
            )

    await coordinator.async_setup()
    _LOGGER.warning("SolarChargerCoordinator initialized for %s", entry.entry_id)

    # Registers update listener to update config entry when options are updated.
    # entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Create entites for each platform
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    _LOGGER.debug("SolarCharger initialized for %s", entry.entry_id)
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
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    if unloaded and coordinator:  # Ensure coordinator was found before trying to pop
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unloaded  # Return the result of unloading platforms
