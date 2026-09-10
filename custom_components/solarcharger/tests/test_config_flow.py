# ruff: noqa: SLF001
"""Unit tests for ConfigFlowHandler (config_flow.py).

ConfigFlowHandler is a real homeassistant.config_entries.ConfigFlow subclass,
not one of this integration's own ScOptionState-derived classes, so the
harness here differs from the rest of this suite: FlowHandler's own result
builders (async_show_form/async_create_entry/async_update_and_abort) are
self-contained (they only read self.flow_id/self.handler/self.context, all
of which have class-level defaults), so a bare ConfigFlowHandler() can be
constructed directly -- no __new__() bypass needed. What does need wiring by
hand is self.hass (never set by __init__) and self.context (source/unique_id/
entry_id all live there, since FlowHandler.source is a read-only property
derived from self.context.get("source")).

_get_entity_entry() calls entity_registry.async_get(self.hass) -- the real HA
helper, not something reachable through the fake hass -- so it's stubbed the
same way test_tesla_custom_charger.py stubs it for HaDevice. Config-file
storage (ha_store_open/async_ha_store_load/async_ha_store_save) is backed by
a real HA Store needing real hass storage plumbing; since these tests are
about ConfigFlowHandler's own step logic, not file storage, those three
module-level functions are monkeypatched directly instead.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

from custom_components.solarcharger.config.config_subentry_charger import (
    AddChargerSubEntryFlowHandler,
)
from custom_components.solarcharger.config.config_subentry_custom import (
    AddCustomSubEntryFlowHandler,
)
import custom_components.solarcharger.config_flow as config_flow_module
from custom_components.solarcharger.config_flow import (
    CONF_CHARGER_DEVICE,
    ConfigFlowHandler,
    validate_charger_config,
    validate_charger_selection,
)
from custom_components.solarcharger.const import (
    CONFIG_CHARGER_CURRENT_UPDATE_PERIOD,
    CONFIG_NET_POWER_SENSOR,
    DEFAULT_CHARGER_CURRENT_UPDATE_PERIOD,
    ERROR_CURRENT_UPDATE_PERIOD,
    ERROR_NET_POWER_SENSOR,
    MINIMUM_CHARGER_CURRENT_UPDATE_PERIOD,
    NAME,
    SUBENTRY_TYPE_CHARGER,
    SUBENTRY_TYPE_CUSTOM,
)
from custom_components.solarcharger.exceptions.validation_exception import (
    ValidationExceptionError,
)
import pytest

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import AbortFlow, FlowResultType

RECONFIGURE_ENTRY_ID = "reconfigure-entry-1"


# ----------------------------------------------------------------------------
def make_config_flow(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: str = SOURCE_USER,
    unique_id: str | None = None,
    reconfigure_entry: SimpleNamespace | None = None,
    known_entity_ids: set[str] | None = None,
    store_config: dict[str, Any] | None = None,
) -> ConfigFlowHandler:
    """Build a ConfigFlowHandler with .hass/.context wired and I/O helpers stubbed."""
    flow = ConfigFlowHandler()
    context: dict[str, Any] = {"source": source}
    if unique_id is not None:
        context["unique_id"] = unique_id
    if reconfigure_entry is not None:
        context["entry_id"] = RECONFIGURE_ENTRY_ID
    flow.context = context  # type: ignore[assignment]

    known_entries = (
        {RECONFIGURE_ENTRY_ID: reconfigure_entry} if reconfigure_entry else {}
    )
    flow.hass = SimpleNamespace(  # type: ignore[assignment]
        config_entries=SimpleNamespace(
            async_get_known_entry=lambda entry_id: known_entries[entry_id],
            async_update_entry=Mock(),
        ),
    )

    known_entity_ids = known_entity_ids or set()
    fake_registry = SimpleNamespace(
        async_get=lambda entity_id: (
            SimpleNamespace(entity_id=entity_id)
            if entity_id in known_entity_ids
            else None
        )
    )
    monkeypatch.setattr(config_flow_module.er, "async_get", lambda hass: fake_registry)

    monkeypatch.setattr(config_flow_module, "ha_store_open", Mock(return_value=Mock()))
    monkeypatch.setattr(
        config_flow_module,
        "async_ha_store_load",
        AsyncMock(return_value=store_config),
    )
    monkeypatch.setattr(config_flow_module, "async_ha_store_save", AsyncMock())

    return flow


def make_reconfigure_entry(
    *, unique_id: str | None = "existing-unique-id", data: dict[str, Any] | None = None
) -> SimpleNamespace:
    """Minimal stand-in for the ConfigEntry being reconfigured."""
    return SimpleNamespace(
        unique_id=unique_id,
        data=data
        or {
            CONFIG_NET_POWER_SENSOR: "sensor.existing_net_power",
            CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 30,
        },
    )


# ----------------------------------------------------------------------------
# Module-level validators
# ----------------------------------------------------------------------------
def test_validate_charger_selection_raises_when_no_device_chosen() -> None:
    """An empty/missing charger selection is a validation error, not a silent pass."""
    with pytest.raises(ValidationExceptionError):
        validate_charger_selection(None, {CONF_CHARGER_DEVICE: None})  # type: ignore[arg-type]


def test_validate_charger_selection_passes_through_a_real_choice() -> None:
    """A real selection is returned unchanged."""
    data = {CONF_CHARGER_DEVICE: "device-123"}

    assert validate_charger_selection(None, data) is data  # type: ignore[arg-type]


def test_validate_charger_config_is_a_pure_passthrough() -> None:
    """There is currently nothing to validate at this step."""
    data = {"anything": "goes"}

    assert validate_charger_config(None, data) is data  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# async_get_options_flow() -- branches on the running HA version
# ----------------------------------------------------------------------------
def test_options_flow_passes_config_entry_on_old_ha_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the 2024.11 options-flow change, config_entry must be passed explicitly.

    ConfigOptionsFlowHandler's own __init__ is version-sensitive (config_entry
    is a plain attribute pre-2024.11, a read-only property from 2024.11
    onward in HA core itself, independent of this component's version
    check), so constructing a real instance here would depend on which HA
    core this happens to run against rather than on async_get_options_flow()'s
    own branching. The constructor call itself is spied on instead, to
    isolate that branching from ConfigOptionsFlowHandler's version-dependent
    internals.
    """
    fake_handler_cls = Mock(return_value=Mock())
    monkeypatch.setattr(
        config_flow_module, "ConfigOptionsFlowHandler", fake_handler_cls
    )
    monkeypatch.setattr(config_flow_module, "ha_version", "2024.10.0")
    config_entry = SimpleNamespace()

    ConfigFlowHandler.async_get_options_flow(config_entry)  # type: ignore[arg-type]

    fake_handler_cls.assert_called_once_with(config_entry=config_entry)


