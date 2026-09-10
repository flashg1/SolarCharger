"""Unit tests for UserCustomCharger (chargers/user_custom_charger.py).

Modeled on a "Hot water" element: switch-controlled, no adjustable current.

Like TeslaCustomCharger, UserCustomCharger only adds device-identity checks;
everything else comes from the inherited ChargerChargeableBase/ScOptionState
chain (see test_tesla_custom_charger.py for that harness's rationale -- the
_stub_entity_registry fixture and make_hass() below follow the same pattern).

Unlike TeslaCustomCharger, a hot water element is identified by the
solarcharger integration's own DOMAIN, not a third-party integration domain
-- there is no external API device to match against.

Out of scope here, same as for Tesla Custom: charger_effective_voltage and
charger_min_current are not read by UserCustomCharger/ChargerChargeableBase at
all.
  - charger_effective_voltage is read by SolarCharge.get_charger_effective_
    voltage() -- see test_solar_charge.py, whose behaviour does not depend on
    which charger class is attached, so it is not repeated per-charger here.
  - charger_min_current is read only by SolarCharge.validate_current() (state_
    machine/solar_charge.py), which has no test module yet.
The three "min workable" parameters, by contrast, ARE directly callable here:
they are defined on ScOptionState itself, which ChargerChargeableBase (and so
UserCustomCharger) inherits directly.

No charger_set_charge_current entity is configured, matching the parameters
given for this device -- a resistive hot water element is switched on/off,
not throttled, so can_set_charge_current() is expected to be False throughout.
"""

from types import SimpleNamespace

from custom_components.solarcharger.chargers import ha_device as ha_device_module
from custom_components.solarcharger.chargers.user_custom_charger import (
    UserCustomCharger,
)
from custom_components.solarcharger.const import (
    DOMAIN,
    ENTITY_CHARGER_GET_CHARGE_CURRENT,
    ENTITY_CHARGER_ON_OFF_SWITCH,
    NUMBER_CHARGER_MAX_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT,
    NUMBER_CHARGER_MIN_WORKABLE_POWER_PAUSE_THRESHOLD,
    NUMBER_CHARGER_MIN_WORKABLE_POWER_RESUME_THRESHOLD,
)
import pytest

from .conftest import make_config_entry, make_hass, make_subentry

HOT_WATER_SUBENTRY_ID = "hot_water"

HOT_WATER_OPTIONS = {
    ENTITY_CHARGER_GET_CHARGE_CURRENT: "sensor.hot_water_charge_current",
    NUMBER_CHARGER_MAX_CURRENT: "number.hot_water_max_current",
    NUMBER_CHARGER_MIN_WORKABLE_CURRENT: "number.hot_water_min_workable_current",
    NUMBER_CHARGER_MIN_WORKABLE_POWER_PAUSE_THRESHOLD: (
        "number.hot_water_pause_threshold"
    ),
    NUMBER_CHARGER_MIN_WORKABLE_POWER_RESUME_THRESHOLD: (
        "number.hot_water_resume_threshold"
    ),
    ENTITY_CHARGER_ON_OFF_SWITCH: "switch.hot_water_element",
}

HOT_WATER_STATES = {
    "number.hot_water_max_current": "15",
    "number.hot_water_min_workable_current": "15",
    "number.hot_water_pause_threshold": "-10",
    "number.hot_water_resume_threshold": "-5",
}


# ----------------------------------------------------------------------------
# Local fakes
# ----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _stub_entity_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """HaDevice.__init__() looks up the real entity registry on construction.

    None of the methods under test read entities through it (they all go
    through ScOptionState.option_get_id() + hass.states.get() instead), so an
    empty stub is enough to let the charger construct.
    """
    fake_registry = SimpleNamespace(
        entities=SimpleNamespace(get_entries_for_device_id=lambda *args, **kwargs: [])
    )
    monkeypatch.setattr(ha_device_module.er, "async_get", lambda hass: fake_registry)


def make_hot_water_charger(
    hass: SimpleNamespace,
    *,
    options: dict[str, str] | None = None,
    identifiers: set[tuple[str, str]] | None = None,
) -> UserCustomCharger:
    """Build a UserCustomCharger backed by the given fake hass and option config."""
    subentry = make_subentry(HOT_WATER_SUBENTRY_ID)
    entry = make_config_entry(subentry, options={subentry.unique_id: (options or {})})
    device = SimpleNamespace(
        id="device-1",
        identifiers=identifiers or {(DOMAIN, "hot_water")},
    )
    return UserCustomCharger(
        hass,
        entry,  # type: ignore[arg-type]
        subentry,
        device,  # type: ignore[arg-type]
    )


# ----------------------------------------------------------------------------
# Device identity -- matches on the solarcharger domain itself, not a
# third-party integration.
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("identifiers", "expected"),
    [
        pytest.param({(DOMAIN, "hot_water")}, True, id="solarcharger_device"),
        pytest.param(
            {("tesla_custom", "abc123")}, False, id="other_integration_device"
        ),
        pytest.param(set(), False, id="no_identifiers"),
    ],
)
def test_is_charger_device_matches_only_solarcharger_domain(
    identifiers: set[tuple[str, str]], expected: bool
) -> None:
    """is_charger_device() looks only at the solarcharger identifier domain."""
    device = SimpleNamespace(name="Hot Water", identifiers=identifiers)

    assert UserCustomCharger.is_charger_device(device) is expected  # type: ignore[arg-type]


def test_is_chargeable_device_agrees_with_is_charger_device() -> None:
    """A user-custom device is both the charger and the chargeable at once."""
    device = SimpleNamespace(name="Hot Water", identifiers={(DOMAIN, "hot_water")})

    assert UserCustomCharger.is_chargeable_device(device) is True  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# Current -- max = 15 A, min workable = 15 A (binary: fully on or off)
# ----------------------------------------------------------------------------
def test_get_max_charge_current_reads_configured_number_entity() -> None:
    """Max charge current comes from the configured number entity's state."""
    hass = make_hass(HOT_WATER_STATES)
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.get_max_charge_current() == 15.0


