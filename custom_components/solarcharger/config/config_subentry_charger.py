# ruff: noqa: TID252, RET504
"""Config subentry flow to create charger using supported integrations."""

import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)

# import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.selector import (
    DeviceFilterSelectorConfig,
    DeviceSelector,
    DeviceSelectorConfig,
    #    EntitySelector,
    #    EntitySelectorConfig,
    #    NumberSelector,
)
from homeassistant.util import slugify

from ..const import (
    DOMAIN_BYD_VEHICLE,
    DOMAIN_ESPHOME,
    DOMAIN_GEELY_CONNECT,
    DOMAIN_GWM_ORA,
    DOMAIN_KIA_UVO,
    DOMAIN_MG_SAIC,
    DOMAIN_MQTT,
    DOMAIN_MYSKODA,
    DOMAIN_OCPP,
    DOMAIN_TESLA_CUSTOM,
    DOMAIN_TESLA_FLEET,
    DOMAIN_TESLEMETRY,
    DOMAIN_TESSIE,
    DOMAIN_VOLVO,
    ERROR_DEVICE_ALREADY_ADDED,
    ERROR_MISSING_DEVICE_NAME,
    ERROR_SELECT_CHARGER,
    ERROR_SUBENTRY_CREATED,
    ESPHOME_TESLA_BLE_MANUFACTURER,
    ESPHOME_TESLA_BLE_MODEL,
    MQTT_TESLA_BLE_MANUFACTURER,
    MQTT_TESLA_BLE_MODEL,
    OCPP_CENTRAL_SYSTEM_MODEL,
    OPTION_CHARGER_NAME,
    SUBENTRY_CHARGER_DEVICE_DOMAIN,
    SUBENTRY_CHARGER_DEVICE_ID,
    SUBENTRY_CHARGER_DEVICE_NAME,
    SUBENTRY_CHARGER_DEVICE_SUBDOMAIN,
    SUBENTRY_TYPE_CHARGER,
    SUPPORTED_CHARGER_DOMAIN_LIST,
)
from ..exceptions.validation_exception import ValidationExceptionError
from ..helpers.utils import compose_subdomain
from .config_options_flow import process_api_config
from .config_utils import (
    async_ha_store_load,
    async_ha_store_save,
    async_ha_store_update_device_list,
    get_subentry_id,
    ha_store_open,
)

