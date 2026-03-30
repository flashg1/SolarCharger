"""State machine context."""

from __future__ import annotations

from abc import ABC, abstractmethod


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class ElectricDevice:
    """The ElectricDevice class is the context. It should be initiated with a default state."""

    def __init__(self, state: DeviceState) -> None:
        """Initialize the electric device with a state."""

        self.set_state(state)

    # ----------------------------------------------------------------------------
    def set_state(self, state: DeviceState):
        """Method to change the state of the object."""

        self._state = state
        self._state.electric_device = self

    # ----------------------------------------------------------------------------
    def get_state_name(self) -> str:
        """Get current state name of object."""

        return type(self._state).__name__

    # ----------------------------------------------------------------------------
    def start(self):
        """Method for executing the device functionality. These depends on the current state of the object."""

        self._state.start()

    # ----------------------------------------------------------------------------
    # if both the buttons are pushed at a time, nothing should happen
    def pushUpAndDownBtns(self) -> None:
        print("Oops.. you should press one button at a time")

    # ----------------------------------------------------------------------------
    # if no button was pushed, it should just wait open for guests
    def noBtnPushed(self) -> None:
        print("Press any button. Up or Down")


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class DeviceState(ABC):
    """The common state interface for all the states."""

    # ----------------------------------------------------------------------------
    @property
    def electric_device(self) -> ElectricDevice:
        """Get the electric device."""
        return self._electric_device

    @electric_device.setter
    def electric_device(self, device: ElectricDevice) -> None:
        """Set the electric device."""
        self._electric_device = device

    # ----------------------------------------------------------------------------
    @abstractmethod
    def start(self) -> None:
        """Start state action."""


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateInitialise(DeviceState):
    """Initialising state: wake up device, etc."""

    # ----------------------------------------------------------------------------
    def start(self) -> None:
        """Start initialising state."""
        self.electric_device.set_state(StateCharge())


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateCharge(DeviceState):
    """Charging state: Turn on charger and start charging."""

    # ----------------------------------------------------------------------------
    def start(self) -> None:
        """Start charging state."""
        self.electric_device.set_state(StateEnd())


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StatePause(DeviceState):
    """Pause state: Turn off charger and wait for external trigger."""

    # ----------------------------------------------------------------------------
    def start(self) -> None:
        """Start pause state."""
        self.electric_device.set_state(StateCharge())


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateEnd(DeviceState):
    """End state: Turn off charger and indicate completion."""

    # ----------------------------------------------------------------------------
    def start(self) -> None:
        """Start end state."""


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateAbort(DeviceState):
    """Abort state: Abort charge."""

    # ----------------------------------------------------------------------------
    def start(self) -> None:
        """Start abort state."""


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # The client code.

    charger = ElectricDevice(StateInitialise())
    charger.get_state_name()

    charger.start()
