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

    # # config_time -> entity_id
    # config_entities: dict[str, str] = {}

    # # config_item -> value
    # config_values: dict[str, Any] = {}


@dataclass
class ConfigValueDict:
    """Dictionary of entity values."""

    config_item: str
    config_values: dict[str, ConfigValue]
