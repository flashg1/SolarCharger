"""Test the Simple Integration config flow."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarcharger import (
    config_flow as cf,
)
from custom_components.solarcharger import (
    const,
)
from custom_components.solarcharger import (
    config_options_flow as of,
)


@pytest.mark.asyncio
async def test_options_flow_init(hass):
    """Test we get the form."""

    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id="MockSolarCharger",
        data={
            cf.CONF_CHARGER_DEVICE: "abc-123",
        },
    )
    config_entry.add_to_hass(hass)

    # show initial form
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["errors"] == {}
    assert of.OPTION_CHARGER_EFFECTIVE_VOLTAGE in result["data_schema"].schema
