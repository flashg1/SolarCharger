# ruff: noqa: SLF001
"""Unit tests for ConfigOptionsFlowHandler (config/config_options_flow.py).

OptionsFlow.config_entry is a read-only property (since HA 2024.11) resolved
via self.hass.config_entries.async_get_known_entry -- see conftest.py's
make_options_flow for how these tests wire a fake config entry through that
lookup instead of assigning to .config_entry directly.

Schema-building tests use a fake config entry with no saved options and
monkeypatch get_saved_option_value/get_device_api_entities where needed, to
keep each test focused on ConfigOptionsFlowHandler's own logic rather than
requiring a fully realistic device config just to avoid unrelated SystemErrors
raised deep inside config_utils.get_device_config_default_value.
"""

from typing import Any

import custom_components.solarcharger.config.config_options_flow as cof_module
from custom_components.solarcharger.config.config_options_flow import (
    ConfigOptionsFlowHandler,
)
from custom_components.solarcharger.config.config_utils import (
    NUMBER_ENTITY_SELECTOR,
    NUMBER_ENTITY_SELECTOR_READ_ONLY,
)
from custom_components.solarcharger.const import (
    ENTITY_CHARGER_ON_OFF_SWITCH,
    ERROR_EMPTY_CHARGER_LIST,
    ERROR_NUMBER_FORMAT,
    ERROR_SUBENTRY_ID_NOT_FOUND,
    NUMBER_CHARGER_EFFECTIVE_VOLTAGE,
    NUMBER_CHARGER_MAX_SPEED,
    OPTION_CHARGER_NAME,
    OPTION_GLOBAL_DEFAULTS_ID,
    OPTION_ID,
    OPTION_NAME,
)
from custom_components.solarcharger.exceptions.validation_exception import (
    ValidationExceptionError,
)
import pytest
import voluptuous as vol

from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    FakeCoordinator,
    make_config_entry,
    make_options_flow,
    make_subentry,
)


async def _noop_store_save(store: str, data: dict[str, Any]) -> None:
    """No-op stand-in for config_utils.async_ha_store_save."""


# ----------------------------------------------------------------------------
# get_option_value
# ----------------------------------------------------------------------------
def test_get_option_value_returns_saved_option() -> None:
    """A saved option value is returned as-is."""
    entry = make_config_entry(options={NUMBER_CHARGER_EFFECTIVE_VOLTAGE: "sensor.foo"})

    value = ConfigOptionsFlowHandler.get_option_value(
        entry, NUMBER_CHARGER_EFFECTIVE_VOLTAGE
    )

    assert value == "sensor.foo"


def test_get_option_value_falls_back_to_global_default_entity() -> None:
    """With no saved option, the global default entity ID is returned instead."""
    entry = make_config_entry(options={})

    value = ConfigOptionsFlowHandler.get_option_value(
        entry, NUMBER_CHARGER_EFFECTIVE_VOLTAGE
    )

    assert value == "number.solarcharger_global_defaults_charger_effective_voltage"


# ----------------------------------------------------------------------------
# _prompt / _required / _optional
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cls",
    [
        pytest.param(vol.Required, id="required"),
        pytest.param(vol.Optional, id="optional"),
    ],
)
def test_prompt_uses_saved_value_as_default(
    monkeypatch: pytest.MonkeyPatch, cls: type[vol.Required | vol.Optional]
) -> None:
    """A saved value becomes the marker's default, regardless of marker class."""
    monkeypatch.setattr(
        cof_module, "get_saved_option_value", lambda *a, **k: "sensor.saved"
    )
    flow = make_options_flow(make_config_entry())
    subentry = make_subentry("X")

    marker = flow._prompt(cls, subentry, "my_item", True)

    assert isinstance(marker, cls)
    assert marker.default() == "sensor.saved"


@pytest.mark.parametrize(
    "cls",
    [
        pytest.param(vol.Required, id="required"),
        pytest.param(vol.Optional, id="optional"),
    ],
)
def test_prompt_has_no_default_when_nothing_saved(
    monkeypatch: pytest.MonkeyPatch, cls: type[vol.Required | vol.Optional]
) -> None:
    """With no saved value, the marker carries no default."""
    monkeypatch.setattr(cof_module, "get_saved_option_value", lambda *a, **k: None)
    flow = make_options_flow(make_config_entry())
    subentry = make_subentry("X")

    marker = flow._prompt(cls, subentry, "my_item", True)

    assert isinstance(marker, cls)
    assert marker.default is vol.UNDEFINED