# ----------------------------------------------------------------------------
# Local constants and variables
# ----------------------------------------------------------------------------
_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Global functions
# ----------------------------------------------------------------------------
def _validate_charger_selection(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger selection step."""
    if not data.get(SUBENTRY_CHARGER_DEVICE_ID):
        raise ValidationExceptionError("base", ERROR_SELECT_CHARGER)

    return data


# ----------------------------------------------------------------------------
def _validate_charger_config(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input for charger config step."""
    return data


# ----------------------------------------------------------------------------
def _validate_power_input(_hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input for the power collection step."""
    # Return info that you want to store in the config entry.
    return data


# ----------------------------------------------------------------------------
async def _async_setup_options(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    subentry_unique_id: str,
    domain: str,
    name: str,
    device_id: str,
) -> None:
    """Set up default options for the new subentry."""

    _LOGGER.debug(
        "Setting up default options for subentry with unique_id: %s",
        subentry_unique_id,
    )

    # entry.options = {
    #     **entry.options,
    #     subentry_unique_id: {
    #         OPTION_CHARGER_DEVICE_NAME: device_name,
    #     },
    # }

    # await self.reset_api_entities(
    #     config_name,
    #     device_name,
    #     data,
    # )

    device_name = slugify(name)
    data: dict[str, Any] = {
        OPTION_CHARGER_NAME: device_name,
    }

    # Look for historical config left behind by a previous installation.
    store = ha_store_open(hass, subentry_unique_id)
    store_config = await async_ha_store_load(store)
    if store_config is not None:
        data.update(store_config)

    process_api_config(config_entry, subentry_unique_id, data, is_init_all=True)

    # Save device settings to file storage.
    await async_ha_store_save(store, data)
    await async_ha_store_update_device_list(hass, domain, name, device_id)

    # Use | (union) to replace or add key:data pair.
    hass.config_entries.async_update_entry(
        config_entry,
        options=config_entry.options
        | {
            subentry_unique_id: data,
        },
    )


# ----------------------------------------------------------------------------
async def async_create_charger_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry[Any],
    input_data: dict[str, Any],
) -> str | None:
    """Create charger device."""

    # Get charger device subentry
    thirdparty_charger_id: str | None = input_data.get(SUBENTRY_CHARGER_DEVICE_ID)
    if not thirdparty_charger_id:
        error_msg = f"Subentry {SUBENTRY_CHARGER_DEVICE_ID} not defined"
        # raise ValueError(error_msg)
        return error_msg

    registry: DeviceRegistry = dr.async_get(hass)
    thirdparty_charger: DeviceEntry | None = registry.async_get(thirdparty_charger_id)
    if not thirdparty_charger:
        error_msg = (
            f"Charger device {thirdparty_charger_id} not found in device registry."
        )
        # raise ValueError(error_msg)
        return error_msg

    # Get charger domain and name to create unique_id
    # Tesla has 2 config entries in "Device info": Tesla Custom Integration, Template
    # thirdparty_config_entry_id: str | None = None
    thirdparty_config_entry: ConfigEntry | None = None

    for entry_id in thirdparty_charger.config_entries:
        entry: ConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
        if entry is not None:
            # Best guess to match
            if entry.domain in SUPPORTED_CHARGER_DOMAIN_LIST:
                # thirdparty_config_entry_id = entry_id
                thirdparty_config_entry = entry
                break

    # Tesla has 2 config entries in "Device info": Tesla Custom Integration, Template
    # So following can sometimes can get Template as domain name!
    # thirdparty_config_entry_id: str = next(
    #     iter(thirdparty_charger.config_entries)
    # )
    # thirdparty_config_entry: ConfigEntry | None = (
    #     self.hass.config_entries.async_get_entry(thirdparty_config_entry_id)
    # )

    if not thirdparty_config_entry:
        error_msg = f"{thirdparty_charger.name}: Charger config entry not found"
        # raise ValueError(error_msg)
        return error_msg

    #######################################################
    # thirdparty_charger.name is set by official Tesla mobile app.  Need reboot
    # HA for name change to take effect.
    # thirdparty_charger.name_by_user is set in HA.  Original value=None.  Can be
    # set to any string including blank in HA.
    #
    # If thirdparty_charger.name_by_user is the first choice, user will also need
    # to apply the name change to the device's entity IDs in order for SC to work.
    # This is an issue for the following reasons,
    #
    # - User might just want to change the device name and not the names for the
    # device's entities for a number of reasons.
    # - The device entities might have historical data, and there is risk involved
    # in changing these orphaned entities.
    # - The device entities might be used in automation and scripts, and a pain to
    # change them all.
    # - The device name is also used to create SC entities to form part of the SC
    # entity name, which means user will need to delete and re-add SC when they
    # changed the device name.
    # - Other custom integrations might not allow renaming of their entities even
    # though their device name can be renamed, eg. OCPP. (Tested "Tesla Custom"
    # integration do allow renaming of entities.)
    # - The name once set in the official Tesla mobile app cannot be "unnamed".
    # The name can be changed in the app, but cannot be deleted to put it back to
    # its original empty state.
    #
    # HA device display name is `name` or `name_by_user`.
    # Prefer the integration's default `name` over `name_by_user`
    # Fall back to `name_by_user` only if `name` is empty.
    # thirdparty_charger_name = (
    #     thirdparty_charger.name or thirdparty_charger.name_by_user
    # )
    #
    # To avoid complications in case of user setting different name in official
    # Tesla app sometime in the future, ensure SC just get name from single source.
    # This will ensure direct cause and effect, and avoid confusion in the future.
    #######################################################
    thirdparty_charger_name = thirdparty_charger.name
    if not thirdparty_charger_name:
        return ERROR_MISSING_DEVICE_NAME

    thirdparty_display_name = (
        f"{thirdparty_config_entry.domain} {thirdparty_charger_name}"
    )
    thirdparty_config_name = slugify(f"{thirdparty_display_name}")
    thirdparty_charger_subdomain = compose_subdomain(
        thirdparty_config_entry.domain,
        thirdparty_charger.manufacturer,
        thirdparty_charger.model,
    )

    _LOGGER.warning(
        "Create subentry %d: charger='%s' (name_by_user='%s', name='%s'), unique_id='%s', sub-domain='%s'",
        len(config_entry.subentries) + 1,
        thirdparty_charger_name,
        thirdparty_charger.name_by_user,
        thirdparty_charger.name,
        thirdparty_config_name,
        thirdparty_charger_subdomain,
    )

    # Check if subentry with this unique_id already exists
    subentry_id = get_subentry_id(config_entry, thirdparty_config_name)
    if subentry_id is not None:
        return ERROR_DEVICE_ALREADY_ADDED

    # Create new subentry
    if (
        not thirdparty_config_entry.domain
        or not thirdparty_charger_name
        or not thirdparty_charger_id
    ):
        error_msg = (
            f"Missing config entry domain, name, or ID: "
            f"{thirdparty_config_entry.domain=}, {thirdparty_charger_name=}, {thirdparty_charger_id=}"
        )
        # raise ValueError(error_msg)
        return error_msg

    hass.config_entries.async_add_subentry(
        config_entry,
        ConfigSubentry(
            subentry_type=SUBENTRY_TYPE_CHARGER,
            title=thirdparty_display_name,
            unique_id=thirdparty_config_name,
            data=MappingProxyType(  # make data immutable
                {
                    SUBENTRY_CHARGER_DEVICE_DOMAIN: thirdparty_config_entry.domain,  # Integration domain
                    SUBENTRY_CHARGER_DEVICE_SUBDOMAIN: thirdparty_charger_subdomain,  # Integration sub-domain
                    SUBENTRY_CHARGER_DEVICE_NAME: thirdparty_charger_name,  # Integration-specific device name
                    SUBENTRY_CHARGER_DEVICE_ID: thirdparty_charger_id,  # Integration-specific device ID
                }
            ),
        ),
    )

    await _async_setup_options(
        hass,
        config_entry,
        thirdparty_config_name,
        thirdparty_config_entry.domain,
        thirdparty_charger_name,
        thirdparty_charger_id,
    )

    _LOGGER.info(
        "Created subentry %d: charger='%s', unique_id='%s', sub-domain='%s'",
        len(config_entry.subentries),
        thirdparty_charger_name,
        thirdparty_config_name,
        thirdparty_charger_subdomain,
    )

    return None


# ----------------------------------------------------------------------------
def _get_supported_devices(
    hass: HomeAssistant,
) -> list[DeviceFilterSelectorConfig]:
    """Dynamically build the selector filters, excluding the OCPP Central System."""

    # 1. Start with your base explicit/static integrations.
    supported_devices: list[DeviceFilterSelectorConfig] = [
        DeviceFilterSelectorConfig(integration=DOMAIN_TESLA_CUSTOM),
        DeviceFilterSelectorConfig(
            integration=DOMAIN_MQTT,
            manufacturer=MQTT_TESLA_BLE_MANUFACTURER,
            model=MQTT_TESLA_BLE_MODEL,
        ),
        DeviceFilterSelectorConfig(
            integration=DOMAIN_ESPHOME,
            manufacturer=ESPHOME_TESLA_BLE_MANUFACTURER,
            model=ESPHOME_TESLA_BLE_MODEL,
        ),
        DeviceFilterSelectorConfig(integration=DOMAIN_TESLA_FLEET),
        DeviceFilterSelectorConfig(integration=DOMAIN_TESSIE),
        DeviceFilterSelectorConfig(integration=DOMAIN_TESLEMETRY),
        DeviceFilterSelectorConfig(integration=DOMAIN_MYSKODA),
        DeviceFilterSelectorConfig(integration=DOMAIN_BYD_VEHICLE),
        DeviceFilterSelectorConfig(integration=DOMAIN_GWM_ORA),
        DeviceFilterSelectorConfig(integration=DOMAIN_KIA_UVO),
        DeviceFilterSelectorConfig(integration=DOMAIN_GEELY_CONNECT),
        DeviceFilterSelectorConfig(integration=DOMAIN_VOLVO),
        DeviceFilterSelectorConfig(integration=DOMAIN_MG_SAIC),
    ]

    # 2. Query the Device Registry to explicitly find allowed OCPP models.
    dev_reg = dr.async_get(hass)
    allowed_ocpp_models: set[str] = set()

    for device in dev_reg.devices.values():
        # Check if this device belongs to the OCPP integration.
        is_ocpp = any(identifier[0] == DOMAIN_OCPP for identifier in device.identifiers)

        if is_ocpp and device.model:
            # Drop device models that are not supported.
            if device.model != OCPP_CENTRAL_SYSTEM_MODEL:
                allowed_ocpp_models.add(device.model)

    # 3. Add explicit inclusive filters for only the valid OCPP models found.
    if allowed_ocpp_models:
        supported_devices.extend(
            [
                DeviceFilterSelectorConfig(integration=DOMAIN_OCPP, model=model_name)
                for model_name in allowed_ocpp_models
            ]
        )

    return supported_devices


# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
class AddChargerSubEntryFlowHandler(ConfigSubentryFlow):
    """Handles subentry flow for creating charger."""

    # cf_data: dict | None = None

    # ----------------------------------------------------------------------------
    # def _set_global_defaults(self, data: dict[str, dict[str, Any]]) -> None:
    #     """Set global data for the config flow."""
    #     self.cf_data = data or {}

    # ----------------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Entry point for subentry config. Prompts for charger selection."""
        errors: dict[str, str] = {}
        input_data: dict[str, Any] | None = None

        config_entry = self._get_entry()
        # config_entry.solarcharger_data = {}
        if user_input is not None:
            try:
                input_data = _validate_charger_selection(self.hass, user_input)
            except ValidationExceptionError as ex:
                errors[ex.base] = ex.key

            if not errors and input_data is not None:
                # self.cf_data = input_data
                # await self.async_step_config_charger()

                error_msg = await async_create_charger_device(
                    self.hass, config_entry, input_data
                )
                if error_msg is not None:
                    _LOGGER.error("%s", error_msg)
                    return self.async_abort(reason=error_msg)

                # Must return with SubentryFlowResult as stipulated in the return type
                return self.async_abort(
                    reason=ERROR_SUBENTRY_CREATED,
                    # description_placeholders={
                    #     "subentry": thirdparty_config_name,
                    #     "subentry_count": f"{len(config_entry.subentries)}",
                    # },
                )

        select_charger_schema = vol.Schema(
            {
                vol.Required(SUBENTRY_CHARGER_DEVICE_ID): DeviceSelector(
                    DeviceSelectorConfig(
                        multiple=False,
                        filter=_get_supported_devices(self.hass),
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=select_charger_schema, errors=errors
        )
