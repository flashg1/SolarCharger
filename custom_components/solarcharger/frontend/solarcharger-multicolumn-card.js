/**
 * Custom Lovelace card: hosts a set of child cards (the device's
 * Controls+Sensors / Diagnostic / Charge schedule / Configuration sections,
 * built by buildDeviceCard() in solarcharger-shared.js) in a CSS
 * multi-column layout that reflows how many columns fit to the available
 * width, instead of always stacking every section full-width, one per row.
 *
 * There's no built-in card for this. hui-grid-card only supports a fixed
 * `columns` value (see solarcharger-auto-grid-card.js's header comment for
 * the same limitation), which is exactly why buildDeviceCard() previously
 * forced it to `columns: 1` -- a fixed grid has no notion of "pack these
 * variable-height sections as tightly as they'll fit," it only knows a fixed
 * number of equal-width cells. CSS multi-column layout (`column-width`)
 * gets genuine width-driven reflow without any of our own height
 * measurement: the browser lays child sections down one column at a time,
 * top to bottom, wrapping to the next column as needed, and (via the
 * default `column-fill: balance`) picks whichever column split minimizes
 * the tallest column -- so eg. two short sections can end up sharing one
 * column while one much taller section keeps a column to itself.
 *
 * `break-inside: avoid-column` on each child wrapper is required -- without
 * it, a section that doesn't fully fit in the remaining space of a column
 * would be cut across the column boundary instead of moving whole to the
 * next one.
 */

const MIN_COLUMN_WIDTH = "320px";

class SolarchargerMulticolumnCard extends HTMLElement {
  connectedCallback() {
    this.style.display = "block";
  }

  setConfig(config) {
    if (!config || !Array.isArray(config.cards)) {
      throw new Error("solarcharger-multicolumn-card: cards array is required");
    }
    this._config = config;
    this._lastCardConfigsKey = null; // force a rebuild of the hosted sections
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

    const serialized = JSON.stringify(this._config.cards);
    if (serialized !== this._lastCardConfigsKey) {
      const helpers = await window.loadCardHelpers();
      this._cards = this._config.cards.map((cardConfig) => helpers.createCardElement(cardConfig));

      if (!this.shadowRoot) {
        this.attachShadow({ mode: "open" });
        this.shadowRoot.innerHTML = `
          <style>
            .columns {
              column-width: ${MIN_COLUMN_WIDTH};
              column-gap: 8px;
            }
            /* column-gap only spaces columns apart, not items stacked
               within the same column -- this margin is the multi-column
               equivalent of solarcharger-auto-grid-card's grid gap. */
            .columns > div {
              break-inside: avoid-column;
              margin-bottom: 8px;
            }
          </style>
          <div class="columns"></div>
        `;
      }

      const container = this.shadowRoot.querySelector(".columns");
      container.innerHTML = "";
      for (const card of this._cards) {
        const wrapper = document.createElement("div");
        wrapper.appendChild(card);
        container.appendChild(wrapper);
      }
      this._lastCardConfigsKey = serialized;
    }

    for (const card of this._cards) {
      card.hass = this._hass;
    }
  }

  // No fixed column count to sum sizes by row (unlike hui-grid-card's own
  // getCardSize) -- this sums every section's own size, ie. the height if
  // they all ended up stacked in one column, as a safe upper-bound estimate
  // for the outer masonry view's packing.
  async getCardSize() {
    if (!this._cards) return 1;
    const sizes = await Promise.all(this._cards.map((card) => card.getCardSize?.() ?? 1));
    return sizes.reduce((total, size) => total + size, 0);
  }

  getGridOptions() {
    return { columns: "full", rows: "auto" };
  }
}

customElements.define("solarcharger-multicolumn-card", SolarchargerMulticolumnCard);
