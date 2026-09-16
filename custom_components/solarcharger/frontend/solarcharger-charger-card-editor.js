/**
 * Visual config editor shared by every per-device SolarCharger custom card
 * (solarcharger-charger-card and the smaller solarcharger-controls-sensors-card
 * / -diagnostic-card / -schedule-card / -configuration-card) -- they all take
 * the same config shape (a device, plus an optional custom title and tile-grid
 * column count), so one editor covers all of them; see
 * solarcharger-section-card-base.js's getConfigElement().
 *
 * Uses <ha-form> with a declarative "device" selector schema -- the same
 * foundational, universally-loaded building block HA's own built-in card
 * editors use for pickers -- instead of manually creating and wiring a raw
 * <ha-device-picker> element. The manual approach rendered nothing visible;
 * the leading theory is that ha-device-picker's own implementation chunk
 * hadn't been lazy-loaded into the page yet and nothing else forced it to,
 * leaving an un-upgraded, contentless placeholder element. ha-form and its
 * selectors are used so pervasively throughout the rest of HA's UI that
 * they're far more likely to already be loaded by the time this runs.
 *
 * Known limitation: a device selector's filter is a declarative, serializable
 * schema, not a JS callback, so it can only filter by integration -- it can't
 * express the exact "has a translation_key=charge switch" rule
 * solarcharger-shared.js's isChargerDevice() uses everywhere else. The
 * "Global defaults" pseudo-device will therefore also appear as a pickable
 * (if not really meaningful) option here.
 *
 * The device selector only understands device_id, so the form's own working
 * field is called that -- but a device's registry ID is an opaque string
 * that changes if the device is ever deleted and recreated (eg. removing and
 * re-adding a charger). What actually gets persisted to the card's config is
 * device_name (see findDeviceByName() in solarcharger-shared.js), converted
 * to/from device_id right here at the form boundary, so a saved card survives
 * that kind of recreation as long as the device keeps the same display name.
 *
 * The title field is seeded with the title this specific card would use by
 * default (eg. "custom Hot water Configuration") -- computed by actually
 * running this card's buildCardConfig (set on the editor instance by
 * getConfigElement() in solarcharger-section-card-base.js, since it differs
 * per card) and pulling the heading back out via firstCardTitle(). This is
 * a real, editable starting *value*, not a placeholder shown over an empty
 * field -- an ha-form text selector with only a schema `default` (no real
 * value) turned out to render as effectively uneditable in practice, while
 * a field seeded with a real value behaves completely normally, so this
 * sidesteps that rather than chasing it further. It's still non-destructive:
 * setting .value on the underlying <input> doesn't itself fire a
 * "value-changed" event, so leaving it untouched and saving still persists
 * no `title` at all. The tricky part is that ha-form's value-changed event
 * can't tell "the user typed this" apart from "this is just the seeded
 * default still sitting in the box" -- both look like the same string coming
 * back in ev.detail.value. That distinction matters when the device changes:
 * without it, the previous device's default title gets misread as a real
 * user override and permanently locked into the config, so every later
 * device pick keeps showing that same stale title instead of its own. See
 * _syncConfig() and the value-changed handler below, which compare the
 * incoming title against this._lastDefaultTitle (the default seeded for the
 * previously-selected device) to tell the two apart.
 *
 * Loaded lazily by getConfigElement() only when the user opens a card's edit
 * dialog.
 */

import { DEFAULT_TILE_COLUMNS, findDeviceByName, firstCardTitle, groupEntitiesByDevice } from "./solarcharger-shared.js";

const SCHEMA = [
  {
    name: "device_id",
    required: true,
    selector: {
      device: {
        filter: { integration: "solarcharger" },
      },
    },
  },
  {
    name: "title",
    selector: { text: {} },
  },
  {
    name: "columns",
    selector: { number: { min: 0, max: 12, mode: "box" } },
  },
];

function computeLabel(schemaEntry) {
  if (schemaEntry.name === "device_id") return "Charger device";
  if (schemaEntry.name === "title") return "Title (optional, overrides the default)";
  if (schemaEntry.name === "columns") return "Columns (0 = fit to available width)";
  return schemaEntry.name;
}

class SolarchargerChargerCardEditor extends HTMLElement {
  // HA's card-config dialog doesn't guarantee setConfig() runs before the
  // hass property is first set on the editor -- initialize _config up front
  // so _syncConfig() never reads .device_id off undefined either way.
  _config = {};

