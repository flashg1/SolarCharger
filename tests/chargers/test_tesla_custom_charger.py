"""Tests for the Tesla Custom charger implementation."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.helpers.device_registry import DeviceEntry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarcharger.chargers.tesla_custom_charger import (
    TeslaCustomCharger,
    TeslaCustomEntityMap,
    TeslaCustomChargerConnectStateMap,
    TeslaCustomChargerChargingStateMap,
)
from custom_components.solarcharger.const import CHARGER_DOMAIN_TESLA_CUSTOM
from custom_components.solarcharger.config_subentry_flow import (
    SUBENTRY_TYPE_CHARGER,
    SUBENTRY_DEVICE_DOMAIN,
    SUBENTRY_DEVICE_NAME,
    SUBENTRY_CHARGER_DEVICE,
)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance for testing."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry for the tests."""
    return MockConfigEntry(
        domain="solarcharger",
        title="Tesla Custom Test Charger",
        data={"charger_type": "tesla_custom"},
        unique_id="test_tesla_custom_charger",
        subentries_data=[
            ConfigSubentryData(
                data={
                    SUBENTRY_DEVICE_DOMAIN: "tesla_custom",
                    SUBENTRY_DEVICE_NAME: "MockTeslaCustomCharger",
                    SUBENTRY_CHARGER_DEVICE: "MockTeslaCustomChargerDeviceId",
                },
                subentry_id="MockSubentryId1",
                subentry_type=SUBENTRY_TYPE_CHARGER,
                title="tesla_custom TestCharger",
                unique_id="tesla_custom_testcharger",
            )
        ],
    )


