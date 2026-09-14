/**
 * Custom Lovelace card: everything for one SolarCharger charger device
 * (Controls, Sensors, Diagnostic, Charge schedule, Configuration) in a
 * single GUI-discoverable card, built on the shared per-device card host in
 * solarcharger-section-card-base.js.
 *
 * Unlike solarcharger-strategy.js (a whole-view strategy, only addable via a
 * YAML hand-edit), this registers in window.customCards so it shows up
 * searchable in the standard "+ Add Card" picker -- a user finds it, picks
 * which charger device it's for via a dropdown (no YAML at all), and gets
 * the exact same Schedule/Controls/Status/Configuration layout the strategy
 * builds, since both call buildChargerSection() from solarcharger-shared.js.
 *
 * If only part of this layout is wanted on its own, see
 * solarcharger-controls-sensors-card.js / -diagnostic-card.js /
 * -schedule-card.js / -configuration-card.js -- the same device's entities,
 * split into four smaller standalone cards instead of one big one.
 */

import { buildChargerSection } from "./solarcharger-shared.js";
import { defineSectionCard } from "./solarcharger-section-card-base.js";

defineSectionCard({
  tagName: "solarcharger-charger-card",
  buildCardConfig: buildChargerSection,
  name: "SolarCharger Charger",
  description: "Controls and status for one SolarCharger charger device.",
});
