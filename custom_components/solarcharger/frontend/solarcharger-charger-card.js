/**
 * Custom Lovelace card: one SolarCharger charger device, GUI-discoverable.
 *
 * Unlike solarcharger-strategy.js (a whole-view strategy, only addable via a
 * YAML hand-edit), this registers in window.customCards so it shows up
 * searchable in the standard "+ Add Card" picker -- a user finds it, picks
 * which charger device it's for via a dropdown (no YAML at all), and gets
 * the exact same Schedule/Controls/Status/Advanced-settings layout the
 * strategy builds, since both call buildChargerSection() from
 * solarcharger-shared.js.
 *
 * This card is a thin host: it doesn't render entity rows itself, it asks
 * HA's own card-helpers to build and host a real "grid" card (the same
 * built-in card type the strategy returns), the same technique community
 * meta-cards like auto-entities use internally.
 */

import {
  buildChargerSection,
  getChargerDevices,
  groupEntitiesByDevice,
} from "./solarcharger-shared.js";

class SolarchargerChargerCard extends HTMLElement {
  // Unknown custom elements default to display: inline (shrink-to-fit
  // content) with no CSS of our own to override it -- without this, the
  // card doesn't stretch to fill its grid/section cell, it just sits at
  // its natural content width, left-aligned within any extra space. Set
  // from connectedCallback(), not the constructor: the Custom Elements spec
  // forbids a constructor from adding attributes (style.display reflects to
  // the "style" attribute), and Chromium enforces this -- document.createElement()
  // throws "NotSupportedError: ... result must not have attributes" if it does.
  connectedCallback() {
    this.style.display = "block";
  }

  static async getConfigElement() {
    await import("./solarcharger-charger-card-editor.js");
    return document.createElement("solarcharger-charger-card-editor");
  }

  static getStubConfig(hass) {
    const [firstCharger] = getChargerDevices(hass);
    return { device_id: firstCharger ? firstCharger.id : "" };
  }

  setConfig(config) {
    if (!config || !config.device_id) {
      throw new Error("Please pick a charger device.");
    }
    this._config = config;
    this._lastSerializedCardConfig = null; // force a rebuild of the hosted card
    if (this._hass) {
      this._update();
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  get hass() {
    return this._hass;
  }

  async _update() {
    if (!this._config || !this._hass) return;

    const device = this._hass.devices[this._config.device_id];
    if (!device) {
      this._renderMessage(`Charger device not found: ${this._config.device_id}`);
      return;
    }

    const entitiesByDevice = groupEntitiesByDevice(this._hass);
    const cardConfig = buildChargerSection(device, entitiesByDevice.get(device.id) || []);

    // buildChargerSection() only embeds entity_ids/names, not live state, so
    // its output is stable across most hass updates -- only re-run setConfig
    // on the hosted card when the actual entity set/order changed, and just
    // refresh .hass (cheap, cards already optimize that internally) otherwise.
    const serialized = JSON.stringify(cardConfig);
    if (serialized !== this._lastSerializedCardConfig) {
      if (!this._hostedCard) {
        const helpers = await window.loadCardHelpers();
        this._hostedCard = helpers.createCardElement(cardConfig);
        this.innerHTML = "";
        this.appendChild(this._hostedCard);
      } else {
        this._hostedCard.setConfig(cardConfig);
      }
      this._lastSerializedCardConfig = serialized;
    }

    this._hostedCard.hass = this._hass;
  }

  _renderMessage(message) {
    this.innerHTML = "";
    const warning = document.createElement("hui-warning");
    warning.textContent = message;
    this.appendChild(warning);
  }

  getCardSize() {
    return this._hostedCard?.getCardSize ? this._hostedCard.getCardSize() : 8;
  }

  // Claim the full width of whatever section (sections view) or column
  // (masonry view) holds this card -- it doesn't grow the section itself
  // relative to the rest of the screen, that's controlled by the section's
  // own width/column_span, adjustable in dashboard edit mode.
  getGridOptions() {
    return { columns: "full", min_columns: 6, rows: "auto" };
  }
}

customElements.define("solarcharger-charger-card", SolarchargerChargerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "solarcharger-charger-card",
  name: "SolarCharger Charger",
  description: "Controls and status for one SolarCharger charger device.",
  preview: true,
});