@pytest.fixture
def mock_device_entry():
    """Create a mock DeviceEntry object for testing."""
    device_entry = MagicMock(spec=DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = {("tesla_custom", "test_charger")}
    return device_entry


@pytest.fixture
def tesla_custom_charger(mock_hass, mock_config_entry, mock_device_entry):
    """Create an TeslaCustomCharger instance for testing."""
    with patch(
        "custom_components.solarcharger.chargers.tesla_custom_charger.TeslaCustomCharger.refresh_entities"
    ):
        charger = TeslaCustomCharger(
            hass=mock_hass,
            config_entry=mock_config_entry,
            config_subentry=next(iter(mock_config_entry.subentries.values())),
            device_entry=mock_device_entry,
        )
        # Mock the _get_entity_state_by_key method
        # charger._get_entity_state_by_key = MagicMock()
        charger._get_entity_state_by_unique_id = MagicMock()
        return charger


def test_is_charger_device():
    """Test the is_charger_device static method."""
    # Test with Tesla Custom device
    tesla_custom_device = MagicMock(spec=DeviceEntry)
    tesla_custom_device.identifiers = {("tesla_custom", "test_charger")}
    assert TeslaCustomCharger.is_charger_device(tesla_custom_device) is True

    # Test with non-Tesla Custom device
    other_device = MagicMock(spec=DeviceEntry)
    other_device.identifiers = {("easee", "test_charger")}
    assert TeslaCustomCharger.is_charger_device(other_device) is False


async def test_set_charge_current(tesla_custom_charger, mock_hass):
    """Test setting current limits on the Tesla Custom charger."""
    # Setup test data
    test_limits = 14

    # Call the method
    await tesla_custom_charger.set_charge_current(test_limits)

    # Verify service call was made with correct parameters
    mock_hass.services.async_call.assert_called_once_with(
        domain="number",
        service="set_value",
        service_data={
            "entity_id": TeslaCustomEntityMap.ChargerCurrent,
            "value": 14,  # Should use minimum of the values
        },
        blocking=True,
    )


async def test_set_charge_current_service_error(tesla_custom_charger, mock_hass):
    """Test setting current limits when service call fails."""
    # Setup test data
    test_limits = 14

    # Mock service call to raise an error
    mock_hass.services.async_call.side_effect = ValueError("Service error")

    # Call the method - should not raise an exception
    await tesla_custom_charger.set_charge_current(test_limits)

    # Verify service call was attempted
    mock_hass.services.async_call.assert_called_once()


def test_get_charge_current_success_from_offered(tesla_custom_charger):
    """Test retrieving the current limit from Current.Offered."""
    # Mock the entity state to return maximum_current
    def mock_entity_state(key):
        if key == TeslaCustomEntityMap.ChargerCurrent:
            return "8.5"
        return None

    # tesla_custom_charger._get_entity_state_by_key.side_effect = mock_entity_state
    tesla_custom_charger._get_entity_state_by_unique_id.side_effect = mock_entity_state

    # Call the method
    result = tesla_custom_charger.get_charge_current()

    # Verify results
    assert result == 8.5


def test_get_charge_current_missing_entity(tesla_custom_charger):
    """Test retrieving the current limit when no entities are available."""
    # Mock the entity state to return None for all entities
    # tesla_custom_charger._get_entity_state_by_key.return_value = None
    tesla_custom_charger._get_entity_state_by_unique_id.return_value = None

    # Call the method
    result = tesla_custom_charger.get_charge_current()

    # Verify results
    assert result is None


def test_get_charge_current_invalid_value(tesla_custom_charger):
    """Test retrieving the current limit with invalid value."""
    # Mock the entity state to return an invalid value
    # tesla_custom_charger._get_entity_state_by_key.return_value = "invalid"
    tesla_custom_charger._get_entity_state_by_unique_id.return_value = "invalid"

    # Call the method
    result = tesla_custom_charger.get_charge_current()

    # Verify results
    assert result is None


def test_get_max_charge_current_default(tesla_custom_charger):
    """Test retrieving the max current limit with default value."""
    # Mock the entity state to return None
    # tesla_custom_charger._get_entity_state_by_key.return_value = None
    tesla_custom_charger._get_entity_state_by_unique_id.return_value = None

    # Call the method
    result = tesla_custom_charger.get_max_charge_current()

    # Verify results - should return default 15A
    assert result == 15


def test_car_connected_true(tesla_custom_charger):
    """Test car_connected returns True for valid statuses."""
    for status in [
        TeslaCustomChargerConnectStateMap.On,
    ]:
        # Mock the status from connector status
        def mock_entity_state(key):
            if key == TeslaCustomEntityMap.ChargerConnectState:
                return status
            return None

        # tesla_custom_charger._get_entity_state_by_key.side_effect = mock_entity_state
        tesla_custom_charger._get_entity_state_by_unique_id.side_effect = mock_entity_state

        # Call the method
        result = tesla_custom_charger.car_connected()

        # Verify results
        assert result is True


def test_car_connected_false(tesla_custom_charger):
    """Test car_connected returns False for invalid statuses."""
    for status in [
        "off",
        None,  # Test with no status
    ]:
        # Mock the status
        def mock_entity_state(key):
            if key == TeslaCustomEntityMap.ChargerConnectState:
                return status
            return None

        # tesla_custom_charger._get_entity_state_by_key.side_effect = mock_entity_state
        tesla_custom_charger._get_entity_state_by_unique_id.side_effect = mock_entity_state

        # Call the method
        result = tesla_custom_charger.car_connected()

        # Verify results
        assert result is False


def test_can_charge_true(tesla_custom_charger):
    """Test can_charge returns True for valid statuses."""
    for status in [
        TeslaCustomChargerChargingStateMap.On,
    ]:
        # Mock the status
        def mock_entity_state(key):
            if key == TeslaCustomEntityMap.ChargerChargingState:
                return status
            return None

        # tesla_custom_charger._get_entity_state_by_key.side_effect = mock_entity_state
        tesla_custom_charger._get_entity_state_by_unique_id.side_effect = mock_entity_state

        # Call the method
        result = tesla_custom_charger.can_charge()

        # Verify results
        assert result is True


def test_can_charge_false(tesla_custom_charger):
    """Test can_charge returns False for invalid statuses."""
    for status in [
        "off",
        None,  # Test with no status
    ]:
        # Mock the status
        def mock_entity_state(key):
            if key == TeslaCustomEntityMap.ChargerConnectState:
                return status
            return None

        # tesla_custom_charger._get_entity_state_by_key.side_effect = mock_entity_state
        tesla_custom_charger._get_entity_state_by_unique_id.side_effect = mock_entity_state

        # Call the method
        result = tesla_custom_charger.can_charge()

        # Verify results
        assert result is False


def test_status_fallback(tesla_custom_charger):
    """Test that status falls back from connector to general status."""
    # Mock connector status as None, general status as Available
    def mock_entity_state(key):
        if key == TeslaCustomEntityMap.ChargerConnectState:
            raise ValueError("Connector status not available")
        elif key == TeslaCustomEntityMap.ChargerChargingState:
            return TeslaCustomChargerChargingStateMap.On
        return None

    # tesla_custom_charger._get_entity_state_by_key.side_effect = mock_entity_state
    tesla_custom_charger._get_entity_state_by_unique_id.side_effect = mock_entity_state

    # Call car_connected which uses _get_status
    result = tesla_custom_charger.car_connected()

    # Should be False since Available is not in connected statuses
    assert result is False

    # Verify both entities were queried
    expected_calls = [
        call(TeslaCustomEntityMap.ChargerConnectState),
        # call(TeslaCustomEntityMap.ChargerChargingState),
    ]
    # tesla_custom_charger._get_entity_state_by_key.assert_has_calls(expected_calls)
    tesla_custom_charger._get_entity_state_by_unique_id.assert_has_calls(expected_calls)


async def test_async_unload(tesla_custom_charger):
    """Test the async_unload method."""
    # Should not raise an exception
    await tesla_custom_charger.async_unload()


async def test_async_setup(tesla_custom_charger):
    """Test the async_setup method."""
    # Should not raise an exception
    await tesla_custom_charger.async_setup()
