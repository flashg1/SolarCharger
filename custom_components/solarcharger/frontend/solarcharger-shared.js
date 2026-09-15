/**
 * Shared grouping/rendering logic for the SolarCharger Lovelace view strategy
 * (solarcharger-strategy.js) and the per-device cards (solarcharger-charger-card.js
 * plus the smaller solarcharger-controls-sensors-card.js / -diagnostic-card.js /
 * -schedule-card.js / -configuration-card.js, all built on top of
 * solarcharger-section-card-base.js). All of them need to turn one device's
 * entities into the same Controls/Sensors/Diagnostic/Schedule/Configuration
 * card layout (either the whole thing, or just one section of it), so that
 * logic lives here once rather than being kept in sync in several places.
 *
 * See solarcharger-strategy.js's header comment for the full design
 * rationale (translation_key / entity_category signals, why Global Defaults
 * is excluded, etc.) -- this file is the implementation, that one documents
 * the "why".
 */

import "./solarcharger-auto-grid-card.js";
import "./solarcharger-schedule-row.js";

export const SOLARCHARGER_DOMAIN = "solarcharger";

const RESET_CHARGE_LIMIT_TRANSLATION_KEY = "reset_charge_limit_and_time";

// Shown as rows in the Charge schedule card, after the reset button, instead
// of in Configuration -- schedule-adjacent toggles/selectors a user is
// likely to check right alongside the weekly schedule itself. Order here is
// the display order.
const SCHEDULE_EXTRA_TRANSLATION_KEYS = [
  "schedule_charge",
  "sun_trigger",
  "plugin_trigger",
  "device_presence_sensor",
  "device_presence_trigger",
  "exit_condition_sensor",
  "exit_condition_trigger",
  "reduce_charge_limit_difference",
];

export const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

// "custom:expander-card" (HACS) collapses the Configuration section by
// default; "entities" (a built-in card, no "custom:" prefix) renders it as a
// plain, always-visible card instead if expander-card isn't installed.
// buildAdvancedCard() shapes the config correctly for either one --
// expander-card wraps a child card via `cards:`, the plain entities card
// just wants a flat `entities:` list.
export const ADVANCED_CARD_TYPE = "entities";

