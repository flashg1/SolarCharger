# ruff: noqa: SLF001
"""Unit tests for ChargeScheduler (state_machine/scheduler.py).

ChargeScheduler.__init__ only wires up ScOptionState plus two trivial local
fields, so unlike SolarCharge it can be constructed directly with the same
hass/entry/subentry fakes used elsewhere in this suite.
"""

from custom_components.solarcharger.const import NUMBER_CHARGER_MAX_SPEED
from custom_components.solarcharger.state_machine.scheduler import ChargeScheduler
import pytest

from .conftest import make_config_entry, make_hass, make_subentry

TESLA23M3_SUBENTRY_ID = "tesla23m3"


# ----------------------------------------------------------------------------
def make_scheduler(
    max_charge_speed: str | None,
) -> ChargeScheduler:
    """Build a ChargeScheduler with the given max-charge-speed option configured."""
    options: dict[str, str] = {}
    states: dict[str, str] = {}
    if max_charge_speed is not None:
        options[NUMBER_CHARGER_MAX_SPEED] = "number.tesla23m3_max_speed"
        states["number.tesla23m3_max_speed"] = max_charge_speed

    hass = make_hass(states)
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(subentry, options={subentry.unique_id: options})
    return ChargeScheduler(hass, entry, subentry)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# _get_one_percent_charge_duration() -- max charge speed = 6.1 %/hr
# ----------------------------------------------------------------------------
def test_one_percent_charge_duration_is_an_hour_divided_by_max_speed() -> None:
    """One percent of charge takes (3600 seconds / configured %-per-hour) to complete."""
    scheduler = make_scheduler("6.1")

    assert scheduler._get_one_percent_charge_duration() == pytest.approx(3600 / 6.1)


def test_one_percent_charge_duration_raises_when_unconfigured() -> None:
    """No configured max-speed entity aborts rather than dividing by a default."""
    scheduler = make_scheduler(None)

    with pytest.raises(ValueError, match="Failed to get entity number value"):
        scheduler._get_one_percent_charge_duration()


def test_one_percent_charge_duration_raises_zero_division_at_zero_speed() -> None:
    """A calibrated max speed of exactly 0 %/hr is not guarded against divide-by-zero.

    Pinned as a characterization test: if 0 becomes a legitimate calibration
    outcome, this method needs a guard, not just a passing test.
    """
    scheduler = make_scheduler("0")

    with pytest.raises(ZeroDivisionError):
        scheduler._get_one_percent_charge_duration()