def test_options_flow_omits_config_entry_on_new_ha_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From 2024.11 onward, config_entry is resolved by the base class instead."""
    fake_handler_cls = Mock(return_value=Mock())
    monkeypatch.setattr(
        config_flow_module, "ConfigOptionsFlowHandler", fake_handler_cls
    )
    monkeypatch.setattr(config_flow_module, "ha_version", "2025.1.0")
    config_entry = SimpleNamespace()

    ConfigFlowHandler.async_get_options_flow(config_entry)  # type: ignore[arg-type]

    fake_handler_cls.assert_called_once_with()


# ----------------------------------------------------------------------------
# async_get_supported_subentry_types()
# ----------------------------------------------------------------------------
def test_supported_subentry_types_maps_charger_and_custom() -> None:
    """Both subentry flows this integration supports are registered under the right key."""
    subentry_types = ConfigFlowHandler.async_get_supported_subentry_types(
        SimpleNamespace()  # type: ignore[arg-type]
    )

    assert subentry_types == {
        SUBENTRY_TYPE_CHARGER: AddChargerSubEntryFlowHandler,
        SUBENTRY_TYPE_CUSTOM: AddCustomSubEntryFlowHandler,
    }


# ----------------------------------------------------------------------------
# _validate_user_config()
# ----------------------------------------------------------------------------
def test_validate_user_config_accepts_a_known_sensor_and_valid_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered net-power sensor and an above-minimum period produce no errors."""
    flow = make_config_flow(monkeypatch, known_entity_ids={"sensor.net_power"})
    data = {
        CONFIG_NET_POWER_SENSOR: "sensor.net_power",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 60,
    }
    errors: dict[str, str] = {}

    flow._validate_user_config(data, errors)

    assert errors == {}


