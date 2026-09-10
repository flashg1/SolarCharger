"""Unit tests for TeslaCustomCharger (chargers/tesla_custom_charger.py).

TeslaCustomCharger itself only adds device-identity checks; every behaviour
that reads configured numbers/states comes from ChargerChargeableBase and its
ScOptionState/ScConfigState/ScState ancestors, so these tests exercise that
inherited behaviour through the concrete Tesla Custom class.

Constructing the class for real would normally require a live HomeAssistant
entity registry (HaDevice.__init__ calls entity_registry.async_get(hass)).
None of the Charger-interface methods under test go through the entity
registry -- they all resolve entity IDs from config_entry.options via
ScOptionState.option_get_id() and then read homeassistant.core.State objects
directly -- so the registry lookup is stubbed out rather than faked in full,
following this test suite's existing preference (see conftest.py) for small
fakes over a real hass instance.

Note what is deliberately NOT covered here: voltage (NUMBER_CHARGER_EFFECTIVE_
VOLTAGE) and max charge speed (NUMBER_CHARGER_MAX_SPEED) are not part of the
Charger interface or ChargerChargeableBase at all -- they are read by
SolarCharge.get_charger_effective_voltage() and
ChargeScheduler._get_one_percent_charge_duration() respectively, one layer up
in the state machine. A TeslaCustomCharger instance has no method for either
value, so there is nothing charger-level to test for them.
"""

from types import SimpleNamespace

from custom_components.solarcharger.chargers import ha_device as ha_device_module
from custom_components.solarcharger.chargers.tesla_custom_charger import (
    TeslaCustomCharger,
)
from custom_components.solarcharger.const import (
    DOMAIN_TESLA_CUSTOM,
    ENTITY_CHARGER_CHARGING_SENSOR,
    ENTITY_CHARGER_ON_OFF_SWITCH,
    ENTITY_CHARGER_PLUGGED_IN_SENSOR,
    ENTITY_CHARGER_SET_CHARGE_CURRENT,
    NUMBER_CHARGER_MAX_CURRENT,
    OPTION_CHARGER_CHARGING_STATE_LIST,
    OPTION_CHARGER_CONNECT_STATE_LIST,
    TEXT_CHARGER_STEP_CURRENT_LIST,
)
import pytest

from .conftest import make_config_entry, make_hass, make_subentry

TESLA23M3_SUBENTRY_ID = "tesla23m3"


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


def make_charger(
    hass: SimpleNamespace,
    *,
    options: dict[str, str] | None = None,
    identifiers: set[tuple[str, str]] | None = None,
) -> TeslaCustomCharger:
    """Build a TeslaCustomCharger backed by the given fake hass and option config."""
    subentry = make_subentry(TESLA23M3_SUBENTRY_ID)
    entry = make_config_entry(subentry, options={subentry.unique_id: (options or {})})
    device = SimpleNamespace(
        id="device-1",
        identifiers=identifiers or {(DOMAIN_TESLA_CUSTOM, "abc123")},
    )
    return TeslaCustomCharger(
        hass,
        entry,  # type: ignore[arg-type]
        subentry,
        device,  # type: ignore[arg-type]
    )


# ----------------------------------------------------------------------------
# Device identity
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("identifiers", "expected"),
    [
        pytest.param({(DOMAIN_TESLA_CUSTOM, "abc123")}, True, id="tesla_custom_device"),
        pytest.param({("tessie", "abc123")}, False, id="other_integration_device"),
        pytest.param(set(), False, id="no_identifiers"),
    ],
)
def test_is_charger_device_matches_only_tesla_custom_identifiers(
    identifiers: set[tuple[str, str]], expected: bool
) -> None:
    """is_charger_device() looks only at the tesla_custom identifier domain."""
    device = SimpleNamespace(name="Tesla23m3", identifiers=identifiers)

    assert TeslaCustomCharger.is_charger_device(device) is expected  # type: ignore[arg-type]


def test_is_chargeable_device_agrees_with_is_charger_device() -> None:
    """A Tesla Custom device is both the charger and the chargeable at once."""
    device = SimpleNamespace(
        name="Tesla23m3", identifiers={(DOMAIN_TESLA_CUSTOM, "abc123")}
    )

    assert TeslaCustomCharger.is_chargeable_device(device) is True  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# get_max_charge_current() -- max current = 15 A
# ----------------------------------------------------------------------------
def test_get_max_charge_current_reads_configured_number_entity() -> None:
    """Max charge current comes from the configured number entity's state."""
    hass = make_hass({"number.tesla23m3_max_current": "15"})
    charger = make_charger(
        hass,
        options={NUMBER_CHARGER_MAX_CURRENT: "number.tesla23m3_max_current"},
    )

    assert charger.get_max_charge_current() == 15.0


def test_get_max_charge_current_is_none_when_unconfigured() -> None:
    """No configured entity means no max current, not an error."""
    hass = make_hass()
    charger = make_charger(hass)

    assert charger.get_max_charge_current() is None


# ----------------------------------------------------------------------------
# get_step_current_list() / get_step_current() -- step snapping around max=15
# ----------------------------------------------------------------------------
def test_get_step_current_list_floors_at_zero_and_tops_at_max_current() -> None:
    """The configured step list gets a 0 floor and the max current appended."""
    hass = make_hass(
        {
            "number.tesla23m3_max_current": "15",
            "text.tesla23m3_step_list": "[6, 8, 10, 12]",
        }
    )
    charger = make_charger(
        hass,
        options={
            NUMBER_CHARGER_MAX_CURRENT: "number.tesla23m3_max_current",
            TEXT_CHARGER_STEP_CURRENT_LIST: "text.tesla23m3_step_list",
        },
    )

    assert charger.get_step_current_list() == [0, 6, 8, 10, 12, 15]


