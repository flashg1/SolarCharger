# Changelog

## v0.6.1 2026-04-26
### Breaking change
- Reminder: Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.5.4 or prior.
### Improvement
- Refactor data models and moved to models directory.
- For scheduled night-time charging, always charge at max current without pause.
- For scheduled day-time charging, it is possible to pause and not always charge at max current.
- Added starting state to set variables once per charging session.

## v0.6.0 2026-04-20
### Breaking change
- Best to set max current locally in SolarCharger instead of reading from OCPP charger.
- Moved default charge limits from settings (cog wheel) to device configuration section for database persistence. Please reset defaults if required.
- Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration).
### New feature
- Added support for [charge priority](https://github.com/flashg1/SolarCharger/wiki/User-guide#priority).
### Fix
- Fixed issue with missing OCPP devid required to set current when running multiple OCPP chargers.
### Improvement
- "Last pause duration" now shows the running pause duration.
- Get latest data and immediately check status at beginning of charge loop.

## v0.5.4 2026-04-19
### Breaking change
- Reminder: Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.4.3 or prior.
### Improvement
- Included PLUG and PRESENCE device class entities for "Device presence sensor" selection.

## v0.5.3 2026-04-11
### Breaking change
- Moved "Device presence sensor" from settings (cog wheel) to device configuration section. Please reset "Device presence sensor" and turn on "Presence trigger" if required.
- Reminder: Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.4.3 or prior.
### Improvement
- Log pause duration on pause exit.
- Log start of device detection.

## v0.5.2 2026-04-04
### Breaking change
- Reminder: Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.4.3 or prior.
### Fix
- Fixed issue with SolarCharger not stopping after unplugging charger in paused state.
### Improvement
- Refactored SolarCharge to handle both charging and paused states.
- Added "Pause count", "Average pause duration" and "Last pause duration" sensors for pause stats per charge session.
- Cleaned up code.

## v0.5.1 2026-04-04
### Breaking change
- Reminder: Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.4.3 or prior.
### Fix
- Fixed issue with SolarCharger not stopping at sunset when in paused state.
### Improvement
- Improved semaphore code to wake up and update HA on device presence detection.

## v0.5.0 2026-03-23
### Breaking change
- Changed "Allocated power" from number to sensor. Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration).
### New feature
- Added [power monitor duration](https://github.com/flashg1/SolarCharger/wiki/User-guide#power-monitor-duration) to turn off charger if average power in duration drops below "Min workable current". Requires "Min workable current" to be a non-zero value.
### Improvement
- The minimum requirement for a custom charger is the charger on/off switch entity.
- Updated run state sensor to reflect state-machine states.
- Refactored to use state machine to manage charging process.
- Added charger "Instance count", "Share allocation" and "Consumed power" sensors.
- SolarCharge class now has direct access to control entities.
- "Power allocation weight" can be zero, ie. keep current power level and not get future power allocation/deallocation.
- "Power allocation weight" and "Allocated power" entities can now be overriden in config.
- Included brand icons for SolarCharger starting with HA 2026.3.
- Included sun integration as dependency in manifest.json.

## v0.4.3 2026-03-18
### Breaking change
- Reminder: Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.3.13 or prior.
### New feature
- Added support for Teslemetry charger (beta release).

## v0.4.2 2026-03-14
### Breaking change
- Reminder: Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.3.13 or prior.
- With "Sun trigger" off, "Sunset elevation end trigger" will no longer stop SolarCharger.
### New feature
- With "Sun trigger" off, SolarCharger will continue to adjust current as long as there is surplus power (eg. from battery, wind turbine, etc.) irrespective of time of day. Thanks @mrblond18 for the idea.
- If all triggers are turned off (ie. Plugin trigger, Sun trigger, Schedule charge), user can now program their own automation to start and stop charger without interference from SolarCharger.

## v0.4.1 2026-03-11
### Breaking change
- Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration) if upgrading from v0.3.13 or prior.
### New feature
- Added support for [ping ICMP](https://github.com/flashg1/SolarCharger/wiki/User-guide#use-ping-to-detect-car-and-update-ha-to-get-latest-status) to detect device presence.
### Fix
- Catch possible exception converting UTC min time to local time during restore, and just set to UTC min time without conversion.
- Changed Tesla Fleet domain name from tesla to tesla_fleet.
- Fixed bug that uses the same entity to set and get charge current for esphome-tesla-ble.
### Improvement
- Added max number of allowable consecutive failures in charge loop before aborting charge.

## v0.4.0 2026-02-22
### Breaking change
- Created separate entities for get and set device charge limit. Please [delete then re-add the integration](https://github.com/flashg1/SolarCharger/wiki/Configuration#how-to-delete-and-re-add-the-solarcharger-integration).
### New feature
- Added support for PedroKTFC esphome-tesla-ble charger (beta release).
### Improvement
- Improved charge loop exception handling to only increase loop count after switching on charger.
- Support setting defaults for chargers from differet manufacturers under the same domain, eg. mqtt, esphome.
- Lint ignore TRY401.
- Moved OCPP cached_property from sc_option_state to ocpp_charger.

## v0.3.13 2026-02-18
### Improvement
- Added config to set OCPP charge profile ID and stack level. Set stack level to -1 to use max stack level.
- Refactored SolarChargerEntityType.
- Log actual charging status.
- For OCPP, only adjust charge current when it is in charging state.
- Removed CALLBACK_HA_STARTED once triggered because unsubscribe is already done by HA.
- Removed OCPP set current entity.
- Removed async_load/unload from solar_charge.

## v0.3.12 2026-02-17
### Improvement
- Refactored _async_charge_device() and _async_calibrate_max_charge_speed_if_required().
- Tidied async_added_to_hass() and pretty print schedule data.
### Fix
- Fixed divide by zero issue when starting max charge speed calibration with SOC above 91%.

## v0.3.11 2026-02-14
### New feature
- Updating today or tomorrow charge schedule will trigger charger to reschedule charge if required.
### Improvement
- Tidied up ChargeController switch code.
- Refactored SolarCharge adding ChargeScheduler class.
- Moved local only entities from SolarCharge to sc_option_state.
- Refactored sc_option_state by removing _get_subentry().
- Refactored ChargeController adding SolarCharge class.
### Fix
- Fixed issue with "Reset charge limit and time" button not working.

## v0.3.10 2026-02-11
- Custom charger can now charge with only 2 controls, ie. on/off switch and set charge current.
- For custom charger, use on/off switch state to determine whether charger is charging or not.

## v0.3.9 2026-02-08
- Terminate charge task on HA stop or reconfigure.
- Track both EVENT_HOMEASSISTANT_STARTED and EVENT_HOMEASSISTANT_STOP events.
- Resume charge after HA restart.
- Refactored charger controller by moving charge control into controller.
- Removed redundant start charge button.

## v0.3.8.1 2026-02-07
- Updated doc for wait_net_power_update.

## v0.3.8 2026-02-05
- Added option to look ahead to reduce charge limit difference between days.
- Support for charge limit and end time changes while charging.
- Refactored setting charge limit.
- Provide code location causing exception.

## v0.3.8-beta3 2026-02-03
- Provide code location causing exception.
- Refactored setting charge limit.

## v0.3.8-beta2 2026-02-03
- Support for charge limit and end time changes while charging.

## v0.3.8-beta1 2026-02-02
- Added option to look ahead to reduce charge limit difference between days.

## v0.3.7 2026-02-02
- First stable release.

## v0.3beta7 2026-01-15
- Tidied up error code.
- Validate default charge limit change before saving option.
- Moved min/max charge limit configs back to Global defaults.

## v0.3beta6 2026-01-13
- Added option to set charge limit defaults in settings.
- Changed iot_class back to local_polling as it best describes SolarCharger communication with devices.

## v0.3beta5 2026-01-12
- Tidied coordinator.
- Minimal control entities.

## v0.3beta4 2026-01-11
- Set all SolarCharger entities to push-pull only.
- Force update is enabled for allocated power so update is send even if new value is same as old.

## v0.3beta3 2026-01-10
- Only accept new SOC state change when old and new states are different.
- SOC can be incorrect by 6% (approx. 1 hour) if required to charge to 100%.
- Changed main while loop delay to be same as power allocation update cycle.
- Moved third party integration update polling from power allocation update cycle to main while loop.
- Added switch to calibrate battery charge speed required for charge scheduling calculation.

## v0.3beta2 2026-01-09
- Added OPTION_CHARGEE_CHARGE_LIMIT local config entity for user custom charger.
- _is_connected() and _is_at_location() will always return true if sensors are not defined.
- Restored call to _async_update_ha() after setting new current. Update rate dependent on main_power_net update rate.
- Turning on force HA update switch will override the in-built update HA button.
- Added optional switch to force third party integration to update charging status in HA instead of using the third party integration in-built update HA button, ie. possibly removes dependency on third party integration update rate.
- Updated doc.

## v0.3beta1 2026-01-08
- Added feature to create user custom chargers and to define user control entities.

## v0.2beta15 2026-01-08
- Added reminder to set charger voltage and max current after adding charger.
- Changed schedule charge default to off.

## v0.2beta14 2026-01-07
- Make chargee_charge_limit modifiable if it is a local config entity (local device entities are not modifiable).
- Removed defaults for charger effective voltage and max current, ie. must be set before use.

## v0.2beta13 2026-01-06
- Removed charger_max_current and chargee_charge_limit from global default entities.
- Set next session time on exit if sun start elevation trigger is off.
- Fixed issue with incorrect check for at home status when scheduling next session.
- Updated config entity descriptions.
- Refactored required local device config entities.

## v0.2beta12 2026-01-05
- Only schedule next charge session if car is connected and at location.
- _get_schedule_data() to check if session started by timer or to scheule next session.
- Need to compare next_start_elevation_trigger_time with now_time.
- Tested MQTT BLE plugin/unplug triggers. Plugin trigger needs external automation to ping car.

## v0.2beta11 2026-01-04
- Fixed today's start time before sunrise not scheduled issue.
- Increase today charge limit if today has no end time, and tomorrow has end time and bigger charge limit.

## v0.2beta10 2026-01-03
- Do not reset next charge time if charge schedule is disabled.
- Fixed Hassfest validation DEPENDENCIES issue.

## v0.2beta9 2026-01-03
- Number slow update by polling fixed by update_ha_state() when setting number.
- Changed SWITCH_SCHEDULE_CHARGE class from SolarChargerSwitchEntity to SolarChargerSwitchAction.

## v0.2beta8 2026-01-02
- Added switch to enable/disable plug in trigger.
- Added switch to enable/disable sun elevation trigger.

## v0.2beta7 2025-12-31
- Support for Tesla MQTT BLE API with initial testing ok.
- Added support for Tesla Fleet and Tessie APIs but not tested.
- Only calculate tomorrow charge schedule if battery SOC is known.

## v0.2beta6 2025-12-31
- Give extra 1 hour if required to charge to 100%.
- Calculate charge schedule data for today or tomorrow if session is started by timer.

## v0.2beta5 2025-12-30
- Determine if session is started by timer.
- Refactored controller.py and added tracker.py.
- Always set next charge time on exit.

## v0.2beta4 2025-12-29
- Fixed incorrect buttons.py lib path.

## v0.2beta3 2025-12-27
- Just-in-time charge scheduling.
- Persist datetime and time entities across reboots.
- Test scheduling next charge session.

## v0.2beta2 2025-12-25
- Tested setting daily charge limit.
- Refactored code to determine hidden entities.
- Created entities for schedule charging.

## v0.2beta1 2025-12-23
- Refactor get_device_domain() and get_device_api_entities().
- Set device default values from CHARGE_API_DEFAULT_VALUES.
- Added configurable min/max charge limits.
- Added reconfigure flow description.
- Moved wait_net_power_update from subentry options flow to config flow.

## v0.1beta11 2025-12-22
- Added change log.
- Updated doc.

## v0.1beta10 2025-11-11
### Improvement
- Updated doc.
- Added fast charge switch.
### Fix
- Worked around issue with calculating offset time from sun elevation by using in-built sun triggers.

## v0.1beta6 2025-11-07
- All triggers will use switch to turn on charger in controller.
- Tested charger plug in sensor.
- Fixed async_track_sunrise() not coroutine issue.
- Calculate time offset for sunrise/sunset triggers.

## v0.1beta4 2025-11-06
- Tested ok with OCPP simulator.
- Allow customised hidden configs. Unhide config entities used by local device.
- Event driven charger current adjustment from net power to allocated power updates.

## v0.1beta3 2025-11-02
- Pick the right domain for integration with more than one config entries in device info.
- Disabled device local config entities. User needs to manually enable if required.
- Create global defaults on first start.
- Tidied up subentry config name.
- Calculate charger allocated power from net power.

## v0.1beta1 2025-10-31
- Added hacs workflow.
- Completed basic charge control test run.
- Save global defaults and device local config in subentry options dictionary.
- Use subentry flow to define charger devices, with each subentry defining one device.
- Use config flow to define feedback loop power, ie. net power.

## v0.1beta0 2025-09-30
- Creation.
