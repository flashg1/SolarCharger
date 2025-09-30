"""SolarCharger base entity."""

import logging

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONFIG_URL, DOMAIN, ICON, MANUFACTURER, VERSION

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerEntity(Entity):
    """SolarCharger base entity class."""

    _attr_icon = ICON
    _attr_has_entity_name = True

    _entity_key: str

    def __init__(
        self,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the SolarCharger base entity."""
        self._subentry = subentry
        self._attr_translation_key = self._entity_key

        # self._attr_should_poll = False
        # self._attr_has_entity_name = True
        # self._attr_unique_id = entity_full_name
        # self._attr_name = self.type.capitalize()
        # self._attr_entity_registry_enabled_default = self._enabled_by_default

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._subentry.subentry_id)},
            name=self._subentry.title,
            model=VERSION,
            manufacturer=MANUFACTURER,
            configuration_url=(CONFIG_URL),
        )

    def set_entity_id(self, platform_str, key):
        """Set the entity id."""
        entity_id = f"{platform_str}.{DOMAIN}_{self._subentry.unique_id}_{key}"
        _LOGGER.debug("entity_id = %s", entity_id)
        self.entity_id = entity_id

    def update_ha_state(self):
        """Update the HA state."""
        if self.entity_id is not None and self.hass is not None:
            self.async_schedule_update_ha_state()