@pytest.mark.parametrize(
    ("saved_val", "expected_default"),
    [
        pytest.param("sensor.saved", "sensor.saved", id="truthy_string"),
        pytest.param(0, 0, id="falsy_zero"),
        pytest.param(None, vol.UNDEFINED, id="nothing_saved"),
    ],
)
def test_required_default_reflects_saved_value(
    monkeypatch: pytest.MonkeyPatch, saved_val: Any, expected_default: Any
) -> None:
    """vol.Required carries the saved value as its default, including a falsy 0."""
    monkeypatch.setattr(cof_module, "get_saved_option_value", lambda *a, **k: saved_val)
    flow = make_options_flow(make_config_entry())
    subentry = make_subentry("X")

    marker = flow._required(subentry, "my_item", True)

    assert isinstance(marker, vol.Required)
    default = marker.default() if callable(marker.default) else marker.default
    assert default == expected_default


@pytest.mark.parametrize(
    ("saved_val", "expected_default"),
    [
        pytest.param("sensor.saved", "sensor.saved", id="truthy_string"),
        pytest.param(False, False, id="falsy_false"),
        pytest.param(None, vol.UNDEFINED, id="nothing_saved"),
    ],
)
def test_optional_default_reflects_saved_value(
    monkeypatch: pytest.MonkeyPatch, saved_val: Any, expected_default: Any
) -> None:
    """vol.Optional carries the saved value as its default, including a falsy False."""
    monkeypatch.setattr(cof_module, "get_saved_option_value", lambda *a, **k: saved_val)
    flow = make_options_flow(make_config_entry())
    subentry = make_subentry("X")

    marker = flow._optional(subentry, "my_item", True)

    assert isinstance(marker, vol.Optional)
    default = marker.default() if callable(marker.default) else marker.default
    assert default == expected_default


# ----------------------------------------------------------------------------
# _charger_environment_schema / _charger_device_control_schema
# ----------------------------------------------------------------------------
def test_charger_environment_schema_maps_effective_voltage_to_number_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The environment schema wires the effective-voltage config item to the number selector."""
    monkeypatch.setattr(cof_module, "get_saved_option_value", lambda *a, **k: None)
    flow = make_options_flow(make_config_entry())
    subentry = make_subentry(OPTION_GLOBAL_DEFAULTS_ID)

    schema = flow._charger_environment_schema(subentry, use_default=True)

    selectors_by_key = {key.schema: selector for key, selector in schema.items()}
    assert selectors_by_key[NUMBER_CHARGER_EFFECTIVE_VOLTAGE] is NUMBER_ENTITY_SELECTOR


@pytest.mark.parametrize(
    ("config_item", "api_entities", "expected_selector"),
    [
        pytest.param(
            NUMBER_CHARGER_MAX_SPEED,
            {NUMBER_CHARGER_MAX_SPEED: "number.solarcharger_charger1_max_speed"},
            NUMBER_ENTITY_SELECTOR,
            id="modifiable_if_sc_entity_and_is_sc_entity",
        ),
        pytest.param(
            NUMBER_CHARGER_MAX_SPEED,
            {NUMBER_CHARGER_MAX_SPEED: "number.some_other_integration_max_speed"},
            NUMBER_ENTITY_SELECTOR_READ_ONLY,
            id="modifiable_if_sc_entity_but_not_sc_entity",
        ),
    ],
)
def test_charger_device_control_schema_chooses_selector_via_api_entities(
    monkeypatch: pytest.MonkeyPatch,
    config_item: str,
    api_entities: dict[str, str],
    expected_selector: Any,
) -> None:
    """The device-control schema's selector choice follows the real device's API entities."""
    monkeypatch.setattr(cof_module, "get_saved_option_value", lambda *a, **k: None)
    monkeypatch.setattr(
        cof_module, "get_device_api_entities", lambda subentry: api_entities
    )
    flow = make_options_flow(make_config_entry())
    subentry = make_subentry("Charger1")

    schema = flow._charger_device_control_schema(subentry, use_default=True)

    selectors_by_key = {key.schema: selector for key, selector in schema.items()}
    assert selectors_by_key[config_item] is expected_selector


def test_charger_device_control_schema_local_entity_is_always_modifiable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPTION_CHARGER_NAME is a local device entity (MODIFIABLE_DEFAULT), always editable."""
    monkeypatch.setattr(cof_module, "get_saved_option_value", lambda *a, **k: None)
    monkeypatch.setattr(cof_module, "get_device_api_entities", lambda subentry: None)
    flow = make_options_flow(make_config_entry())
    subentry = make_subentry("Charger1")

    schema = flow._charger_device_control_schema(subentry, use_default=True)

    selectors_by_key = {key.schema: selector for key, selector in schema.items()}
    assert selectors_by_key[ENTITY_CHARGER_ON_OFF_SWITCH] is not None
    assert OPTION_CHARGER_NAME in selectors_by_key


