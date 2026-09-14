/**
 * Custom Lovelace card: just the Configuration section for one SolarCharger
 * charger device, GUI-discoverable via "+ Add Card".
 *
 * One of four smaller cards (see also -controls-sensors-card.js,
 * -diagnostic-card.js, -schedule-card.js) that together cover the same
 * ground as the single combined solarcharger-charger-card.js, for
 * dashboards that want to lay those sections out separately instead of as
 * one big card. Built on the shared per-device card host in
 * solarcharger-section-card-base.js.
 */

import { buildConfigurationCard } from "./solarcharger-shared.js";
import { defineSectionCard } from "./solarcharger-section-card-base.js";

defineSectionCard({
  tagName: "solarcharger-configuration-card",
  buildCardConfig: buildConfigurationCard,
  name: "SolarCharger Configuration",
  description: "Configuration entities for one SolarCharger charger device.",
});
