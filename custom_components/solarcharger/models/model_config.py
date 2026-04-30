"""Config data models."""

from dataclasses import dataclass
from typing import Any


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ConfigValue:
    """Result for entity value."""

    config_item: str
    entity_id: str | None
    entity_value: Any | None

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of config value."""

        return f"{self.config_item}:(id={self.entity_id}, val={self.entity_value})"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
@dataclass
class ConfigValueDict:
    """Dictionary of entity values."""

    config_item: str
    config_values: dict[str, ConfigValue]

    # ----------------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return string representation of config value."""

        return f"{self.config_values.values()}"