@pytest.mark.parametrize(
    ("ideal_current", "expected_step"),
    [
        pytest.param(13, 12, id="between_steps_snaps_down"),
        pytest.param(12, 12, id="exact_step_stays"),
        pytest.param(15, 15, id="at_max_current_stays"),
        pytest.param(20, 15, id="above_max_current_clamps_to_max"),
        pytest.param(5, 0, id="below_lowest_step_floors_to_zero"),
    ],
)
def test_get_step_current_snaps_down_to_nearest_configured_step(
    ideal_current: float, expected_step: float
) -> None:
    """Charge current always snaps down, never up, to the nearest step."""
    hass = make_hass(
        {
            "number.tesla23m3_max_current": "15",
            "text.tesla23m3_step_list": "[6, 8, 10, 12]",
        }
    )
    charger = make_charger(
        hass,
        options={
            NUMBER_CHARGER_MAX_CURRENT: "number.tesla23m3_max_current",
            TEXT_CHARGER_STEP_CURRENT_LIST: "text.tesla23m3_step_list",
        },
    )

    assert charger.get_step_current(ideal_current) == expected_step


def test_get_step_current_without_step_list_rounds_to_nearest_integer() -> None:
    """With no step list configured, current is just rounded, not snapped."""
    hass = make_hass({"number.tesla23m3_max_current": "15"})
    charger = make_charger(
        hass,
        options={NUMBER_CHARGER_MAX_CURRENT: "number.tesla23m3_max_current"},
    )

    assert charger.get_step_current(13.4) == 13


# ----------------------------------------------------------------------------
# Connection / charging state
# ----------------------------------------------------------------------------
def test_is_connected_true_when_state_in_configured_connect_list() -> None:
    """is_connected() checks the plug sensor state against the configured list.

    OPTION_CHARGER_CONNECT_STATE_LIST is a plain JSON string saved directly in
    config_entry.options -- unlike ENTITY_CHARGER_PLUGGED_IN_SENSOR, it is not
    an entity ID to dereference through hass.states.
    """
    hass = make_hass({"binary_sensor.tesla23m3_plugged_in": "Charging"})
    charger = make_charger(
        hass,
        options={
            ENTITY_CHARGER_PLUGGED_IN_SENSOR: "binary_sensor.tesla23m3_plugged_in",
            OPTION_CHARGER_CONNECT_STATE_LIST: '["Charging", "Complete"]',
        },
    )

    assert charger.is_connected() is True


def test_is_connected_false_when_state_not_in_configured_connect_list() -> None:
    """A plug state outside the configured list means not connected."""
    hass = make_hass({"binary_sensor.tesla23m3_plugged_in": "Disconnected"})
    charger = make_charger(
        hass,
        options={
            ENTITY_CHARGER_PLUGGED_IN_SENSOR: "binary_sensor.tesla23m3_plugged_in",
            OPTION_CHARGER_CONNECT_STATE_LIST: '["Charging", "Complete"]',
        },
    )

    assert charger.is_connected() is False


def test_is_charging_true_when_state_in_configured_charging_list() -> None:
    """is_charging() checks the charging sensor state against the configured list."""
    hass = make_hass({"sensor.tesla23m3_charging_state": "Charging"})
    charger = make_charger(
        hass,
        options={
            ENTITY_CHARGER_CHARGING_SENSOR: "sensor.tesla23m3_charging_state",
            OPTION_CHARGER_CHARGING_STATE_LIST: '["Charging"]',
        },
    )

    assert charger.is_charging() is True


# ----------------------------------------------------------------------------
# can_set_charge_current() / async_set_charge_current()
# ----------------------------------------------------------------------------
def test_can_set_charge_current_reflects_whether_entity_is_configured() -> None:
    """Ability to set current depends only on whether the set-current entity is configured."""
    hass = make_hass()

    with_entity = make_charger(
        hass,
        options={ENTITY_CHARGER_SET_CHARGE_CURRENT: "number.tesla23m3_set_current"},
    )
    without_entity = make_charger(hass)

    assert with_entity.can_set_charge_current() is True
    assert without_entity.can_set_charge_current() is False


async def test_async_set_charge_current_snaps_to_step_and_calls_number_service() -> (
    None
):
    """Setting current snaps to the nearest step first, then calls number.set_value."""
    hass = make_hass(
        {
            "number.tesla23m3_max_current": "15",
            "text.tesla23m3_step_list": "[6, 8, 10, 12]",
        }
    )
    charger = make_charger(
        hass,
        options={
            NUMBER_CHARGER_MAX_CURRENT: "number.tesla23m3_max_current",
            TEXT_CHARGER_STEP_CURRENT_LIST: "text.tesla23m3_step_list",
            ENTITY_CHARGER_SET_CHARGE_CURRENT: "number.tesla23m3_set_current",
        },
    )

    new_current = await charger.async_set_charge_current(13)

    assert new_current == 12
    hass.services.async_call.assert_awaited_once_with(
        domain="number",
        service="set_value",
        service_data={"entity_id": "number.tesla23m3_set_current", "value": 12},
        blocking=True,
        target=None,
        return_response=False,
    )


async def test_async_turn_charger_switch_calls_switch_service() -> None:
    """Turning the charger on calls switch.turn_on on the configured entity."""
    hass = make_hass()
    charger = make_charger(
        hass,
        options={ENTITY_CHARGER_ON_OFF_SWITCH: "switch.tesla23m3_charger"},
    )

    await charger.async_turn_charger_switch(True)

    hass.services.async_call.assert_awaited_once_with(
        domain="switch",
        service="turn_on",
        service_data={"entity_id": "switch.tesla23m3_charger"},
        blocking=True,
        target=None,
        return_response=False,
    )
