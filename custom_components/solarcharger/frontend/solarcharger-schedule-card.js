/**
 * Custom Lovelace card: just the Charge schedule section (weekly schedule
 * table plus the schedule-adjacent toggle/selector badges shown underneath
 * it) for one SolarCharger charger device, GUI-discoverable via "+ Add Card".
 *
 * One of four smaller cards (see also -controls-sensors-card.js,
 * -diagnostic-card.js, -configuration-card.js) that together cover the same
 * ground as the single combined solarcharger-charger-card.js, for
 * dashboards that want to lay those sections out separately instead of as
 * one big card. Built on the shared per-device card host in
 * solarcharger-section-card-base.js.
 */

import { buildScheduleCard } from "./solarcharger-shared.js";
import { defineSectionCard } from "./solarcharger-section-card-base.js";

defineSectionCard({
  tagName: "solarcharger-schedule-card",
  buildCardConfig: buildScheduleCard,
  name: "SolarCharger Charge Schedule",
  description: "Charge schedule for one SolarCharger charger device.",
  // The weekly schedule table itself has no "columns" concept, but the
  // schedule-adjacent toggle tiles underneath it (Sun trigger, etc.) do --
  // see buildScheduleSection()'s doc comment in solarcharger-shared.js.
});
