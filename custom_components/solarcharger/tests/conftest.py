"""Shared fakes and builders for power allocator tests.

PowerAllocator only ever touches DeviceControl.controller.solar_charge and
.controller.charge_control.instance_count, so tests use small fakes for those
instead of constructing real ChargeController/HomeAssistant objects.
"""

from dataclasses import dataclass
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest

# Allow "import custom_components.solarcharger..." without a running Home
# Assistant instance. custom_components/ has no __init__.py, but Python's
# implicit namespace packages make it importable once "config" is on the path.
_CONFIG_DIR = Path(__file__).resolve().parents[3]
if str(_CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(_CONFIG_DIR))

from custom_components.solarcharger.const import (  # noqa: E402
    OPTION_GLOBAL_DEFAULTS_ID,
    RunState,
)
from custom_components.solarcharger.models.model_allocation import (  # noqa: E402
    AllocationGroup,
    PowerAllocation,
)
from custom_components.solarcharger.models.model_device_control import (  # noqa: E402
    DeviceControl,
)
import custom_components.solarcharger.modules.allocator as allocator_module  # noqa: E402
from custom_components.solarcharger.modules.allocator import (  # noqa: E402
    PowerAllocator,
)

GLOBAL_DEFAULTS_SUBENTRY_ID = "global-defaults"


@dataclass
class FakeSolarCharge:
    """Stand-in for state_machine.solar_charge.SolarCharge."""

    priority: int = 10
    allocation_weight: float = 1.0
    max_current: float = 16.0
    voltage: float = 230.0
    power_factor: float = 1.0
    share_allocation: int = 1
    self_depower: bool = False
    can_set_current: bool = True
    max_speed_charge: bool = False
    consumed_power: float = 0.0
    activation_power: float = -100.0
    adjusted_activation_power: float = -100.0
    net_power: float | None = 0.0
    run_state: RunState = RunState.CHARGE
    rebalance_needed: bool = False

    def get_charger_priority(self) -> int:
        """Return configured priority."""
        return self.priority

    def get_charger_power_allocation_weight(self) -> float:
        """Return configured allocation weight."""
        return self.allocation_weight

    def get_charger_max_current(self) -> float:
        """Return configured max current."""
        return self.max_current

    def get_charger_effective_voltage(self) -> float:
        """Return configured voltage."""
        return self.voltage

    def get_charger_power_factor(self) -> float:
        """Return configured power factor."""
        return self.power_factor

    def get_share_allocation(self) -> int:
        """Return configured share allocation."""
        return self.share_allocation

    @property
    def is_self_depower(self) -> bool:
        """Return configured self-depower flag."""
        return self.self_depower

    def get_adjusted_activation_power(self, run_state: RunState) -> tuple[float, float]:
        """Return configured (adjusted_activation_power, activation_power)."""
        return self.adjusted_activation_power, self.activation_power

    def need_rebalance(self) -> bool:
        """Return configured need-rebalance flag."""
        return self.rebalance_needed

    def set_need_rebalance(self, need_rebalance: bool) -> None:
        """Record need-rebalance flag."""
        self.rebalance_needed = need_rebalance

    def is_max_speed_charge(self) -> bool:
        """Return configured max-speed-charge flag."""
        return self.max_speed_charge

    def get_consumed_power(self) -> float:
        """Return configured consumed power."""
        return self.consumed_power

    def set_consumed_power(self, val: float) -> None:
        """Record consumed power."""
        self.consumed_power = val

    def get_net_power(self) -> float | None:
        """Return configured net power."""
        return self.net_power

    @property
    def machine_state(self) -> SimpleNamespace:
        """Return an object exposing .state, like SolarChargeState."""
        return SimpleNamespace(state=self.run_state)


@dataclass
class FakeChargeControl:
    """Stand-in for model_charge_control.ChargeControl."""

    instance_count: int = 1


@dataclass
class FakeChargeController:
    """Stand-in for modules.controller.ChargeController."""

    solar_charge: FakeSolarCharge
    charge_control: FakeChargeControl


def make_device_control(
    subentry_id: str,
    config_name: str,
    *,
    instance_count: int = 1,
    **solar_charge_overrides: Any,
) -> DeviceControl:
    """Build a DeviceControl backed by fake solar_charge/charge_control."""
    controller = FakeChargeController(
        solar_charge=FakeSolarCharge(**solar_charge_overrides),
        charge_control=FakeChargeControl(instance_count=instance_count),
    )
    return DeviceControl(
        subentry_id=subentry_id, config_name=config_name, controller=controller
    )


def make_allocator(
    *device_controls: DeviceControl, net_power: float | None = 0.0
) -> PowerAllocator:
    """Build a PowerAllocator with a global-defaults control plus given devices."""
    global_control = make_device_control(
        GLOBAL_DEFAULTS_SUBENTRY_ID,
        OPTION_GLOBAL_DEFAULTS_ID,
        instance_count=0,
        net_power=net_power,
    )
    controls: dict[str, DeviceControl] = {GLOBAL_DEFAULTS_SUBENTRY_ID: global_control}
    for control in device_controls:
        controls[control.subentry_id] = control

    global_defaults_subentry = SimpleNamespace(subentry_id=GLOBAL_DEFAULTS_SUBENTRY_ID)
    return PowerAllocator(global_defaults_subentry, controls)  # type: ignore[arg-type]


def make_power_allocation(**overrides: Any) -> PowerAllocation:
    """Build a PowerAllocation with sensible defaults, overridden per test."""
    defaults: dict[str, Any] = {
        "subentry_id": "member",
        "name": "Member",
        "max_power": 2000.0,
        "max_current": 8.7,
        "activation_power": -100.0,
        "adjusted_activation_power": -100.0,
        "priority": 10,
        "allocation_weight": 1.0,
        "instance": 1,
        "share_allocation": 1,
        "can_set_current": True,
    }
    defaults.update(overrides)
    return PowerAllocation(**defaults)


def make_group(priority: int = 10, **overrides: Any) -> AllocationGroup:
    """Build an AllocationGroup with sensible defaults, overridden per test."""
    defaults: dict[str, Any] = {"priority": priority, "member_map": {}}
    defaults.update(overrides)
    return AllocationGroup(**defaults)


@pytest.fixture(name="allocation_calls")
def allocation_calls_fixture(monkeypatch: pytest.MonkeyPatch) -> dict[int, float]:
    """Capture every delta power sent, keyed by the charge_control's identity."""
    calls: dict[int, float] = {}

    async def fake_async_set_delta_allocated_power(
        charge_control: FakeChargeControl, delta_power: float
    ) -> bool:
        calls[id(charge_control)] = delta_power
        return True

    monkeypatch.setattr(
        allocator_module,
        "async_set_delta_allocated_power",
        fake_async_set_delta_allocated_power,
    )
    return calls
