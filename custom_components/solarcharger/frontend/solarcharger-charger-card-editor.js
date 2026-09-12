/**
 * Visual config editor for the "solarcharger-charger-card" custom card.
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
 * Loaded lazily by SolarchargerChargerCard.getConfigElement() only when the
 * user opens the card's edit dialog.
 */

import { findDeviceByName } from "./solarcharger-shared.js";

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
];

function computeLabel(schemaEntry) {
  return schemaEntry.name === "device_id" ? "Charger device" : schemaEntry.name;
}

class SolarchargerChargerCardEditor extends HTMLElement {
  // HA's card-config dialog doesn't guarantee setConfig() runs before the
  // hass property is first set on the editor -- initialize _config up front
  // so _render() never reads .device_id off undefined either way.
  _config = {};

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  get hass() {
    return this._hass;
  }

  _render() {
    if (!this._hass) return;

    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = computeLabel;
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        const deviceId = ev.detail.value.device_id;
        const device = this._hass.devices[deviceId];
        // Merge into the existing config (preserving "type" and anything
        // else the dialog already put there) rather than replacing it
        // outright -- _form.data below deliberately only carries device_id
        // (the field our schema manages), so ha-form's echoed value doesn't
        // include "type", and building newConfig from scratch would silently
        // drop it. Persist the device's current display name, not its
        // registry ID -- see the file header comment for why.
        const newConfig = { ...this._config, device_name: device ? device.name_by_user || device.name : "" };
        delete newConfig.device_id;
        this._config = newConfig;
        // Standard Lovelace card-editor contract: bubble the edited config
        // up to the card-config dialog via a "config-changed" event.
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: newConfig },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }

    // The selector only understands device_id -- resolve our persisted
    // device_name (or a legacy device_id, for cards saved before this
    // switch) back to the current matching device just to seed the picker's
    // displayed selection.
    const selectedDevice = this._config.device_name
      ? findDeviceByName(this._hass, this._config.device_name)
      : this._config.device_id
        ? this._hass.devices[this._config.device_id]
        : undefined;

    this._form.hass = this._hass;
    this._form.schema = SCHEMA;
    this._form.data = { device_id: selectedDevice ? selectedDevice.id : "" };
  }
}

customElements.define(
  "solarcharger-charger-card-editor",
  SolarchargerChargerCardEditor
);
