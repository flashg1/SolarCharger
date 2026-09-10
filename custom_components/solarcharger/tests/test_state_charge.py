# ruff: noqa: SLF001
"""Unit tests for StateCharge's self-depower tracking (state_machine/state_charge.py).

Self-depower only matters for a charger that cannot set its own current --
exactly the "Hot water" element from test_user_custom_charger.py
(can_set_charge_current() is False there). For such a device, SolarCharger
cannot dial current down itself; it can only detect that the *device*
reduced its own draw (eg. a thermostat cutting out) and mark the session as
self-depowered, so the allocator stops counting that charger's theoretical
share as available (see modules/allocator.py's self_depower handling).

StateCharge.__init__ is a plain `self.state = RunState.CHARGE`, and
`solarcharge` is a settable property (see SolarChargeState), so a real
StateCharge can be built directly and pointed at the existing FakeSolarCharge
fixture from conftest.py rather than a full session object graph.
"""

from custom_components.solarcharger.const import RunState
from custom_components.solarcharger.state_machine.state_charge import StateCharge

from .conftest import FakeSolarCharge

HOT_WATER_MAX_CURRENT = 15.0  # matches test_user_custom_charger.py


# ----------------------------------------------------------------------------
def make_state_charge(fake_solar_charge: FakeSolarCharge) -> StateCharge:
    """Build a StateCharge pointed at the given fake SolarCharge context."""
    state = StateCharge()
    state.solarcharge = fake_solar_charge  # type: ignore[assignment]
    return state


# ----------------------------------------------------------------------------
# _update_self_depower_state() -- only acts for chargers that cannot set current
# ----------------------------------------------------------------------------
def test_device_reducing_current_on_its_own_marks_self_depower() -> None:
    """A real drop in current (well beyond noise) flags self-depower and counts it."""
    fake_solar_charge = FakeSolarCharge(
        can_set_current=False,
        max_current=HOT_WATER_MAX_CURRENT,
        self_depower=False,
        self_depower_today=2,
    )
    state = make_state_charge(fake_solar_charge)

    state._update_self_depower_state(new_current=10.0, old_current=15.0)

    assert fake_solar_charge.self_depower is True
    assert fake_solar_charge.self_depower_today == 3
    assert fake_solar_charge.run_state == RunState.SELF_DEPOWER


def test_device_returning_to_max_current_clears_self_depower() -> None:
    """Once the device is back at max current, self-depower is cleared."""
    fake_solar_charge = FakeSolarCharge(
        can_set_current=False,
        max_current=HOT_WATER_MAX_CURRENT,
        self_depower=True,
        self_depower_today=3,
    )
    state = make_state_charge(fake_solar_charge)

    state._update_self_depower_state(new_current=15.0, old_current=10.0)

    assert fake_solar_charge.self_depower is False
    assert fake_solar_charge.run_state == RunState.CHARGE
    # Only a detected drop increments the counter, not a return to max.
    assert fake_solar_charge.self_depower_today == 3


def test_steady_partial_current_leaves_self_depower_state_unchanged() -> None:
    """A stable current that is neither a real drop nor at max current changes nothing.

    old=10 -> new=10.3 is within the allowed current variation of old (so not
    "reduced by itself"), and nowhere near max_current=15 (so not "at max
    current" either) -- neither branch of _update_self_depower_state() fires.
    """
    fake_solar_charge = FakeSolarCharge(
        can_set_current=False,
        max_current=HOT_WATER_MAX_CURRENT,
        self_depower=True,
        self_depower_today=3,
    )
    state = make_state_charge(fake_solar_charge)

    state._update_self_depower_state(new_current=10.3, old_current=10.0)

    assert fake_solar_charge.self_depower is True
    assert fake_solar_charge.self_depower_today == 3


def test_charger_that_can_set_current_is_never_flagged_self_depower() -> None:
    """Self-depower tracking is a no-op for chargers SolarCharger can throttle itself.

    Unlike the hot water element, a settable charger (eg. Tesla Custom) is
    never expected to change its own current -- any drop was commanded by
    SolarCharger, not the device, so there is nothing to detect here.
    """
    fake_solar_charge = FakeSolarCharge(
        can_set_current=True,
        max_current=HOT_WATER_MAX_CURRENT,
        self_depower=False,
        self_depower_today=0,
    )
    state = make_state_charge(fake_solar_charge)

    state._update_self_depower_state(new_current=0.0, old_current=15.0)

    assert fake_solar_charge.self_depower is False
    assert fake_solar_charge.self_depower_today == 0
    assert fake_solar_charge.run_state == RunState.CHARGE