def test_validate_user_config_flags_an_unregistered_sensor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A net-power sensor that isn't a real entity is rejected."""
    flow = make_config_flow(monkeypatch, known_entity_ids=set())
    data = {
        CONFIG_NET_POWER_SENSOR: "sensor.does_not_exist",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 60,
    }
    errors: dict[str, str] = {}

    flow._validate_user_config(data, errors)

    assert errors[CONFIG_NET_POWER_SENSOR] == ERROR_NET_POWER_SENSOR


def test_validate_user_config_flags_a_too_short_update_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A current-update period below the minimum is rejected."""
    flow = make_config_flow(monkeypatch, known_entity_ids={"sensor.net_power"})
    data = {
        CONFIG_NET_POWER_SENSOR: "sensor.net_power",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: MINIMUM_CHARGER_CURRENT_UPDATE_PERIOD - 1,
    }
    errors: dict[str, str] = {}

    flow._validate_user_config(data, errors)

    assert errors[CONFIG_CHARGER_CURRENT_UPDATE_PERIOD] == ERROR_CURRENT_UPDATE_PERIOD


def test_validate_user_config_can_flag_both_fields_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both problems are reported together, not just the first one found."""
    flow = make_config_flow(monkeypatch, known_entity_ids=set())
    data = {
        CONFIG_NET_POWER_SENSOR: "sensor.does_not_exist",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 0,
    }
    errors: dict[str, str] = {}

    flow._validate_user_config(data, errors)

    assert set(errors) == {
        CONFIG_NET_POWER_SENSOR,
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD,
    }


# ----------------------------------------------------------------------------
# async_step_user() -- initial "user" source
# ----------------------------------------------------------------------------
async def test_initial_user_step_shows_form_with_built_in_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No prior history on disk: the form falls back to the built-in defaults."""
    flow = make_config_flow(monkeypatch, store_config=None)

    result = await flow.async_step_user(None)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema_defaults = {
        key.schema: key.default() for key in result["data_schema"].schema
    }
    assert schema_defaults[CONFIG_NET_POWER_SENSOR] is None
    assert (
        schema_defaults[CONFIG_CHARGER_CURRENT_UPDATE_PERIOD]
        == DEFAULT_CHARGER_CURRENT_UPDATE_PERIOD
    )


async def test_initial_user_step_prefills_from_leftover_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A previous installation's saved config pre-fills the form instead of the defaults."""
    flow = make_config_flow(
        monkeypatch,
        store_config={
            CONFIG_NET_POWER_SENSOR: "sensor.old_net_power",
            CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 45,
        },
    )

    result = await flow.async_step_user(None)

    schema_defaults = {
        key.schema: key.default() for key in result["data_schema"].schema
    }
    assert schema_defaults[CONFIG_NET_POWER_SENSOR] == "sensor.old_net_power"
    assert schema_defaults[CONFIG_CHARGER_CURRENT_UPDATE_PERIOD] == 45


async def test_user_step_valid_submission_saves_and_creates_the_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid submission is persisted to file storage and creates the config entry."""
    flow = make_config_flow(monkeypatch, known_entity_ids={"sensor.net_power"})
    user_input = {
        CONFIG_NET_POWER_SENSOR: "sensor.net_power",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 60,
    }

    result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == user_input
    config_flow_module.async_ha_store_save.assert_awaited_once()  # type: ignore[attr-defined]


async def test_user_step_invalid_submission_reshows_the_form_with_the_users_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid submission re-shows the form with errors, keeping what the user typed."""
    flow = make_config_flow(monkeypatch, known_entity_ids=set())
    user_input = {
        CONFIG_NET_POWER_SENSOR: "sensor.does_not_exist",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 60,
    }

    result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONFIG_NET_POWER_SENSOR] == ERROR_NET_POWER_SENSOR
    schema_defaults = {
        key.schema: key.default() for key in result["data_schema"].schema
    }
    assert schema_defaults[CONFIG_NET_POWER_SENSOR] == "sensor.does_not_exist"
    config_flow_module.async_ha_store_save.assert_not_awaited()  # type: ignore[attr-defined]


