"""Unit tests for config_utils.choose_selector's use of the Modifiable enum.

Modifiable itself is just a set of string constants with no behavior of its
own; the interesting logic lives entirely in choose_selector's handling of
each member (and combinations with the EXCLUDE_OCPP override), so that is
what these tests exercise. Selectors are represented by plain sentinel
strings rather than real EntitySelector instances, since choose_selector only
ever returns whichever of the two it was given, unchanged.
"""

from custom_components.solarcharger.config.config_utils import choose_selector
from custom_components.solarcharger.const import (
    CHARGE_API_DOMAIN,
    DOMAIN_OCPP,
    Modifiable,
)
import pytest

READ_ONLY = "read_only_selector"
MODIFIABLE = "modifiable_selector"
CONFIG_ITEM = "config_item"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "modifiable_config",
    [
        pytest.param([], id="no_modes_configured"),
        pytest.param([Modifiable.NEVER], id="never"),
        pytest.param([Modifiable.IF_NONE], id="if_none"),
    ],
)
def test_choose_selector_is_modifiable_without_api_entities(
    modifiable_config: list[Modifiable],
) -> None:
    """A device with no API entities (e.g. global defaults) is always modifiable.

    The Modifiable config is only consulted once real API entities exist to
    check against, so it has no effect here -- not even Modifiable.NEVER.
    """
    selector = choose_selector(
        None, CONFIG_ITEM, READ_ONLY, MODIFIABLE, modifiable_config
    )

    assert selector == MODIFIABLE


# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("sensor.foo", id="entity_present"),
        pytest.param(None, id="entity_absent"),
    ],
)
def test_choose_selector_always_is_always_modifiable(entity_id: str | None) -> None:
    """Modifiable.ALWAYS is modifiable no matter what the API entity looks like."""
    selector = choose_selector(
        {CONFIG_ITEM: entity_id},
        CONFIG_ITEM,
        READ_ONLY,
        MODIFIABLE,
        [Modifiable.ALWAYS],
    )

    assert selector == MODIFIABLE


# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("sensor.solarcharger_foo", id="solarcharger_entity"),
        pytest.param("sensor.other_foo", id="third_party_entity"),
        pytest.param(None, id="entity_absent"),
    ],
)
def test_choose_selector_never_is_always_read_only(entity_id: str | None) -> None:
    """Modifiable.NEVER is read-only no matter what the API entity looks like."""
    selector = choose_selector(
        {CONFIG_ITEM: entity_id}, CONFIG_ITEM, READ_ONLY, MODIFIABLE, [Modifiable.NEVER]
    )

    assert selector == READ_ONLY


# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        pytest.param(None, MODIFIABLE, id="no_api_entity_defined"),
        pytest.param("sensor.foo", READ_ONLY, id="api_entity_defined"),
    ],
)
def test_choose_selector_if_none(entity_id: str | None, expected: str) -> None:
    """Modifiable.IF_NONE is modifiable only when the API defines no entity for it."""
    selector = choose_selector(
        {CONFIG_ITEM: entity_id},
        CONFIG_ITEM,
        READ_ONLY,
        MODIFIABLE,
        [Modifiable.IF_NONE],
    )

    assert selector == expected


# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        pytest.param("sensor.solarcharger_foo", MODIFIABLE, id="solarcharger_entity"),
        pytest.param("sensor.other_foo", READ_ONLY, id="third_party_entity"),
        pytest.param(None, READ_ONLY, id="entity_absent"),
    ],
)
def test_choose_selector_if_sc_entity(entity_id: str | None, expected: str) -> None:
    """Modifiable.IF_SC_ENTITY is modifiable only for a solarcharger-owned entity."""
    selector = choose_selector(
        {CONFIG_ITEM: entity_id},
        CONFIG_ITEM,
        READ_ONLY,
        MODIFIABLE,
        [Modifiable.IF_SC_ENTITY],
    )

    assert selector == expected


# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "modifiable_config",
    [
        pytest.param([], id="empty_config"),
        pytest.param(
            [Modifiable.EXCLUDE_OCPP], id="only_an_exclusion_list_no_primary_mode"
        ),
    ],
)
def test_choose_selector_requires_a_primary_mode_when_api_entities_exist(
    modifiable_config: list[Modifiable],
) -> None:
    """Without one of ALWAYS/NEVER/IF_NONE/IF_SC_ENTITY, an API-backed device raises."""
    with pytest.raises(SystemError, match="ALWAYS, NEVER, IF_NONE or IF_SC_ENTITY"):
        choose_selector(
            {CONFIG_ITEM: "sensor.foo"},
            CONFIG_ITEM,
            READ_ONLY,
            MODIFIABLE,
            modifiable_config,
        )


# ----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("device_domain", "expected"),
    [
        pytest.param(DOMAIN_OCPP, READ_ONLY, id="ocpp_device_forced_read_only"),
        pytest.param("tesla_custom", MODIFIABLE, id="non_ocpp_device_keeps_always"),
    ],
)
def test_choose_selector_exclude_ocpp_overrides_always_for_ocpp_devices(
    device_domain: str, expected: str
) -> None:
    """Modifiable.EXCLUDE_OCPP forces read-only for OCPP even when ALWAYS is also set."""
    api_entities = {CONFIG_ITEM: "sensor.foo", CHARGE_API_DOMAIN: device_domain}

    selector = choose_selector(
        api_entities,
        CONFIG_ITEM,
        READ_ONLY,
        MODIFIABLE,
        [Modifiable.ALWAYS, Modifiable.EXCLUDE_OCPP],
    )

    assert selector == expected
