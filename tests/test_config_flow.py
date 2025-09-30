"""Test the Simple Integration config flow."""

from unittest import mock

from homeassistant import config_entries
from homeassistant.const import __version__ as HA_VERSION
from packaging.version import parse as parse_version
from custom_components.solarcharger import config_flow, const


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"


async def test_flow_user_init(hass):
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": "user"}
    )
    expected = {
        "data_schema": config_flow.STEP_SOURCE_POWER_SCHEMA,
        "description_placeholders": None,
        "errors": {},
        "flow_id": mock.ANY,
        "handler": "solarcharger",
        "last_step": None,
        "step_id": "user",
        "type": "form",
        "preview": None,
    }
    assert expected == result