# ----------------------------------------------------------------------------
# async_step_user() -- "reconfigure" source
# ----------------------------------------------------------------------------
async def test_reconfigure_initial_step_prefills_from_the_existing_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starting a reconfigure shows the form pre-filled from the entry being reconfigured."""
    entry = make_reconfigure_entry(
        data={
            CONFIG_NET_POWER_SENSOR: "sensor.existing_net_power",
            CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 30,
        }
    )
    flow = make_config_flow(
        monkeypatch,
        source=SOURCE_RECONFIGURE,
        unique_id="existing-unique-id",
        reconfigure_entry=entry,
    )

    result = await flow.async_step_user(None)

    schema_defaults = {
        key.schema: key.default() for key in result["data_schema"].schema
    }
    assert schema_defaults[CONFIG_NET_POWER_SENSOR] == "sensor.existing_net_power"
    assert schema_defaults[CONFIG_CHARGER_CURRENT_UPDATE_PERIOD] == 30


async def test_reconfigure_valid_submission_updates_and_aborts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid reconfigure submission updates the entry and ends the flow, not creates a new one."""
    entry = make_reconfigure_entry()
    flow = make_config_flow(
        monkeypatch,
        source=SOURCE_RECONFIGURE,
        unique_id="existing-unique-id",
        reconfigure_entry=entry,
        known_entity_ids={"sensor.net_power"},
    )
    user_input = {
        CONFIG_NET_POWER_SENSOR: "sensor.net_power",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 60,
    }

    result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    flow.hass.config_entries.async_update_entry.assert_called_once()  # type: ignore[attr-defined]
    config_flow_module.async_ha_store_save.assert_awaited_once()  # type: ignore[attr-defined]


async def test_reconfigure_aborts_on_unique_id_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconfiguring an entry whose unique ID no longer matches the flow context aborts outright."""
    entry = make_reconfigure_entry(unique_id="a-different-unique-id")
    flow = make_config_flow(
        monkeypatch,
        source=SOURCE_RECONFIGURE,
        unique_id="existing-unique-id",
        reconfigure_entry=entry,
        known_entity_ids={"sensor.net_power"},
    )
    user_input = {
        CONFIG_NET_POWER_SENSOR: "sensor.net_power",
        CONFIG_CHARGER_CURRENT_UPDATE_PERIOD: 60,
    }

    with pytest.raises(AbortFlow):
        await flow.async_step_user(user_input)

    config_flow_module.async_ha_store_save.assert_not_awaited()  # type: ignore[attr-defined]


async def test_reconfigure_initial_step_also_aborts_on_unique_id_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mismatch guard applies even before the user has submitted anything."""
    entry = make_reconfigure_entry(unique_id="a-different-unique-id")
    flow = make_config_flow(
        monkeypatch,
        source=SOURCE_RECONFIGURE,
        unique_id="existing-unique-id",
        reconfigure_entry=entry,
    )

    with pytest.raises(AbortFlow):
        await flow.async_step_user(None)


# ----------------------------------------------------------------------------
# async_step_reconfigure() -- delegates straight to async_step_user()
# ----------------------------------------------------------------------------
async def test_step_reconfigure_delegates_to_step_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dedicated reconfigure entry point is just a thin alias for the user step."""
    entry = make_reconfigure_entry()
    flow = make_config_flow(
        monkeypatch,
        source=SOURCE_RECONFIGURE,
        unique_id="existing-unique-id",
        reconfigure_entry=entry,
    )

    result = await flow.async_step_reconfigure(None)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