  setConfig(config) {
    this._config = config || {};
    this._ensureForm();
    if (this._hass) {
      this._syncConfig();
    }
  }

  // hass is reassigned on essentially every hass state change (anything,
  // anywhere in the system, not just this integration) -- multiple times a
  // second while a charger is actively reporting live power/current. Only
  // forward it to the form here; do NOT also recompute/reassign .data or
  // .schema on every one of those ticks, or the title field's underlying
  // <input> gets its value/selectors force-refreshed out from under the
  // user's cursor constantly, making it effectively impossible to type into
  // (this is what the placeholder-flicker bug reported after adding the
  // title field turned out to be -- see _syncConfig()).
  set hass(hass) {
    this._hass = hass;
    this._ensureForm();
    this._form.hass = hass;
    if (!this._configSynced) {
      this._syncConfig();
    }
  }

  get hass() {
    return this._hass;
  }

  _ensureForm() {
    if (this._form) return;

    this._form = document.createElement("ha-form");
    this._form.computeLabel = computeLabel;
    this._form.addEventListener("value-changed", (ev) => {
      ev.stopPropagation();
      const { device_id: deviceId, title, columns } = ev.detail.value;
      const device = this._hass.devices[deviceId];
      // Merge into the existing config (preserving "type" and anything else
      // the dialog already put there) rather than replacing it outright --
      // _form.data below deliberately only carries device_id/title/columns
      // (the fields our schema manages), so ha-form's echoed value doesn't
      // include "type", and building newConfig from scratch would silently
      // drop it. Persist the device's current display name, not its
      // registry ID -- see the file header comment for why.
      const newConfig = { ...this._config, device_name: device ? device.name_by_user || device.name : "" };
      delete newConfig.device_id;
      // A title equal to the previously-seeded default means the user never
      // touched the field -- it's just the old device's default text still
      // sitting in the box, not an intentional override. Only persist it if
      // it actually differs from that.
      if (title && title !== this._lastDefaultTitle) {
        newConfig.title = title;
      } else {
        delete newConfig.title;
      }
      newConfig.columns = Number(columns) || 0;
      this._config = newConfig;
      // Standard Lovelace card-editor contract: bubble the edited config up
      // to the card-config dialog via a "config-changed" event.
      this.dispatchEvent(
        new CustomEvent("config-changed", {
          detail: { config: newConfig },
          bubbles: true,
          composed: true,
        })
      );
      // Only re-sync the form's own data/schema (which recomputes the
      // title's default value) when the device actually changed -- doing it
      // on every keystroke of the title field itself would fight the user's
      // typing/cursor position for no benefit, since ha-form already
      // reflects what was just typed without our help.
      if (deviceId !== this._lastDeviceId) {
        this._syncConfig();
      }
    });
    this.appendChild(this._form);
  }

  /** (Re)compute and push this._config down into the form's data/schema --
   * called on setConfig(), on hass first becoming available, and after a
   * device change (see _ensureForm()'s value-changed handler), never on a
   * plain hass tick. */
  _syncConfig() {
    this._configSynced = true;

    // The selector only understands device_id -- resolve our persisted
    // device_name (or a legacy device_id, for cards saved before this
    // switch) back to the current matching device just to seed the picker's
    // displayed selection.
    const selectedDevice = this._config.device_name
      ? findDeviceByName(this._hass, this._config.device_name)
      : this._config.device_id
        ? this._hass.devices[this._config.device_id]
        : undefined;
    this._lastDeviceId = selectedDevice ? selectedDevice.id : "";

    let defaultTitle = "";
    if (selectedDevice && this.buildCardConfig) {
      const entitiesByDevice = groupEntitiesByDevice(this._hass);
      const cardConfig = this.buildCardConfig(selectedDevice, entitiesByDevice.get(selectedDevice.id) || []);
      defaultTitle = firstCardTitle(cardConfig) || "";
    }
    this._lastDefaultTitle = defaultTitle;

    this._form.schema = SCHEMA;
    this._form.data = {
      device_id: selectedDevice ? selectedDevice.id : "",
      title: this._config.title || defaultTitle,
      columns: this._config.columns === undefined ? DEFAULT_TILE_COLUMNS : Number(this._config.columns) || 0,
    };
  }
}

customElements.define(
  "solarcharger-charger-card-editor",
  SolarchargerChargerCardEditor
);
