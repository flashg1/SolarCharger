"""State of charge data model."""

from dataclasses import dataclass
from datetime import datetime


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class StateOfCharge:
    """State of charge data."""

    state_of_charge: float
    update_time: datetime

    def __repr__(self) -> str:
        """Return string representation of StateOfCharge."""
        return f"{self.update_time}: {self.state_of_charge}"
