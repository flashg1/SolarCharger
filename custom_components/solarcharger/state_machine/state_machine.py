"""State machine implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# Reference
# https://auth0.com/blog/state-pattern-in-python/


class StateMachine:
    """The StateMachine class is the context. It should be initiated with a default state."""

    def __init__(self, state: DeviceState) -> None:
        """Initialize the state machine with a state."""

        self.set_state(state)

    # ----------------------------------------------------------------------------
    def set_state(self, state: DeviceState):
        """Method to change the state of the object."""

        self._state = state
        self._state.state_machine = self

    # ----------------------------------------------------------------------------
    def get_state_name(self) -> str:
        """Get current state name of object."""

        return type(self._state).__name__

    # ----------------------------------------------------------------------------
    async def async_action_state(self):
        """Method for executing the device functionality. These depends on the current state of the object."""

        await self._state.async_activate_state()

    # ----------------------------------------------------------------------------
    def pushUpAndDownBtns(self) -> None:
        """If both the buttons are pushed at a time, nothing should happen."""
        _LOGGER.info("Oops.. you should press one button at a time")

    # ----------------------------------------------------------------------------
    def noBtnPushed(self) -> None:
        """If no button was pushed, it should just wait open for guests."""
        _LOGGER.info("Press any button. Up or Down")


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class DeviceState(ABC):
    """The common state interface for all the states."""

    # ----------------------------------------------------------------------------
    @property
    def state_machine(self) -> StateMachine:
        """Get the state machine."""
        return self._context

    @state_machine.setter
    def state_machine(self, context: StateMachine) -> None:
        """Set the state machine."""
        self._context = context

    # ----------------------------------------------------------------------------
    @abstractmethod
    async def async_activate_state(self) -> None:
        """Start state action."""


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateInitialise(DeviceState):
    """Initialising state: wake up device, etc."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start initialising state."""
        self.state_machine.set_state(StateCharge())


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateCharge(DeviceState):
    """Charging state: Turn on charger and start charging."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start charging state."""
        self.state_machine.set_state(StateTidyUp())


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateTidyUp(DeviceState):
    """Tidy up state: Turn off charger."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start tidy up state."""
        self.state_machine.set_state(StateEnd())


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StatePause(DeviceState):
    """Pause state: Turn off charger and wait for external trigger."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start pause state."""
        self.state_machine.set_state(StateCharge())


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateAbort(DeviceState):
    """Abort state: Abort charge."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start abort state."""


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class StateEnd(DeviceState):
    """End state: Signal completion."""

    # ----------------------------------------------------------------------------
    async def async_activate_state(self) -> None:
        """Start end state."""


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
async def main() -> None:
    """The main function."""

    # if __name__ == "__main__":
    # The client code.

    charger = StateMachine(StateInitialise())
    while True:
        action_state = charger.get_state_name()
        _LOGGER.info("Action state: %s", action_state)
        if action_state == "StateEnd":
            break
        await charger.async_action_state()
