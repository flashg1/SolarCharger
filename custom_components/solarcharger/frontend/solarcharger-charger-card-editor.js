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
 * Loaded lazily by SolarchargerChargerCard.getConfigElement() only when the
 * user opens the card's edit dialog.
 */

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
        // ha-form's value-changed carries the full, merged form data object
        // in detail.value, not just the field that changed.
        const newConfig = ev.detail.value;
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

    this._form.hass = this._hass;
    this._form.schema = SCHEMA;
    this._form.data = this._config;
  }
}

customElements.define(
  "solarcharger-charger-card-editor",
  SolarchargerChargerCardEditor
);