def test_get_charge_current_reads_configured_sensor_entity() -> None:
    """get_charge_current() reports whatever the configured current sensor says."""
    hass = make_hass({**HOT_WATER_STATES, "sensor.hot_water_charge_current": "15"})
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.get_charge_current() == 15.0


def test_get_charger_min_workable_current_reads_configured_number_entity() -> None:
    """Min workable current comes from ScOptionState, inherited unchanged.

    Configured equal to max current (15 A): this device has no partial
    range -- it either draws its full rated current or none at all.
    """
    hass = make_hass(HOT_WATER_STATES)
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.get_charger_min_workable_current() == 15.0


def test_get_step_current_without_step_list_rounds_rather_than_enforcing_binary() -> (
    None
):
    """No step list is configured, so get_step_current() just rounds.

    Nothing at the Charger level enforces the 0-or-15 binary constraint
    implied by min_workable_current == max_current; that constraint is
    enforced elsewhere (pause/resume thresholds), not here. Pinned so a
    future reader doesn't assume this method already guarantees it.
    """
    hass = make_hass(HOT_WATER_STATES)
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.get_step_current(7.4) == 7


# ----------------------------------------------------------------------------
# Min-workable-power pause/resume thresholds -- pause=-10, resume=-5
# ----------------------------------------------------------------------------
def test_get_charger_min_workable_power_pause_threshold_reads_configured_entity() -> (
    None
):
    """Pause threshold comes from the configured number entity's state."""
    hass = make_hass(HOT_WATER_STATES)
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.get_charger_min_workable_power_pause_charge_threshold() == -10.0


def test_get_charger_min_workable_power_resume_threshold_reads_configured_entity() -> (
    None
):
    """Resume threshold comes from the configured number entity's state."""
    hass = make_hass(HOT_WATER_STATES)
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.get_charger_min_workable_power_resume_charge_threshold() == -5.0


def test_min_workable_power_thresholds_raise_when_unconfigured() -> None:
    """Both thresholds abort rather than silently defaulting when unconfigured."""
    hass = make_hass()
    charger = make_hot_water_charger(hass)

    with pytest.raises(ValueError, match="Failed to get entity number value"):
        charger.get_charger_min_workable_power_pause_charge_threshold()
    with pytest.raises(ValueError, match="Failed to get entity number value"):
        charger.get_charger_min_workable_power_resume_charge_threshold()


# ----------------------------------------------------------------------------
# On/off switch -- no set-current entity, so this device is switch-only
# ----------------------------------------------------------------------------
def test_can_set_charge_current_is_false_without_a_set_current_entity() -> None:
    """A hot water element has no set-current entity: it is switched, not throttled."""
    hass = make_hass(HOT_WATER_STATES)
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.can_set_charge_current() is False


def test_is_charger_switch_on_reads_configured_switch_entity() -> None:
    """is_charger_switch_on() reflects the configured switch entity's state."""
    hass = make_hass({**HOT_WATER_STATES, "switch.hot_water_element": "on"})
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    assert charger.is_charger_switch_on() is True


async def test_async_turn_charger_switch_calls_switch_service() -> None:
    """Turning the element on calls switch.turn_on on the configured entity."""
    hass = make_hass(HOT_WATER_STATES)
    charger = make_hot_water_charger(hass, options=HOT_WATER_OPTIONS)

    await charger.async_turn_charger_switch(True)

    hass.services.async_call.assert_awaited_once_with(
        domain="switch",
        service="turn_on",
        service_data={"entity_id": "switch.hot_water_element"},
        blocking=True,
        target=None,
        return_response=False,
    )
