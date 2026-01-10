# Changelog

## v0.3beta3 2026-01-10
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
