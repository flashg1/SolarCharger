"""Test helpers for Solar Charger."""

from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.solarcharger.chargers.charger import Charger


class MockCharger(Charger):
    """Mock implementation of a Charger for testing."""

    def __init__(self,
                 initial_current: int = 10,
                 max_current: int = 16,
                 charger_id: str = "mock_id",
                 device_id: str = "mock_device_id") -> None:
        """Initialize MockCharger with configurable parameters."""
        # Skip the parent class initialization to avoid needing HomeAssistant, etc.
        # This is safe for testing but wouldn't work in production
        self.hass = None
        self.config_entry = type('ConfigEntry', (), {'entry_id': charger_id})()
        self.device = type('DeviceEntry', (), {'id': device_id})()

        # Charger state
        self._current_limit = initial_current
        self._max_current_limit = max_current
        self._is_car_connected = False
        self._can_charge_state = False

    @staticmethod
    def is_charger_device(device: DeviceEntry) -> bool:
        """Check if the given device is a mock charger."""
        return any(id_domain == "mock" for id_domain, _ in device.identifiers)

    async def set_charge_current(self, charge_current: float) -> None:
        """Set the charger limit in amps."""
        min_value = charge_current
        self._current_limit = min_value

    def get_charge_current(self) -> float | None:
        """Get the current limit of the charger in amps."""
        return self._current_limit

    def get_max_charge_current(self) -> float | None:
        """Get the configured maximum current limit of the charger in amps."""
        return self._max_current_limit

    def car_connected(self) -> bool:
        """Return whether the car is connected to the charger."""
        return self._is_car_connected

    def can_charge(self) -> bool:
        """Return whether the car can charge."""
        return self._can_charge_state

    # Test helper methods
    def set_car_connected(self, connected: bool) -> None:
        """Set whether a car is connected for testing."""
        self._is_car_connected = connected

    def set_can_charge(self, can_charge: bool) -> None:
        """Set whether the car can charge for testing."""
        self._can_charge_state = can_charge

    def set_current_limits(self, limits: int) -> None:
        """Manually set the current limits for testing."""
        self._current_limit = limits

    def set_max_limits(self, limits: int) -> None:
        """Manually set the max current limits for testing."""
        self._max_current_limit = limits

    async def async_setup(self) -> None:
        """Set up the mock charger."""

    async def async_unload(self) -> None:
        """Unload the mock charger."""
