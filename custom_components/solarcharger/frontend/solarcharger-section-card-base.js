/**
 * Shared "thin host" custom-element implementation for every per-device
 * SolarCharger Lovelace card -- solarcharger-charger-card.js (Controls +
 * Sensors + Diagnostic + Schedule + Configuration, all in one) and the
 * smaller solarcharger-controls-sensors-card.js / -diagnostic-card.js /
 * -schedule-card.js / -configuration-card.js. They only differ in which
 * section(s) of a device's entities they turn into a card config -- see
 * solarcharger-shared.js -- so that one difference is injected here as
 * `buildCardConfig`, and everything else (device lookup, hosting a real
 * built-in "grid" card via HA's card-helpers, the config editor, GUI-picker
 * registration) lives in one place rather than five near-identical copies.
 */

import { findDeviceByName, getChargerDevices, groupEntitiesByDevice } from "./solarcharger-shared.js";

export function defineSectionCard({ tagName, buildCardConfig, name, description }) {
  class SolarchargerSectionCard extends HTMLElement {
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
      const editor = document.createElement("solarcharger-charger-card-editor");
      // Lets the editor preview this specific card's default title (see
      // firstCardTitle() in solarcharger-shared.js) as its title field's
      // placeholder -- each of the five cards computes a different one.
      editor.buildCardConfig = buildCardConfig;
      return editor;
    }

    static getStubConfig(hass) {
      const [firstCharger] = getChargerDevices(hass);
      return { device_name: firstCharger ? firstCharger.name_by_user || firstCharger.name : "" };
    }

    setConfig(config) {
      if (!config || !(config.device_name || config.device_id)) {
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

      // device_name is the persisted, stable identifier (see findDeviceByName's
      // doc comment in solarcharger-shared.js); device_id is only read as a
      // fallback for cards saved before this switch, since registry IDs aren't
      // stable across a delete+recreate of the device.
      const device = this._config.device_name
        ? findDeviceByName(this._hass, this._config.device_name)
        : this._hass.devices[this._config.device_id];
      if (!device) {
        const identifier = this._config.device_name || this._config.device_id;
        this._renderMessage(`Charger device not found: ${identifier}`);
        return;
      }

      const entitiesByDevice = groupEntitiesByDevice(this._hass);
      const cardConfig = buildCardConfig(
        device,
        entitiesByDevice.get(device.id) || [],
        this._config.title,
        this._config.columns
      );

      // buildCardConfig() only embeds entity_ids/names, not live state, so
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

  customElements.define(tagName, SolarchargerSectionCard);

  window.customCards = window.customCards || [];
  // false: the live-rendered preview (an actual instance of the hosted
  // grid/entities card) is much taller than the built-in cards' previews,
  // making the picker awkward to scroll -- plain description text matches
  // how cards like Grid/Horizontal stack/Humidifier present themselves.
  window.customCards.push({ type: tagName, name, description, preview: false });
}
