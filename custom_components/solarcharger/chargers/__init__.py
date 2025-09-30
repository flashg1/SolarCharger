"""Solar Charger Chargers."""

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

# from .controller import ChargeController
# from .chargeable import Chargeable
from .charger import Charger
from .ocpp_charger import OcppCharger
from .tesla_custom_charger import TeslaCustomCharger

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry


async def charger_factory(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    config_subentry: ConfigSubentry,
    device_entry_id: str,
) -> Charger:
    """Create a charger instance based on the device's properties."""

    if not device_entry_id:
        raise ValueError("Device entry ID is required to create a charger.")

    registry = dr.async_get(hass)
    device: DeviceEntry | None = registry.async_get(device_entry_id)

    if not device:
        msg = f"Device with ID {device_entry_id} not found in registry."
        raise ValueError(msg)

    for charger_cls in [
        OcppCharger,
        TeslaCustomCharger,
    ]:
        if charger_cls.is_charger_device(device):
            return charger_cls(hass, config_entry, config_subentry, device)

    msg = f"Unsupported device: {device.name} (ID: {device_entry_id}). "
    raise ValueError(msg)
