"""Tests for the OCPP charger implementation."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.helpers.device_registry import DeviceEntry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.solarcharger.chargers.ocpp_charger import (
    OcppCharger,
    OcppEntityMap,
    OcppStatusMap,
)
from custom_components.solarcharger.const import CHARGER_DOMAIN_OCPP
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
        title="OCPP Test Charger",
        data={"charger_type": "ocpp"},
        unique_id="test_ocpp_charger",
        subentries_data=[
            ConfigSubentryData(
                data={
                    SUBENTRY_DEVICE_DOMAIN: "ocpp",
                    SUBENTRY_DEVICE_NAME: "MockOcppCharger",
                    SUBENTRY_CHARGER_DEVICE: "MockOcppDeviceId",
                },
                subentry_id="MockSubentryId1",
                subentry_type=SUBENTRY_TYPE_CHARGER,
                title="ocpp TestCharger",
                unique_id="ocpp_testcharger",
            )
        ],
    )


@pytest.fixture
def mock_device_entry():
    """Create a mock DeviceEntry object for testing."""
    device_entry = MagicMock(spec=DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = {("ocpp", "test_charger")}
    return device_entry


@pytest.fixture
def ocpp_charger(mock_hass, mock_config_entry, mock_device_entry):
    """Create an OcppCharger instance for testing."""
    with patch(
        "custom_components.solarcharger.chargers.ocpp_charger.OcppCharger.refresh_entities"
    ):
        charger = OcppCharger(
            hass=mock_hass,
            config_entry=mock_config_entry,
            config_subentry=next(iter(mock_config_entry.subentries.values())),
            device_entry=mock_device_entry,
        )
        # Mock the _get_entity_state_by_key method
        charger._get_entity_state_by_key = MagicMock()
        # charger._get_entity_state_by_unique_id = MagicMock()
        return charger


def test_is_charger_device():
    """Test the is_charger_device static method."""
    # Test with OCPP device
    ocpp_device = MagicMock(spec=DeviceEntry)
    ocpp_device.identifiers = {("ocpp", "test_charger")}
    assert OcppCharger.is_charger_device(ocpp_device) is True

    # Test with non-OCPP device
    other_device = MagicMock(spec=DeviceEntry)
    other_device.identifiers = {("easee", "test_charger")}
    assert OcppCharger.is_charger_device(other_device) is False


async def test_set_charge_current(ocpp_charger, mock_hass):
    """Test setting current limits on the OCPP charger."""
    # Setup test data
    limit = 14

    # Call the method
    await ocpp_charger.set_charge_current(limit)

    # Verify service call was made with correct parameters
    mock_hass.services.async_call.assert_called_once_with(
        domain=CHARGER_DOMAIN_OCPP,
        service="set_charge_rate",
        service_data={
            "device_id": "test_device_id",
            "limit_amps": 14,  # Should use minimum of the values
        },
        blocking=True,
    )


async def test_set_charge_current_service_error(ocpp_charger, mock_hass):
    """Test setting current limits when service call fails."""
    # Setup test data
    limit = 14

    # Mock service call to raise an error
    mock_hass.services.async_call.side_effect = ValueError("Service error")

    # Call the method - should not raise an exception
    await ocpp_charger.set_charge_current(limit)

    # Verify service call was attempted
    mock_hass.services.async_call.assert_called_once()


def test_get_charge_current_success_from_offered(ocpp_charger):
    """Test retrieving the current limit from Current.Offered."""
    # Mock the entity state to return maximum_current
    def mock_entity_state(key):
        if key == OcppEntityMap.MaximumCurrent:
            return "16.5"
        return None

    ocpp_charger._get_entity_state_by_key.side_effect = mock_entity_state

    # Call the method
    result = ocpp_charger.get_charge_current()

    # Verify results
    assert result == 16.5


def test_get_charge_current_missing_entity(ocpp_charger):
    """Test retrieving the current limit when no entities are available."""
    # Mock the entity state to return None for all entities
    ocpp_charger._get_entity_state_by_key.return_value = None

    # Call the method
    result = ocpp_charger.get_charge_current()

    # Verify results
    assert result is None


def test_get_charge_current_invalid_value(ocpp_charger):
    """Test retrieving the current limit with invalid value."""
    # Mock the entity state to return an invalid value
    ocpp_charger._get_entity_state_by_key.return_value = "invalid"

    # Call the method
    result = ocpp_charger.get_charge_current()

    # Verify results
    assert result is None


def test_get_max_charge_current_default(ocpp_charger):
    """Test retrieving the max current limit with default value."""
    # Mock the entity state to return None
    ocpp_charger._get_entity_state_by_key.return_value = None

    # Call the method
    result = ocpp_charger.get_max_charge_current()

    # Verify results - should return default 32A
    assert result == 15


def test_car_connected_true(ocpp_charger):
    """Test car_connected returns True for valid statuses."""
    for status in [
        OcppStatusMap.Preparing,
        OcppStatusMap.Charging,
        OcppStatusMap.SuspendedEVSE,
        OcppStatusMap.SuspendedEV,
        OcppStatusMap.Finishing,
    ]:
        # Mock the status from connector status
        def mock_entity_state(key):
            if key == OcppEntityMap.StatusConnector:
                return status
            return None

        ocpp_charger._get_entity_state_by_key.side_effect = mock_entity_state

        # Call the method
        result = ocpp_charger.car_connected()

        # Verify results
        assert result is True


def test_car_connected_false(ocpp_charger):
    """Test car_connected returns False for invalid statuses."""
    for status in [
        OcppStatusMap.Available,
        OcppStatusMap.Reserved,
        OcppStatusMap.Unavailable,
        OcppStatusMap.Faulted,
        None,  # Test with no status
    ]:
        # Mock the status
        def mock_entity_state(key):
            if key == OcppEntityMap.StatusConnector:
                return status
            return None

        ocpp_charger._get_entity_state_by_key.side_effect = mock_entity_state

        # Call the method
        result = ocpp_charger.car_connected()

        # Verify results
        assert result is False


def test_can_charge_true(ocpp_charger):
    """Test can_charge returns True for valid statuses."""
    for status in [
        OcppStatusMap.Preparing,
        OcppStatusMap.Charging,
        OcppStatusMap.SuspendedEV,
    ]:
        # Mock the status
        def mock_entity_state(key):
            if key == OcppEntityMap.StatusConnector:
                return status
            return None

        ocpp_charger._get_entity_state_by_key.side_effect = mock_entity_state

        # Call the method
        result = ocpp_charger.can_charge()

        # Verify results
        assert result is True


def test_can_charge_false(ocpp_charger):
    """Test can_charge returns False for invalid statuses."""
    for status in [
        OcppStatusMap.Available,
        OcppStatusMap.SuspendedEVSE,
        OcppStatusMap.Finishing,
        OcppStatusMap.Reserved,
        OcppStatusMap.Unavailable,
        OcppStatusMap.Faulted,
        None,  # Test with no status
    ]:
        # Mock the status
        def mock_entity_state(key):
            if key == OcppEntityMap.StatusConnector:
                return status
            return None

        ocpp_charger._get_entity_state_by_key.side_effect = mock_entity_state

        # Call the method
        result = ocpp_charger.can_charge()

        # Verify results
        assert result is False


def test_status_fallback(ocpp_charger):
    """Test that status falls back from connector to general status."""
    # Mock connector status as None, general status as Available
    def mock_entity_state(key):
        if key == OcppEntityMap.StatusConnector:
            raise ValueError("Connector status not available")
        elif key == OcppEntityMap.Status:
            return OcppStatusMap.Available
        return None

    ocpp_charger._get_entity_state_by_key.side_effect = mock_entity_state

    # Call car_connected which uses _get_status
    result = ocpp_charger.car_connected()

    # Should be False since Available is not in connected statuses
    assert result is False

    # Verify both entities were queried
    expected_calls = [
        call(OcppEntityMap.StatusConnector),
        call(OcppEntityMap.Status),
    ]
    ocpp_charger._get_entity_state_by_key.assert_has_calls(expected_calls)


async def test_async_unload(ocpp_charger):
    """Test the async_unload method."""
    # Should not raise an exception
    await ocpp_charger.async_unload()


async def test_async_setup(ocpp_charger):
    """Test the async_setup method."""
    # Should not raise an exception
    await ocpp_charger.async_setup()
