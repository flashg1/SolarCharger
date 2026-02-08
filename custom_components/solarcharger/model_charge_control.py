"""Data models."""

from asyncio import Task
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

# from .chargers.controller import ChargeController

#######################################################
# Problem: Circular imports
# SolarChargerCoordinator > ChargeControl > SolarChargerSensorEntity > SolarChargerCoordinator
#
# Not a good solution:
# Comment out exact entity imports to circumvent circular import error detection
# Use type Any to break the circular dependency!!!
# from typing import Any
# sensors: dict[str, Any] | None = None
# switches: dict[str, Any] | None = None
#
# Use one of following solutions:
# from __future__ import annotations
#   Affects all type annotations in the module, making them string literals, even if the type is readily available.
# if TYPE_CHECKING:
#   Specifically targets imports that are only needed for type checking, preventing them from being executed at runtime.
#   You still need to use string literals for forward references if the type isn't available at runtime.
#######################################################
if TYPE_CHECKING:
    from .button import SolarChargerButtonActionEntity
    from .datetime import SolarChargerDateTimeConfigEntity
    from .input_datetime import SolarChargerInputTimeConfigEntity
    from .number import SolarChargerNumberConfigEntity
    from .sensor import SolarChargerSensorEntity
    from .switch import SolarChargerSwitchEntity
    from .time import SolarChargerTimeConfigEntity


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ChargeControl:
    """Data structure for charger data."""

    subentry_id: str
    config_name: str
    # Callbacks
    # unsub_callbacks: dict[str, CALLBACK_TYPE]

    # controller: ChargeController | None = None

    charge_task: Task | None = None
    instance_count: int = 0
    end_charge_task: Task | None = None
    # last_charger_target_update: tuple[float, int] | None = (
    #     None  # (new_current, timestamp)
    # )

    sensors: dict[str, "SolarChargerSensorEntity"] | None = None
    numbers: dict[str, "SolarChargerNumberConfigEntity"] | None = None
    switches: dict[str, "SolarChargerSwitchEntity"] | None = None
    buttons: dict[str, "SolarChargerButtonActionEntity"] | None = None
    times: dict[str, "SolarChargerTimeConfigEntity"] | None = None
    datetimes: dict[str, "SolarChargerDateTimeConfigEntity"] | None = None

    # Cannot get input_datetime to work, so input_times is not used.
    input_times: dict[str, "SolarChargerInputTimeConfigEntity"] | None = None

    # Sensors
    sensor_last_check_timestamp: datetime | None = None

    # Switches
    switch_charge: bool | None = None


# type ChargerConfigEntry = ConfigEntry[ChargeControl]
