# ruff: noqa: SLF001
"""Unit tests for StateCharge (state_machine/state_charge.py).

Self-depower only matters for a charger that cannot set its own current --
exactly the "Hot water" element from test_user_custom_charger.py
(can_set_charge_current() is False there). For such a device, SolarCharger
cannot dial current down itself; it can only detect that the *device*
reduced its own draw (eg. a thermostat cutting out) and mark the session as
self-depowered, so the allocator stops counting that charger's theoretical
share as available (see modules/allocator.py's self_depower handling).

_async_charge_device() is the actual per-second charge loop: it repeatedly
polls status via solarcharge.async_set_charge_status(), switches the charger
on exactly once, checks for calibration, and tolerates transient failures up
to MAX_CONSECUTIVE_FAILURE_COUNT. That method alone drives the real schedule
calculation, charge-limit logic and HA entity updates through SolarCharge, so
testing it here means scripting a fake SolarCharge that returns a canned
sequence of ContextData results instead -- these tests are about the loop's
own control flow (when it switches on, when it stops, how failures are
counted), not about the status-evaluation logic that produces each
ContextData, which belongs to SolarCharge's own tests.

StateCharge.__init__ is a plain `self.state = RunState.CHARGE`, and
`solarcharge` is a settable property (see SolarChargeState), so a real
StateCharge can be built directly and pointed at a fake SolarCharge context
rather than a full session object graph.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from custom_components.solarcharger.const import (
    MAX_CONSECUTIVE_FAILURE_COUNT,
    ChargeStatus,
    RunState,
)
from custom_components.solarcharger.models.model_charge_stats import ChargeStats
from custom_components.solarcharger.models.model_context_data import ContextData
from custom_components.solarcharger.state_machine.state_charge import StateCharge
import pytest

from .conftest import FakeSolarCharge

HOT_WATER_MAX_CURRENT = 15.0  # matches test_user_custom_charger.py


# ----------------------------------------------------------------------------
def make_state_charge(fake_solar_charge: object) -> StateCharge:
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


# ----------------------------------------------------------------------------
# _async_charge_device() -- the per-second charge loop
# ----------------------------------------------------------------------------
def make_context(next_step: ChargeStatus) -> ContextData:
    """Build a ContextData carrying only the field _async_charge_device() reads."""
    return ContextData(
        charger=None,  # type: ignore[arg-type]
        chargeable=None,  # type: ignore[arg-type]
        state=RunState.CHARGE,
        goal=None,  # type: ignore[arg-type]
        net_allocations=None,  # type: ignore[arg-type]
        stats=ChargeStats(),
        next_step=next_step,
    )


def make_loop_solarcharge(
    stats: ChargeStats, context_sequence: list[ContextData]
) -> SimpleNamespace:
    """Stand-in for SolarCharge, scripted for the loop's control flow only.

    async_set_charge_status() hands back context_sequence one item per call,
    in order -- callers script it to match how many iterations of the loop
    are expected to reach that point. abort_if_exceed_max_consecutive_failure()
    re-implements the real threshold check against the same `stats` object
    _async_charge_device() mutates, since in production they are the same
    ChargeStats instance (see StateCharge.async_activate_state()).
    """

    def abort_if_exceed_max_consecutive_failure() -> None:
        if stats.loop_consecutive_fail_count > MAX_CONSECUTIVE_FAILURE_COUNT:
            raise RuntimeError(
                "Exceeded max number of allowable consecutive failures "
                f"({MAX_CONSECUTIVE_FAILURE_COUNT}) in charge loop"
            )

    return SimpleNamespace(
        caller="hot_water",
        last_charge_current=0.0,
        abort_if_exceed_max_consecutive_failure=abort_if_exceed_max_consecutive_failure,
        async_update_ha=AsyncMock(),
        async_set_charge_status=AsyncMock(side_effect=context_sequence),
        async_charger_sleep=AsyncMock(),
        tracker=SimpleNamespace(untrack_sync_update=Mock()),
    )


def make_charging_state(fake_solar_charge: SimpleNamespace) -> StateCharge:
    """Build a StateCharge with its switch-on/calibration collaborators stubbed out.

    Those two are private StateCharge methods, not SolarCharge's, so they are
    replaced directly on the instance -- these tests are only about when the
    loop calls them, not what they do.
    """
    state = make_state_charge(fake_solar_charge)
    state._switch_on_charger_and_set_current = AsyncMock()
    state._async_calibrate_max_charge_speed_if_required = AsyncMock()
    return state


async def test_loop_ends_immediately_without_switching_on_charger() -> None:
    """First status check already says stop: no switch-on, no calibration, no trailing sleep."""
    stats = ChargeStats()
    final_context = make_context(ChargeStatus.CHARGE_END)
    fake_solar_charge = make_loop_solarcharge(stats, [final_context])
    state = make_charging_state(fake_solar_charge)

    result = await state._async_charge_device(None, None, RunState.CHARGE, stats)

    assert result is final_context
    fake_solar_charge.async_update_ha.assert_awaited_once()
    fake_solar_charge.async_set_charge_status.assert_awaited_once()
    state._switch_on_charger_and_set_current.assert_not_awaited()
    state._async_calibrate_max_charge_speed_if_required.assert_not_awaited()
    fake_solar_charge.async_charger_sleep.assert_not_awaited()
    fake_solar_charge.tracker.untrack_sync_update.assert_not_called()
    assert stats.loop_success_count == 0
    assert stats.loop_total_count == 0


async def test_loop_switches_on_charger_only_once_across_iterations() -> None:
    """Two CONTINUE iterations then a stop: switch-on ran once, calibration ran each time."""
    stats = ChargeStats()
    contexts = [
        make_context(ChargeStatus.CHARGE_CONTINUE),
        make_context(ChargeStatus.CHARGE_CONTINUE),
        make_context(ChargeStatus.CHARGE_PAUSE),
    ]
    fake_solar_charge = make_loop_solarcharge(stats, contexts)
    state = make_charging_state(fake_solar_charge)

    result = await state._async_charge_device(None, None, RunState.CHARGE, stats)

    assert result is contexts[-1]
    assert state._switch_on_charger_and_set_current.await_count == 1
    assert state._async_calibrate_max_charge_speed_if_required.await_count == 2
    # The terminating (3rd) iteration breaks before reaching the trailing sleep.
    assert fake_solar_charge.async_charger_sleep.await_count == 2
    assert stats.loop_success_count == 2
    assert stats.loop_total_count == 2
    fake_solar_charge.tracker.untrack_sync_update.assert_called_once()


async def test_loop_recovers_from_a_transient_failure_and_resets_the_streak() -> None:
    """A failed iteration counts as a failure; the next successful CONTINUE clears the streak."""
    stats = ChargeStats()
    contexts = [
        make_context(ChargeStatus.CHARGE_CONTINUE),
        make_context(ChargeStatus.CHARGE_END),
    ]
    fake_solar_charge = make_loop_solarcharge(stats, contexts)
    # 1st iteration fails before async_set_charge_status is even reached.
    fake_solar_charge.async_update_ha.side_effect = [
        ValueError("transient"),
        None,
        None,
    ]
    state = make_charging_state(fake_solar_charge)

    await state._async_charge_device(None, None, RunState.CHARGE, stats)

    assert stats.loop_total_fail_count == 1
    assert stats.loop_consecutive_fail_count == 0
    assert stats.loop_success_count == 1
    assert stats.loop_total_count == 2


async def test_loop_aborts_after_exceeding_max_consecutive_failures() -> None:
    """Enough consecutive failures abort the whole state, not just log and keep retrying forever."""
    stats = ChargeStats()
    fake_solar_charge = make_loop_solarcharge(stats, [])
    fake_solar_charge.async_update_ha.side_effect = ValueError("permanently broken")
    state = make_charging_state(fake_solar_charge)

    with pytest.raises(
        RuntimeError, match="Exceeded max number of allowable consecutive failures"
    ):
        await state._async_charge_device(None, None, RunState.CHARGE, stats)

    assert stats.loop_consecutive_fail_count == MAX_CONSECUTIVE_FAILURE_COUNT + 1
    fake_solar_charge.async_set_charge_status.assert_not_awaited()
