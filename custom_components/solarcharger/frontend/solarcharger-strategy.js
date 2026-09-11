/**
 * Lovelace view strategy for SolarCharger.
 *
 * Generates one section per charger subentry (device), pulling its entity
 * list live from the entity/device registries at render time -- so adding
 * or removing a charger through the integration's own "Add charger" flow
 * changes this view with no dashboard editing at all.
 *
 * Usage, in any dashboard's YAML:
 *
 *   views:
 *     - strategy:
 *         type: custom:solarcharger
 *
 * There is currently no GUI for picking a custom view strategy -- adding
 * this view is a one-time hand-edit of that YAML block, same as any other
 * custom Lovelace strategy. For a GUI-discoverable, one-device-at-a-time
 * alternative (searchable in "+ Add Card"), see solarcharger-charger-card.js,
 * which reuses the exact same grouping logic from solarcharger-shared.js.
 *
 * Per charger device, four blocks, built entirely from two stable signals
 * this integration already sets on every entity (see entity.py):
 *   - translation_key, which always equals the Python config_item constant
 *     (eg. "charge_limit_monday"), independent of user-renamed entity_ids.
 *   - entity_category ("config" / "diagnostic" / none), which the backend
 *     assigns per entity.
 *
 *   1. Schedule    -- translation_key matches charge_limit_<weekday> /
 *                     charge_endtime_<weekday>, rendered Monday->Sunday in a
 *                     fixed order (never alphabetical -- "Friday" sorts
 *                     before "Monday" and would silently scramble the week).
 *   2. Controls    -- remaining entities with entity_category unset
 *                     (HA's "primary" category), domain switch/select/number/
 *                     button, ie. day-to-day toggles and setpoints.
 *   3. Status      -- remaining sensor/datetime entities: primary ones
 *                     first, then entity_category "diagnostic" ones.
 *   4. Advanced settings -- remaining entity_category "config" entities,
 *                     collapsed by default via expander-card. Skipped
 *                     entirely for a device with nothing left in it.
 *
 * The "Global defaults" pseudo-device is deliberately excluded: it has no
 * attached Charger/Chargeable, so it never gets the main "charge" switch
 * (translation_key "charge") -- that's the signal used to tell a real
 * charger device apart from Global Defaults, rather than matching on the
 * device's (user-renamable) name.
 */

import { buildChargerSection, getChargerDevices, groupEntitiesByDevice } from "./solarcharger-shared.js";

class SolarchargerViewStrategy extends HTMLElement {
  static async generate(_config, hass) {
    const entitiesByDevice = groupEntitiesByDevice(hass);
    const chargerDevices = getChargerDevices(hass);

    const sections = chargerDevices.map((device) =>
      buildChargerSection(device, entitiesByDevice.get(device.id) || [])
    );

    return {
      type: "sections",
      max_columns: 2,
      sections,
    };
  }
}

customElements.define("ll-strategy-view-solarcharger", SolarchargerViewStrategy);