# ----------------------------------------------------------------------------
# process_config_options
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_process_config_options_returns_processed_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A config with no validation error returns the processed data as-is."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry)
    coordinator = FakeCoordinator(validate_config_options_error=None)
    flow = make_options_flow(entry, coordinator=coordinator, config_name="Charger1")
    monkeypatch.setattr(
        cof_module, "process_api_config", lambda *a, **k: {"processed": True}
    )

    result = await flow.process_config_options("Charger1", {"raw": 1})

    assert result == {"processed": True}
    assert coordinator.validate_config_options_calls == [
        ("Charger1", {"processed": True})
    ]


@pytest.mark.asyncio
async def test_process_config_options_raises_on_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A validation error from the coordinator raises ValidationExceptionError."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry)
    coordinator = FakeCoordinator(validate_config_options_error="bad_value")
    flow = make_options_flow(entry, coordinator=coordinator, config_name="Charger1")
    monkeypatch.setattr(
        cof_module, "process_api_config", lambda *a, **k: {"processed": True}
    )

    with pytest.raises(ValidationExceptionError) as exc_info:
        await flow.process_config_options("Charger1", {"raw": 1})

    assert exc_info.value.base == "base"
    assert exc_info.value.key == "bad_value"


# ----------------------------------------------------------------------------
# async_step_config_device
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_async_step_config_device_aborts_when_subentry_id_not_found() -> None:
    """An unknown config name aborts instead of crashing on a missing subentry."""
    entry = make_config_entry()
    flow = make_options_flow(entry, config_name="No Such Device")

    result = await flow.async_step_config_device(None)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ERROR_SUBENTRY_ID_NOT_FOUND


