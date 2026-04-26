# ruff: noqa: TID252
"""Device control data model."""

from dataclasses import dataclass

from ..chargers.controller import ChargeController


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class DeviceControl:
    """Data structure for charge controller."""

    subentry_id: str
    config_name: str

    controller: ChargeController
