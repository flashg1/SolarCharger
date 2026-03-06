"""SolarCharger base entity."""

from enum import Enum
import logging

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .config_utils import get_device_domain, is_api_defined_solarcharger_entity
from .const import (
    CONFIG_NAME_GLOBAL_DEFAULTS,
    CONFIG_URL,
    DEVICE_MODEL_MAP,
    DOMAIN,
    DOMAIN_OCPP,
    DOMAIN_TESLA_CUSTOM,
    DOMAIN_TESLA_FLEET,
    DOMAIN_TESLA_TESSIE,
    ICON,
    MANUFACTURER,
    SUBDOMAIN_ESPHOME_TESLA_BLE,
    SUBDOMAIN_MQTT_TESLA_BLE,
    SUBENTRY_CHARGER_TYPES,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
def compose_entity_id(platform_str: str, subentry_unique_id: str | None, key: str):
    """Compose the entity id."""

    id_name = slugify(f"{DOMAIN}_{subentry_unique_id}_{key}")
    return f"{platform_str}.{id_name}"


# ----------------------------------------------------------------------------
def compose_entity_unique_id(platform_str: str, subentry: ConfigSubentry, key: str):
    """Compose the entity unique id for HA internal use only."""

    return f"{subentry.subentry_id}.{slugify(subentry.unique_id)}.{platform_str}.{slugify(key)}"


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerEntityType(Enum):
    """Enumeration of Solar Charger entity types."""

    #####################################
    # Create global default entities for all devices
    #####################################
    TYPE_GLOBAL = "global_default"

    #####################################
    # Create local device entities
    #####################################
    # For all devices
    TYPE_LOCAL = "local_default"
    TYPE_LOCALHIDDEN = "local_hidden"

    # For specify device
    # Only the following can be placed in a list when defining entities. All others must be single entity type.
    TYPE_LOCAL_OCPP = DOMAIN_OCPP
    TYPE_LOCAL_TESLA_CUSTOM = DOMAIN_TESLA_CUSTOM
    TYPE_LOCAL_TESLA_MQTTBLE = SUBDOMAIN_MQTT_TESLA_BLE
    TYPE_LOCAL_TESLA_ESPBLE = SUBDOMAIN_ESPHOME_TESLA_BLE
    TYPE_LOCAL_TESLA_FLEET = DOMAIN_TESLA_FLEET
    TYPE_LOCAL_TESLA_TESSIE = DOMAIN_TESLA_TESSIE
    TYPE_LOCAL_USER_CUSTOM = DOMAIN

    #####################################
    # Create both local device and global default entities for all devices
    #####################################
    TYPE_LOCALHIDDEN_GLOBALHIDDEN = "hidden_default"
    TYPE_LOCAL_GLOBAL = "local_and_global"
    # Local device default if exists will take precedence over global default. Local device entities are hidden.
    TYPE_LOCALHIDDEN_GLOBAL = "local_hidden_or_global"


# ----------------------------------------------------------------------------
def is_entity_enabled(
    subentry: ConfigSubentry, entity_type: SolarChargerEntityType
) -> bool:
    """Disable entity if hidden.

    Global default entities = Enabled.
    Charger specific entities = Enabled. (eg. TYPE_LOCAL_OCPP)
    Local device entities = Disabled.
    """

    enabled: bool = True

    if entity_type == SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBALHIDDEN or (
        #####################################
        # Charger subentry
        #####################################
        subentry.subentry_type in SUBENTRY_CHARGER_TYPES
        and entity_type
        in (
            SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBAL,
            SolarChargerEntityType.TYPE_LOCALHIDDEN,
        )
    ):
        enabled = False

    return enabled


# ----------------------------------------------------------------------------
def get_single_entity_type(
    subentry: ConfigSubentry,
    entity_type: SolarChargerEntityType | list[SolarChargerEntityType],
) -> SolarChargerEntityType:
    """Get the single entity type from a list of entity types or return the entity type if it's not a list."""

    if subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
        # Charger subentry types
        device_domain = get_device_domain(subentry)
        if device_domain is None:
            raise SystemError(
                f"Device domain is None for subentry {subentry.unique_id}"
            )

        # entity_type is a list of SolarChargerEntityType for charger specific entities.
        if isinstance(entity_type, list):
            if len(entity_type) <= 0:
                raise ValueError("Expected at least a single entity type in list.")

            if SolarChargerEntityType(device_domain) in entity_type:
                single_entity_type = SolarChargerEntityType(device_domain)
            else:
                # If is_create_entity() is true, code will never reach here.
                single_entity_type = SolarChargerEntityType.TYPE_LOCALHIDDEN
        else:
            single_entity_type = entity_type

    else:
        # Global defaults subentry types
        if isinstance(entity_type, list):
            raise ValueError(
                "Global default entity must be defined with a single entity type."
            )

        single_entity_type = entity_type

    return single_entity_type


# ----------------------------------------------------------------------------
def is_create_entity(
    subentry: ConfigSubentry,
    entity_type: SolarChargerEntityType | list[SolarChargerEntityType],
) -> bool:
    """Check if entity is enabled."""
    is_create: bool = False

    if subentry.subentry_type in SUBENTRY_CHARGER_TYPES:
        # Charger subentry types
        device_domain = get_device_domain(subentry)
        if device_domain is None:
            raise SystemError(
                f"Device domain is None for subentry {subentry.unique_id}"
            )

        # entity_type is a single SolarChargerEntityType.
        if isinstance(entity_type, SolarChargerEntityType):
            if (
                entity_type
                in (
                    SolarChargerEntityType.TYPE_LOCAL,
                    SolarChargerEntityType.TYPE_LOCALHIDDEN,
                    SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBALHIDDEN,
                    SolarChargerEntityType.TYPE_LOCAL_GLOBAL,
                    SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBAL,
                )
                or entity_type.value == device_domain
            ):
                is_create = True

        # entity_type is a list of SolarChargerEntityType for charger specific entities.
        elif SolarChargerEntityType(device_domain) in entity_type:
            is_create = True

    else:  # noqa: PLR5501
        # Global defaults subentry types
        if entity_type in (
            SolarChargerEntityType.TYPE_GLOBAL,
            SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBALHIDDEN,
            SolarChargerEntityType.TYPE_LOCAL_GLOBAL,
            SolarChargerEntityType.TYPE_LOCALHIDDEN_GLOBAL,
        ):
            is_create = True

    return is_create


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class SolarChargerEntity(Entity):
    """SolarCharger base entity class."""

    _attr_icon = ICON
    _attr_has_entity_name = True

    _entity_key: str

    def __init__(
        self,
        config_item: str,
        subentry: ConfigSubentry,
        entity_type: SolarChargerEntityType,
    ) -> None:
        """Initialize the SolarCharger base entity."""
        self._entity_key = config_item
        self._attr_translation_key = config_item
        self._subentry = subentry
        self._entity_type = entity_type

        # Set all SolarCharger entities to push-pull only.
        # Use either poll or push, but not both at the same time. Otherwise will get
        # twice the updates, once from polling and once from push!
        # Also update by polling only can be delayed by few seconds.
        self._attr_should_poll = False

        # self._attr_has_entity_name = True
        # self._attr_unique_id = entity_full_name
        # self._attr_name = self.type.capitalize()
        # self._attr_entity_registry_enabled_default = self._enabled_by_default

        #####################################
        # Hidden entities are disabled unless it is defined in the charger API.
        #
        # Global default entities = Enabled
        # Charger specific entities = Enabled (eg. TYPE_LOCAL_OCPP)
        # Local device entities = Disabled unless defined in charger API **using same config_item key** (eg. max current)
        #
        # Note:
        # - OCPP and user custom charge limit entities use different config keys for get and set, and for the entity itself.
        # - OCPP and user custom charge limit entities are enabled by TYPE_LOCAL_OCPP and TYPE_LOCAL_USER_CUSTOM respectively.
        #####################################
        self._attr_entity_registry_enabled_default = is_entity_enabled(
            subentry, entity_type
        ) or is_api_defined_solarcharger_entity(subentry, config_item)

        domain = get_device_domain(subentry)
        if domain is None:
            domain = CONFIG_NAME_GLOBAL_DEFAULTS
        device_model = DEVICE_MODEL_MAP.get(domain)

        self._attr_device_info = DeviceInfo(
            # Best to use a non-changing variable as identifier in the device registry.
            # identifiers={(DOMAIN, self._subentry.unique_id)},
            identifiers={(DOMAIN, self._subentry.subentry_id)},
            name=self._subentry.title,
            manufacturer=MANUFACTURER,
            model=device_model,
            sw_version=VERSION,
            configuration_url=(CONFIG_URL),
        )

    # ----------------------------------------------------------------------------
    def set_entity_id(self, platform_str, key):
        """Set the entity id."""

        self.entity_id = compose_entity_id(platform_str, self._subentry.unique_id, key)
        _LOGGER.debug("entity_id = %s", self.entity_id)

    # ----------------------------------------------------------------------------
    def set_entity_unique_id(self, platform_str, key):
        """Set the entity unique id for HA internal use only."""

        # id_name = self._entity_key.replace("_", "").lower()
        # self._attr_unique_id = f"{subentry.subentry_id}.{SWITCH}.{id_name}"
        # self._attr_unique_id = f"{self._subentry.subentry_id}.{self._subentry.unique_id}.{platform_str}.{slugify(key)}"
        self._attr_unique_id = compose_entity_unique_id(
            platform_str, self._subentry, key
        )
        _LOGGER.debug("unique_entity_id = %s", self._attr_unique_id)

    # ----------------------------------------------------------------------------
    def update_ha_state(self):
        """Update the HA state."""

        if self.entity_id is not None and self.hass is not None:
            self.async_schedule_update_ha_state()