@pytest.mark.asyncio
async def test_async_step_config_device_aborts_on_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ValidationExceptionError from processing aborts with its error key."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry)
    flow = make_options_flow(entry, config_name="Charger1")

    async def raise_validation_error(*args: Any, **kwargs: Any) -> None:
        raise ValidationExceptionError("base", "some_error_key")

    monkeypatch.setattr(flow, "process_config_options", raise_validation_error)

    result = await flow.async_step_config_device({"field_a": "value_a"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "some_error_key"


@pytest.mark.asyncio
async def test_async_step_config_device_aborts_on_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ValueError from processing (e.g. bad number text) aborts with a generic reason."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry)
    flow = make_options_flow(entry, config_name="Charger1")

    async def raise_value_error(*args: Any, **kwargs: Any) -> None:
        raise ValueError("not a number")

    monkeypatch.setattr(flow, "process_config_options", raise_value_error)

    result = await flow.async_step_config_device({"field_a": "value_a"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ERROR_NUMBER_FORMAT


@pytest.mark.asyncio
async def test_async_step_config_device_creates_new_device_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A first-time save for a device adds OPTION_NAME/OPTION_ID alongside the input."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry, options={})
    flow = make_options_flow(entry, config_name="Charger1")

    async def fake_process_config_options(
        config_name: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return data

    monkeypatch.setattr(flow, "process_config_options", fake_process_config_options)
    monkeypatch.setattr(
        cof_module, "ha_store_open", lambda hass, name: f"store-for-{name}"
    )
    saved: dict[str, Any] = {}

    async def fake_store_save(store: str, data: dict[str, Any]) -> None:
        saved["store"] = store
        saved["data"] = dict(data)

    monkeypatch.setattr(cof_module, "async_ha_store_save", fake_store_save)

    result = await flow.async_step_config_device({"field_a": "value_a"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["Charger1"] == {
        OPTION_NAME: "Charger1",
        OPTION_ID: subentry.subentry_id,
        "field_a": "value_a",
    }
    assert saved["store"] == "store-for-Charger1"
    assert saved["data"] == result["data"]["Charger1"]
    assert (
        entry.options == {}
    )  # Original options untouched; a deep copy was mutated instead.


@pytest.mark.asyncio
async def test_async_step_config_device_merges_into_existing_device_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving again for an existing device merges into its options, keeping other fields."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry, options={"Charger1": {"existing_field": "old"}})
    flow = make_options_flow(entry, config_name="Charger1")

    async def fake_process_config_options(
        config_name: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return data

    monkeypatch.setattr(flow, "process_config_options", fake_process_config_options)
    monkeypatch.setattr(cof_module, "ha_store_open", lambda hass, name: "store")
    monkeypatch.setattr(cof_module, "async_ha_store_save", _noop_store_save)

    result = await flow.async_step_config_device({"field_a": "value_a"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["Charger1"] == {
        "existing_field": "old",
        "field_a": "value_a",
    }


@pytest.mark.asyncio
async def test_async_step_config_device_shows_general_schema_only_for_global_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global-defaults subentry only ever shows the environment schema."""
    subentry = make_subentry(OPTION_GLOBAL_DEFAULTS_ID)
    entry = make_config_entry(subentry)
    flow = make_options_flow(entry, config_name=OPTION_GLOBAL_DEFAULTS_ID)
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        flow,
        "_charger_environment_schema",
        lambda s, use_default: (
            calls.append(("environment", use_default))
            or {vol.Optional("env_field"): str}
        ),
    )
    monkeypatch.setattr(
        flow,
        "_charger_device_control_schema",
        lambda s, use_default: (
            calls.append(("device_control", use_default))
            or {vol.Optional("control_field"): str}
        ),
    )

    result = await flow.async_step_config_device(None)

    assert result["type"] is FlowResultType.FORM
    assert calls == [("environment", True)]
    assert {key.schema for key in result["data_schema"].schema} == {"env_field"}


@pytest.mark.asyncio
async def test_async_step_config_device_combines_both_schemas_for_a_regular_charger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A regular charger subentry combines the environment and device-control schemas."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry)
    flow = make_options_flow(entry, config_name="Charger1")
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        flow,
        "_charger_environment_schema",
        lambda s, use_default: (
            calls.append(("environment", use_default))
            or {vol.Optional("env_field"): str}
        ),
    )
    monkeypatch.setattr(
        flow,
        "_charger_device_control_schema",
        lambda s, use_default: (
            calls.append(("device_control", use_default))
            or {vol.Optional("control_field"): str}
        ),
    )

    result = await flow.async_step_config_device(None)

    assert result["type"] is FlowResultType.FORM
    assert calls == [("environment", False), ("device_control", True)]
    assert {key.schema for key in result["data_schema"].schema} == {
        "env_field",
        "control_field",
    }


# ----------------------------------------------------------------------------
# async_step_init
# ----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_async_step_init_delegates_to_config_device_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting a device sets _config_name and hands off to the device step."""
    subentry = make_subentry("Charger1")
    entry = make_config_entry(subentry)
    flow = make_options_flow(entry)
    calls: list[dict[str, Any] | None] = []

    async def fake_async_step_config_device(
        user_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        calls.append(user_input)
        return {"type": FlowResultType.FORM}

    monkeypatch.setattr(flow, "async_step_config_device", fake_async_step_config_device)

    await flow.async_step_init({"select_global_or_local_settings": "Charger1"})

    assert flow._config_name == "Charger1"
    assert calls == [None]


@pytest.mark.asyncio
async def test_async_step_init_aborts_when_no_subentries_configured() -> None:
    """With no subentries at all, there is nothing to select and the flow aborts."""
    entry = make_config_entry()
    flow = make_options_flow(entry)

    result = await flow.async_step_init(None)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ERROR_EMPTY_CHARGER_LIST


@pytest.mark.asyncio
async def test_async_step_init_lists_global_defaults_and_charger_subentries_only() -> (
    None
):
    """The device list always starts with global defaults, then charger/custom subentries.

    Non-charger subentry types (e.g. an unrelated "something_else" type) are
    excluded, even if such a subentry happened to share the global-defaults ID.
    """
    sub_charger = make_subentry("Charger1", subentry_type="charger")
    sub_custom = make_subentry("Custom1", subentry_type="custom")
    sub_other = make_subentry("Other1", subentry_type="something_else")
    entry = make_config_entry(sub_charger, sub_custom, sub_other)
    flow = make_options_flow(entry)

    result = await flow.async_step_init(None)

    assert result["type"] is FlowResultType.FORM
    selector = next(iter(result["data_schema"].schema.values()))
    assert selector.config["options"] == ["Global defaults", "Charger1", "Custom1"]
