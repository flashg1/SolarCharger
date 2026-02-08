"""Data models."""

from dataclasses import dataclass

from .chargers.controller import ChargeController


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class DeviceControl:
    """Data structure for charger data."""

    subentry_id: str
    config_name: str

    controller: ChargeController
