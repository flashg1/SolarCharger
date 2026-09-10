# ruff: noqa: SLF001
"""Unit tests for SolarCharge (state_machine/solar_charge.py).

SolarCharge.__init__ wires up a Tracker, ControlEntities, a Charger/Chargeable
pair and reads config_entry.data for the current-update period -- none of
which get_charger_effective_voltage() touches (it only resolves one option
entity through the inherited ScOptionState/ScConfigState/ScState chain).
Constructing a full SolarCharge just to test that one getter would mean
building fakes for the whole session object graph to satisfy attributes the
test never uses, so these tests bypass __init__ via SolarCharge.__new__() and
set only the four attributes ScState/ScConfigState/ScOptionState actually
read: _hass, _entry, _subentry, caller.
"""

from types import SimpleNamespace

from custom_components.solarcharger.const import (
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MIN_CURRENT,
)
from custom_components.solarcharger.state_machine.solar_charge import SolarCharge
import pytest

from homeassistant.config_entries import ConfigSubentry

from .conftest import FakeConfigEntry, make_config_entry, make_hass, make_subentry

TESLA23M3_SUBENTRY_ID = "tesla23m3"


# ----------------------------------------------------------------------------
def make_bare_solar_charge(
    hass: object,
    entry: FakeConfigEntry,
    subentry: ConfigSubentry,
    *,
    charger: object | None = None,
    entities: object | None = None,
) -> SolarCharge:
    """Build a SolarCharge exposing only a handful of ScState-chain attributes.

    charger and entities are only set by tests that exercise
    get_charger_min_current()/validate_current() -- they stand in for the
    Charger instance and the ControlEntities.numbers used by the direct=True
    lookup path, respectively.
    """
    solar_charge = SolarCharge.__new__(SolarCharge)
    solar_charge._hass = hass
    solar_charge._entry = entry
    solar_charge._subentry = subentry
    solar_charge.caller = subentry.unique_id
    solar_charge.charger = charger
    solar_charge.entities = entities
    return solar_charge


def make_fake_charger(max_current: float) -> SimpleNamespace:
    """Minimal stand-in for a Charger: only get_max_charge_current() is read here."""
    return SimpleNamespace(get_max_charge_current=lambda: max_current)


# ----------------------------------------------------------------------------
# get_charger_effective_voltage() -- voltage = 230 V
# ----------------------------------------------------------------------------
def test_get_charger_effective_voltage_reads_configured_number_entity() -> None:
    """Effective voltage comes from the configured number entity's state."""
    hass = make_hass({"number.tesla23m3_voltage": "230"})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_EFFECTIVE_VOLTAGE: "number.tesla23m3_voltage"
            }
        },
    )
    solar_charge = make_bare_solar_charge(hass, entry, subentry)

    assert solar_charge.get_charger_effective_voltage() == 230.0


@pytest.mark.parametrize(
    "voltage",
    [
        pytest.param("0", id="zero_voltage"),
        pytest.param("-230", id="negative_voltage"),
    ],
)
def test_get_charger_effective_voltage_rejects_non_positive_value(
    voltage: str,
) -> None:
    """A configured but non-positive voltage is treated as invalid, not silently used."""
    hass = make_hass({"number.tesla23m3_voltage": voltage})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_EFFECTIVE_VOLTAGE: "number.tesla23m3_voltage"
            }
        },
    )
    solar_charge = make_bare_solar_charge(hass, entry, subentry)

    with pytest.raises(ValueError, match="Invalid charger effective voltage"):
        solar_charge.get_charger_effective_voltage()


def test_get_charger_effective_voltage_raises_when_unconfigured() -> None:
    """No configured entity aborts rather than silently returning a default."""
    hass = make_hass()
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(subentry, options={subentry.unique_id: {}})
    solar_charge = make_bare_solar_charge(hass, entry, subentry)

    with pytest.raises(ValueError, match="Failed to get entity number value"):
        solar_charge.get_charger_effective_voltage()


# ----------------------------------------------------------------------------
# validate_current() -- clamps to [0, max_current], never raises
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("current", "max_current", "expected"),
    [
        pytest.param(-5, 15, 0, id="negative_clamps_to_zero"),
        pytest.param(20, 15, 15, id="above_max_clamps_to_max"),
        pytest.param(7.5, 15, 7.5, id="within_range_passes_through_unchanged"),
        pytest.param(0, 15, 0, id="zero_passes_through_unchanged"),
        pytest.param(15, 15, 15, id="exactly_max_passes_through_unchanged"),
    ],
)
def test_validate_current_clamps_to_explicit_max_current(
    current: float, max_current: float, expected: float
) -> None:
    """With max_current given explicitly, validate_current() needs no charger at all."""
    solar_charge = make_bare_solar_charge(
        make_hass(), make_config_entry(), make_subentry(TESLA23M3_SUBENTRY_ID)
    )

    assert solar_charge.validate_current(current, max_current) == expected


def test_validate_current_falls_back_to_charger_max_current_when_not_given() -> None:
    """Without an explicit max_current, validate_current() asks the attached charger."""
    solar_charge = make_bare_solar_charge(
        make_hass(),
        make_config_entry(),
        make_subentry(TESLA23M3_SUBENTRY_ID),
        charger=make_fake_charger(max_current=15),
    )

    assert solar_charge.validate_current(20) == 15


# ----------------------------------------------------------------------------
# get_charger_min_current() -- min current = 0 A, max current = 15 A
# ----------------------------------------------------------------------------
def test_get_charger_min_current_reads_configured_entity() -> None:
    """Min current comes from the configured number entity, clamped against max current."""
    hass = make_hass({"number.tesla23m3_min_current": "0"})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_MIN_CURRENT: "number.tesla23m3_min_current"
            }
        },
    )
    solar_charge = make_bare_solar_charge(
        hass, entry, subentry, charger=make_fake_charger(max_current=15)
    )

    assert solar_charge.get_charger_min_current() == 0.0


@pytest.mark.parametrize(
    ("configured_min_current", "expected"),
    [
        pytest.param("-3", 0, id="negative_config_clamps_to_zero"),
        pytest.param("20", 15, id="config_above_max_clamps_to_max"),
    ],
)
def test_get_charger_min_current_clamps_a_misconfigured_value(
    configured_min_current: str, expected: float
) -> None:
    """A min-current option outside [0, max_current] is clamped, not trusted as-is."""
    hass = make_hass({"number.tesla23m3_min_current": configured_min_current})
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(
        subentry,
        options={
            subentry.unique_id: {
                NUMBER_CHARGER_MIN_CURRENT: "number.tesla23m3_min_current"
            }
        },
    )
    solar_charge = make_bare_solar_charge(
        hass, entry, subentry, charger=make_fake_charger(max_current=15)
    )

    assert solar_charge.get_charger_min_current() == expected


def test_get_charger_min_current_direct_reads_control_entity_state_instead() -> None:
    """direct=True reads the live ControlEntities.numbers state, bypassing config options.

    This is the path get_number_state() takes -- entities.numbers is a dict
    of the actual SolarChargerNumberConfigEntity objects, so a plain object
    exposing .state stands in for one here.
    """
    solar_charge = make_bare_solar_charge(
        make_hass(),
        make_config_entry(),
        make_subentry(TESLA23M3_SUBENTRY_ID),
        charger=make_fake_charger(max_current=15),
        entities=SimpleNamespace(
            numbers={NUMBER_CHARGER_MIN_CURRENT: SimpleNamespace(state=0)}
        ),
    )

    assert solar_charge.get_charger_min_current(direct=True) == 0.0
