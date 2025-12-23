# Changelog

## v0.2beta1 2025-12-23
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

## v0.1beta3 2025-11-02
- Pick the right domain for integration with more than one config entries in device info.
- Disable local device entities. User needs to manually enable if required.
- Create global defaults on first start.
- Tidied up subentry config name.
- Linked charger allocated power.

## v0.1beta1 2025-10-31
- Completed basic charge control test run.

## v0.1beta0 2025-09-30
- Creation.
