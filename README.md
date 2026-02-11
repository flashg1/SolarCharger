# <img src="https://brands.home-assistant.io/solarcharger/dark_icon.png" alt="SolarCharger" width="50" style="vertical-align:Left;" /> Solar charger custom integration for Home Assistant

[![Stable][releases-shield]][releases] [![HACS Badge][hacs-badge]][hacs-link] ![Project Maintenance][maintenance-shield] [![GitHub Activity][commits-shield]][commits] [![License][license-shield]](LICENSE) [![Downloads (all releases)][total-downloads]][solarcharger-link] [![Downloads (latest release)][latest-downloads]][solarcharger-link]

[solarcharger-link]: https://github.com/flashg1/SolarCharger
[commits-shield]: https://img.shields.io/github/commit-activity/y/flashg1/SolarCharger.svg
[commits]: https://github.com/flashg1/SolarCharger/commits/main
[license-shield]: https://img.shields.io/github/license/flashg1/SolarCharger.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[releases-shield]: https://img.shields.io/github/release/flashg1/SolarCharger.svg
[releases]: https://github.com/flashg1/SolarCharger/releases/latest
[hacs-badge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg
<!-- [total-downloads]: https://img.shields.io/github/downloads/flashg1/SolarCharger/total -->
[total-downloads]: https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.solarcharger.total
<!-- [latest-downloads]: https://img.shields.io/github/downloads/flashg1/SolarCharger/latest/total -->
[latest-downloads]: https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=latest%20version&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.solarcharger.versions['0.3.10']
[hacs-link]: https://hacs.xyz/


## Solar Charger - Work in progress


## Disclaimer:
Even though this custom integration has been created with care, the author cannot be responsible for any damage caused by this integration.  Use at your own risk.


## Overview
Home Assistant solar charger custom integration using OCPP and/or EV specific API to charge EV from surplus solar and weather forecast.

![Screenshot_20230702-094232_Home Assistant](https://github.com/flashg1/TeslaSolarCharger/assets/122323972/58d1df89-905b-422c-8542-0081b9fa342f)

![Screenshot_20230630-135925_Home Assistant](https://github.com/flashg1/TeslaSolarCharger/assets/122323972/2f04b1e2-b56d-493c-977f-82d5dd04cbe5)


## Features

- Charge from excess solar adjusting car charging current according to feedback loop value "Main Power Net".  The "Main Power Net" sensor expresses negative value in Watts for available power for charging car, or positive value for consumed power.
- Support multi-day solar charging using sun elevation triggers to start and stop.
- Compatible with off-peak night time charging.
- Configurable 7 days charge limit schedule.  Default is to use existing charge limit already set in car.
- Support just-in-time schedule charging to required charge limit using solar and grid if charge completion time is set for the day.
- Automatically charge more today if today has no charge completion time and next 3 days have higher charge limit.
- Automatically adjust to the highest charge limit set within a rainy forecast period.  The highest charge limit is selected from the 7 days charge limit settings that are within the forecast period taking into account the charge limit on bad weather setting.  The objective is to charge more before a rainy period.  Default disabled. (TODO)
- Might be possible to prolong car battery life by setting daily charge limit to 60%, and only charge more before a rainy period by enabling option to adjust daily car charge limit based on weather. (TODO)
- Allow manual top up from secondary power source (eg. grid, battery) if there is not enough solar during the day, or if required to charge during the night. Just need to set the power offset to specify the maximum power to draw from secondary power source. Also need to toggle on secondary power source if required to charge during the night. (TODO)
- Support manually setting or automatic programming of minimum charge current according to your requirement.
- Support charging multiple cars at the same time based on power allocation weighting for each car.
- Support skew to shift the power export/import curve left or right to achieve your minimal power import. (TODO)
- Configurable return codes for comparison with connect trigger states, connected states and charging states returned by your EV or charger specific API. These states are used to determine the stages of the charging process.
- Use EV specific API to control a EV for charging, and/or use OCPP to control an OCPP compliant charger to charge a EV. Only tested with [OCPP simulator](https://github.com/lewei50/iammeter-simulator) and Tesla car. OCPP and Tesla Fleet API support in beta testing phase.


**💡 Tip:** Please :star: this project if you find it useful, and may be also buy me a coffee!

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/flashg1)


## My setup
- [Home Assistant](https://www.home-assistant.io/)
- [Enphase Envoy Integration](https://www.home-assistant.io/integrations/enphase_envoy) configured for 20 seconds update interval.
- [Tesla Custom Integration](https://github.com/alandtse/tesla) v3.20.4 (to control charging Tesla via Tesla cloud).
- Tesla UMC charger, 230V, max 15A.
- Tesla Model 3.

### Other supported integrations
Entities from following integrations are also pre-configured in SolarCharger, ie. charger can be added using "Add charger device" button.  Since I am not using these integrations, these integrations have only been tested by other users.  Please feel free to ask for help in GitHub discussions.

- [Tesla BLE MQTT docker](https://github.com/tesla-local-control/tesla_ble_mqtt_docker)  This is for people who want to control their Tesla locally via Bluetooth without cloud.
- [OCPP](https://github.com/lbbrhzn/ocpp)  This is for people who want to use OCPP to control an OCPP compliant charger to charge their EV.
- [Telsa Fleet](https://www.home-assistant.io/integrations/tesla_fleet)
- [Tessie](https://www.home-assistant.io/integrations/tessie)

If your integration is not listed above, you might want to try "Add custom device" button and define your own charge control entities.


## Installation
### Install via HACS (Recommended)
The [Home Assistant Community Store (HACS)](https://www.hacs.xyz/) is a custom integration that provides a UI to manage custom elements such as Solar Charger Custom Integration in Home Assistant.
You first need to [install and configure](https://www.hacs.xyz/docs/use/) it before following these instructions below.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=flashg1&repository=SolarCharger&category=Integration)

1. Go to **HACS > Integrations** in Home Assistant
2. Search and install **SolarCharger** Integration
3. Restart Home Assistant


### Manual install
- Copy the solarcharger directory to your Home Assistant machine, ie.
```
From:  <Your git clone directory>\SolarCharger\custom_components\solarcharger
To:    \\homeassistant.local\config\custom_components\solarcharger
```
- Restart Home Assistant.

## Configuration
- Go through normal procedure to add the integration, ie. Settings > Devices & services > Add integration > Search for "SolarCharger"
- Set up "Main Power Net" sensor in Home Assistant (HA) config.  For example, for Enphase, sensor main_power_net expresses negative value in Watts for available power for charging or positive value for consumed power.  For other inverter brands, adjust the formula to conform with above requirement according to your setup.
```
Settings > Devices & services > Helpers > Create helper > Template > Template a sensor >

Name: Main power net
State template: {{ states('sensor.envoy_[YourEnvoyId]_current_power_consumption')|int - states('sensor.envoy_[YourEnvoyId]_current_power_production')|int }}
Unit of measurement: W
Device class: Power
State class: Measurement
Device: Envoy [YourEnvoyId]
```
- Add charger device, eg. Tesla, OCPP, etc.

- If using OCPP charger, configure your charger to point to your HA OCPP central server, eg. ws://homeassistant.local:9000

- Config the integration specifying the charger effective voltage, maximum current, maximum charge speed, ie.
```
SolarCharger > Global defaults > Configuration > Effective voltage
SolarCharger > Your local device > Configuration > Max current (if available)
```

How to use
==========

- Set your car charge limit.
- Connect charger to car.  Normal charging at constant current should begin immediately if schedule charging is disabled.  After a little while, the integration will take over and manage the charging current during daylight hours.  Please see [wiki](https://github.com/flashg1/SolarCharger/wiki/User-guide#automation-cannot-be-triggered) if automation cannot be triggered.
- There are 2 options on how to charge the car (see below).
- The integration will stop if charger is turned off manually or automatically by car when reaching charge limit.
- To abort charging, toggle off the "Charge" switch.

2 options on how to charge the car:

Option 1
--------
To charge from excess solar, just plug in the charger.  The initial charge current is 6A.  After about 1 minute it will adjust the current according to amount of excess power exported to grid.

Option 2
--------
To charge at full speed from secondary power source and solar, toggle on "Fast charge mode".

Please also check out the [wiki](https://github.com/flashg1/SolarCharger/wiki) pages.