function capitalize(word) {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

export function entityLabel(entity) {
  return entity.name || entity.original_name || entity.entity_id;
}

function byLabel(a, b) {
  return entityLabel(a).localeCompare(entityLabel(b));
}

/** An entities-card row with an explicit short name, overriding HA's default
 * has_entity_name-driven "{device name} {entity name}" friendly_name --
 * redundant once the device name is already the card/section heading. */
function toEntityRow(entity) {
  return { entity: entity.entity_id, name: entityLabel(entity) };
}

function entityDomain(entity) {
  return entity.entity_id.split(".", 1)[0];
}

/** A "tile" card for one entity -- icon + name + colored state/toggle, used
 * for Controls/Status instead of plain entities-card rows. */
function toTileCard(entity) {
  return { type: "tile", entity: entity.entity_id, name: entityLabel(entity) };
}

/** A titled grid of tile cards that reflows its column count to the
 * available width (see solarcharger-auto-grid-card.js), rather than a fixed
 * column count. */
function buildTileGrid(title, entities) {
  return {
    type: "custom:solarcharger-auto-grid-card",
    title,
    cards: entities.map(toTileCard),
  };
}

/** Build a device_id -> [entity registry entries] map from hass.entities. */
export function groupEntitiesByDevice(hass) {
  const entitiesByDevice = new Map();
  for (const entity of Object.values(hass.entities)) {
    if (!entity.device_id) continue;
    if (!entitiesByDevice.has(entity.device_id)) {
      entitiesByDevice.set(entity.device_id, []);
    }
    entitiesByDevice.get(entity.device_id).push(entity);
  }
  return entitiesByDevice;
}

/** Every HA device belonging to this integration, from hass.devices. */
export function getSolarchargerDevices(hass) {
  return Object.values(hass.devices).filter((device) =>
    device.identifiers.some(([domain]) => domain === SOLARCHARGER_DOMAIN)
  );
}

/** Find a device by its current display name (name_by_user || name).
 * Device registry IDs are opaque, HA-generated strings that change if a
 * device is ever deleted and recreated (eg. removing and re-adding a
 * charger) -- the display name is what a user actually controls and would
 * re-enter consistently, so the charger card persists that instead of a
 * device_id. */
export function findDeviceByName(hass, name) {
  if (!name) return undefined;
  return Object.values(hass.devices).find((device) => (device.name_by_user || device.name) === name);
}

/** Is this device a real charger (has a charge switch), not the Global Defaults device? */
export function isChargerDevice(device, entitiesByDevice) {
  const entities = entitiesByDevice.get(device.id) || [];
  return entities.some(
    (e) => entityDomain(e) === "switch" && e.translation_key === "charge"
  );
}

/** Every real charger device (Global Defaults excluded), sorted by name. */
export function getChargerDevices(hass) {
  const entitiesByDevice = groupEntitiesByDevice(hass);
  return getSolarchargerDevices(hass)
    .filter((device) => isChargerDevice(device, entitiesByDevice))
    .sort((a, b) => (a.name_by_user || a.name).localeCompare(b.name_by_user || b.name));
}

/** Split one device's entities into the weekly schedule rows plus the four card buckets. */
function groupDeviceEntities(entities) {
  const byTranslationKey = new Map(entities.map((e) => [e.translation_key, e]));
  const scheduleRows = [];
  const scheduleEntityIds = new Set();

  for (const day of WEEKDAYS) {
    const limit = byTranslationKey.get(`charge_limit_${day}`);
    const endtime = byTranslationKey.get(`charge_endtime_${day}`);
    const defaultLimit = byTranslationKey.get(`default_charge_limit_${day}`);
    if (!limit && !endtime && !defaultLimit) continue;

    scheduleRows.push({
      day: capitalize(day),
      limitEntityId: limit ? limit.entity_id : null,
      endtimeEntityId: endtime ? endtime.entity_id : null,
      defaultLimitEntityId: defaultLimit ? defaultLimit.entity_id : null,
    });
    if (limit) scheduleEntityIds.add(limit.entity_id);
    if (endtime) scheduleEntityIds.add(endtime.entity_id);
    if (defaultLimit) scheduleEntityIds.add(defaultLimit.entity_id);
  }

  const resetButton = entities.find(
    (e) => e.translation_key === RESET_CHARGE_LIMIT_TRANSLATION_KEY
  );
  const scheduleExtras = SCHEDULE_EXTRA_TRANSLATION_KEYS.map((key) =>
    byTranslationKey.get(key)
  ).filter(Boolean);
  const scheduleExtraIds = new Set(scheduleExtras.map((e) => e.entity_id));
  const rest = entities.filter(
    (e) =>
      !scheduleEntityIds.has(e.entity_id) &&
      e !== resetButton &&
      !scheduleExtraIds.has(e.entity_id)
  );
  const isStatusDomain = (e) => ["sensor", "datetime"].includes(entityDomain(e));

  const controls = rest
    .filter((e) => !e.entity_category && !isStatusDomain(e))
    .sort(byLabel);
  const sensors = rest.filter((e) => !e.entity_category && isStatusDomain(e)).sort(byLabel);
  const diagnostic = rest.filter((e) => e.entity_category === "diagnostic").sort(byLabel);
  const advanced = rest.filter((e) => e.entity_category === "config").sort(byLabel);

  return {
    scheduleRows,
    resetButton,
    scheduleExtras,
    controls,
    sensors,
    diagnostic,
    advanced,
  };
}

/** Prefix a section's own title with the device name, for whichever card ends
 * up first in a host card -- eg. "Controls" becomes "tesla_custom Tesla23m3
 * Controls" so the device name and the section title share one line/header
 * instead of a separate heading line above it. `prefix` is only truthy for
 * the very first card a host actually renders (see buildDeviceCard below);
 * every other card keeps its own plain title (or null) unchanged. */
function withHeadingPrefix(prefix, title) {
  if (!prefix) return title ?? null;
  return title ? `${prefix} ${title}` : prefix;
}

/** Shape the Configuration card correctly for a container type (expander-card)
 * vs. the plain built-in "grid" card, which has no concept of a collapsible title. */
function buildAdvancedCard(advancedEntities, title) {
  if (ADVANCED_CARD_TYPE === "entities") {
    return buildTileGrid(title, advancedEntities);
  }

  return {
    type: ADVANCED_CARD_TYPE,
    title,
    expanded: false,
    cards: [buildTileGrid(null, advancedEntities)],
  };
}

/** Controls + Sensors tile grids -- mirrors HA's own native device-page
 * grouping (split by entity_category, then domain). Sensors has no title of
 * its own, the same way the Charge schedule badges don't -- it reads as more
 * tiles under the "Controls" heading rather than a second titled section. */
function buildControlsSensorsSection(grouped, headingPrefix) {
  const cards = [];
  if (grouped.controls.length) {
    cards.push(buildTileGrid(withHeadingPrefix(headingPrefix, "Controls"), grouped.controls));
    headingPrefix = null;
  }
  if (grouped.sensors.length) {
    cards.push(buildTileGrid(withHeadingPrefix(headingPrefix, null), grouped.sensors));
  }
  return cards;
}

/** Diagnostic tile grid -- mirrors HA's own native device-page grouping. */
function buildDiagnosticSection(grouped, headingPrefix) {
  return grouped.diagnostic.length
    ? [buildTileGrid(withHeadingPrefix(headingPrefix, "Diagnostic"), grouped.diagnostic)]
    : [];
}

/** The weekly schedule table plus the schedule-adjacent toggle/selector tiles
 * shown directly underneath it. Has no native HA device-page equivalent, so
 * it's built from scratch rather than mirrored. */
function buildScheduleSection(grouped, headingPrefix) {
  const cards = [];
  if (grouped.scheduleRows.length) {
    cards.push({
      type: "entities",
      title: withHeadingPrefix(headingPrefix, "Charge schedule"),
      show_header_toggle: false,
      // A built-in card's header has no CSS custom property for its own
      // background or padding (unlike --ha-card-header-font-size, which
      // solarcharger-section-card-base.js sets directly) -- highlighting
      // just the header row, and shrinking its padding/line-height down to
      // the same height as the other section titles, needs card_mod (HACS).
      // Harmless if card_mod isn't installed: an unrecognized config key is
      // just ignored. Keep this in sync by hand with
      // solarcharger-auto-grid-card.js's own h1 (background, padding), used
      // for the other section titles.
      card_mod: {
        style: `
          .card-header {
            background-color: rgba(var(--rgb-primary-color), 0.15);
            border-radius: var(--ha-border-radius-sm, 4px) var(--ha-border-radius-sm, 4px) 0 0;
            padding: 4px 8px;
            line-height: normal;
          }
        `,
      },
      entities: [
        { type: "custom:solarcharger-schedule-row", header: true },
        ...grouped.scheduleRows.map((row) => ({
          type: "custom:solarcharger-schedule-row",
          day: row.day,
          limit_entity: row.limitEntityId,
          endtime_entity: row.endtimeEntityId,
          default_limit_entity: row.defaultLimitEntityId,
        })),
        ...(grouped.resetButton ? [toEntityRow(grouped.resetButton)] : []),
      ],
    });
    headingPrefix = null;
  }
  if (grouped.scheduleExtras.length) {
    cards.push(buildTileGrid(withHeadingPrefix(headingPrefix, null), grouped.scheduleExtras));
  }
  return cards;
}

/** The Configuration card. */
function buildConfigurationSection(grouped, headingPrefix) {
  return grouped.advanced.length
    ? [buildAdvancedCard(grouped.advanced, withHeadingPrefix(headingPrefix, "Configuration"))]
    : [];
}

/** Stack whichever section(s) `sections` produce, as a single
 * full-width-stacked "grid" card, with the device name merged into the
 * first section's own title rather than shown as a separate heading line
 * above it (see withHeadingPrefix()). If a device happens to have nothing
 * in its first section(s) (eg. no Controls or Sensors entities at all), the
 * device name attaches to whichever section actually ends up first instead
 * of being silently dropped. Shared by the full combined card and each
 * smaller per-section card -- see solarcharger-section-card-base.js. */
function buildDeviceCard(device, entities, sections) {
  const grouped = groupDeviceEntities(entities);
  let headingPrefix = device.name_by_user || device.name;
  const cards = [];
  for (const buildSection of sections) {
    const sectionCards = buildSection(grouped, headingPrefix);
    if (sectionCards.length) {
      cards.push(...sectionCards);
      headingPrefix = null;
    }
  }

  // columns: 1 + square: false stacks the sub-cards full-width vertically --
  // without them, "grid" defaults to multiple square-forced columns, which
  // squishes everything into tiny boxes both here and inside the nested
  // tile/schedule grids above.
  return { type: "grid", columns: 1, square: false, cards };
}

/** Build the full Controls/Sensors/Diagnostic/Schedule/Configuration card config
 * for one device -- used by both the whole-view strategy and
 * solarcharger-charger-card (the single "everything in one card" card). */
export function buildChargerSection(device, entities) {
  return buildDeviceCard(device, entities, [
    buildControlsSensorsSection,
    buildDiagnosticSection,
    buildScheduleSection,
    buildConfigurationSection,
  ]);
}

/** Just the Controls + Sensors card for one device, for solarcharger-controls-sensors-card. */
export function buildControlsSensorsCard(device, entities) {
  return buildDeviceCard(device, entities, [buildControlsSensorsSection]);
}

/** Just the Diagnostic card for one device, for solarcharger-diagnostic-card. */
export function buildDiagnosticCard(device, entities) {
  return buildDeviceCard(device, entities, [buildDiagnosticSection]);
}

/** Just the Charge schedule card (+ the badges underneath it) for one device,
 * for solarcharger-schedule-card. */
export function buildScheduleCard(device, entities) {
  return buildDeviceCard(device, entities, [buildScheduleSection]);
}

/** Just the Configuration card for one device, for solarcharger-configuration-card. */
export function buildConfigurationCard(device, entities) {
  return buildDeviceCard(device, entities, [buildConfigurationSection]);
}
