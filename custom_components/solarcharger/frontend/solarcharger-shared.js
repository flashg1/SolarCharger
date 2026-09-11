/**
 * Shared grouping/rendering logic for the SolarCharger Lovelace view strategy
 * (solarcharger-strategy.js) and the single-device card
 * (solarcharger-charger-card.js). Both need to turn one device's entities
 * into the same Schedule/Controls/Status/Advanced-settings card layout, so
 * that logic lives here once rather than being kept in sync in two places.
 *
 * See solarcharger-strategy.js's header comment for the full design
 * rationale (translation_key / entity_category signals, why Global Defaults
 * is excluded, etc.) -- this file is the implementation, that one documents
 * the "why".
 */

export const SOLARCHARGER_DOMAIN = "solarcharger";

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
  const limitRows = [];
  const endtimeRows = [];
  const scheduleEntityIds = new Set();

  for (const day of WEEKDAYS) {
    const limit = byTranslationKey.get(`charge_limit_${day}`);
    const endtime = byTranslationKey.get(`charge_endtime_${day}`);
    if (limit) {
      limitRows.push({ entity: limit.entity_id, name: capitalize(day) });
      scheduleEntityIds.add(limit.entity_id);
    }
    if (endtime) {
      endtimeRows.push({ entity: endtime.entity_id, name: capitalize(day) });
      scheduleEntityIds.add(endtime.entity_id);
    }
  }

  const rest = entities.filter((e) => !scheduleEntityIds.has(e.entity_id));
  const isStatusDomain = (e) => ["sensor", "datetime"].includes(entityDomain(e));

  const controls = rest
    .filter((e) => !e.entity_category && !isStatusDomain(e))
    .sort(byLabel);
  const statusPrimary = rest.filter((e) => !e.entity_category && isStatusDomain(e));
  const statusDiagnostic = rest.filter((e) => e.entity_category === "diagnostic");
  const status = [...statusPrimary, ...statusDiagnostic].sort(byLabel);
  const advanced = rest.filter((e) => e.entity_category === "config").sort(byLabel);

  return { limitRows, endtimeRows, controls, status, advanced };
}

/** Shape the Advanced settings card correctly for a container type (expander-card)
 * vs. the plain built-in "entities" card, which has no concept of child cards. */
function buildAdvancedCard(advancedEntities) {
  const entitiesCard = {
    type: "entities",
    entities: advancedEntities.map(toEntityRow),
  };

  if (ADVANCED_CARD_TYPE === "entities") {
    return { ...entitiesCard, title: "Advanced settings" };
  }

  return {
    type: ADVANCED_CARD_TYPE,
    title: "Advanced settings",
    expanded: false,
    cards: [entitiesCard],
  };
}

/** Build the full Schedule/Controls/Status/Advanced-settings card config for one device. */
export function buildChargerSection(device, entities) {
  const { limitRows, endtimeRows, controls, status, advanced } =
    groupDeviceEntities(entities);

  const cards = [{ type: "heading", heading: device.name_by_user || device.name }];

  if (controls.length) {
    cards.push(buildTileGrid("Controls", controls, 4));
  }

  if (limitRows.length || endtimeRows.length) {
    cards.push({
      type: "grid",
      columns: 2,
      square: false,
      title: "Charge schedule",
      cards: [
        { type: "entities", title: "Limit", entities: limitRows },
        { type: "entities", title: "End time", entities: endtimeRows },
      ],
    });
  }

  if (status.length) {
    cards.push(buildTileGrid("Status", status, 4));
  }

  if (advanced.length) {
    cards.push(buildAdvancedCard(advanced));
  }

  // columns: 1 + square: false stacks the sub-cards (schedule/controls/status/
  // advanced) full-width vertically -- without them, "grid" defaults to
  // multiple square-forced columns, which squishes everything into tiny
  // boxes both here and inside the nested tile/schedule grids above.
  return { type: "grid", columns: 1, square: false, cards };
}
