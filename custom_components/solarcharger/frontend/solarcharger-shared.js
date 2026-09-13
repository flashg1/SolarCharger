/**
 * Shared grouping/rendering logic for the SolarCharger Lovelace view strategy
 * (solarcharger-strategy.js) and the single-device card
 * (solarcharger-charger-card.js). Both need to turn one device's entities
 * into the same Controls/Sensors/Diagnostic/Schedule/Advanced-settings card
 * layout, so that logic lives here once rather than being kept in sync in
 * two places.
 *
 * See solarcharger-strategy.js's header comment for the full design
 * rationale (translation_key / entity_category signals, why Global Defaults
 * is excluded, etc.) -- this file is the implementation, that one documents
 * the "why".
 */

import "./solarcharger-schedule-row.js";

export const SOLARCHARGER_DOMAIN = "solarcharger";

const RESET_CHARGE_LIMIT_TRANSLATION_KEY = "reset_charge_limit_and_time";

export const WEEKDAYS = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

// "custom:expander-card" (HACS) collapses the Advanced settings section by
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

/** A titled grid of tile cards. square: false lets tiles keep their natural
 * (non-square) chip shape instead of being forced into square boxes. */
function buildTileGrid(title, entities, columns = 2) {
  return {
    type: "grid",
    title,
    columns,
    square: false,
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
  const rest = entities.filter(
    (e) => !scheduleEntityIds.has(e.entity_id) && e !== resetButton
  );
  const isStatusDomain = (e) => ["sensor", "datetime"].includes(entityDomain(e));

  const controls = rest
    .filter((e) => !e.entity_category && !isStatusDomain(e))
    .sort(byLabel);
  const sensors = rest.filter((e) => !e.entity_category && isStatusDomain(e)).sort(byLabel);
  const diagnostic = rest.filter((e) => e.entity_category === "diagnostic").sort(byLabel);
  const advanced = rest.filter((e) => e.entity_category === "config").sort(byLabel);

  return { scheduleRows, resetButton, controls, sensors, diagnostic, advanced };
}

/** Shape the Advanced settings card correctly for a container type (expander-card)
 * vs. the plain built-in "grid" card, which has no concept of a collapsible title. */
function buildAdvancedCard(advancedEntities) {
  if (ADVANCED_CARD_TYPE === "entities") {
    return buildTileGrid("Advanced settings", advancedEntities, 2);
  }

  return {
    type: ADVANCED_CARD_TYPE,
    title: "Advanced settings",
    expanded: false,
    cards: [buildTileGrid(null, advancedEntities, 2)],
  };
}

/** Build the full Controls/Sensors/Diagnostic/Schedule/Advanced-settings card config
 * for one device -- Controls/Sensors/Diagnostic mirror HA's own native device-page
 * grouping (split by entity_category, then domain); Charge schedule has no native
 * equivalent and is built separately below. */
export function buildChargerSection(device, entities) {
  const { scheduleRows, resetButton, controls, sensors, diagnostic, advanced } =
    groupDeviceEntities(entities);

  const cards = [{ type: "heading", heading: device.name_by_user || device.name }];

  if (controls.length) {
    cards.push(buildTileGrid("Controls", controls, 2));
  }

  if (sensors.length) {
    cards.push(buildTileGrid("Sensors", sensors, 2));
  }

  if (diagnostic.length) {
    cards.push(buildTileGrid("Diagnostic", diagnostic, 2));
  }

  if (scheduleRows.length) {
    cards.push({
      type: "entities",
      title: "Charge schedule",
      show_header_toggle: false,
      entities: [
        { type: "custom:solarcharger-schedule-row", header: true },
        ...scheduleRows.map((row) => ({
          type: "custom:solarcharger-schedule-row",
          day: row.day,
          limit_entity: row.limitEntityId,
          endtime_entity: row.endtimeEntityId,
          default_limit_entity: row.defaultLimitEntityId,
        })),
        ...(resetButton ? [toEntityRow(resetButton)] : []),
      ],
    });
  }

  if (advanced.length) {
    cards.push(buildAdvancedCard(advanced));
  }

  // columns: 1 + square: false stacks the sub-cards (controls/sensors/diagnostic/
  // advanced) full-width vertically -- without them, "grid" defaults to
  // multiple square-forced columns, which squishes everything into tiny
  // boxes both here and inside the nested tile/schedule grids above.
  return { type: "grid", columns: 1, square: false, cards };
}
