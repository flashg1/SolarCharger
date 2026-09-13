/**
 * Custom Lovelace card: a titled grid of child cards (tile cards, in this
 * project) that reflows its column count to the available width via plain
 * CSS `repeat(auto-fit, minmax(...))`, instead of a fixed count.
 *
 * The built-in "grid" card (hui-grid-card) only supports a fixed `columns`
 * value from config (or a hardcoded default) -- its own CSS is
 * `repeat(var(--grid-card-column-count, N), minmax(0, 1fr))`. Even setting
 * that custom property to the "auto-fit" keyword from the outside wouldn't
 * help, since the minimum track size is hardcoded to 0 -- there's no real
 * minimum width for auto-fit to reflow around, so it would just render as a
 * single column. Overriding a built-in card's internal CSS to fix that would
 * need card_mod (HACS); this card sidesteps that dependency by hosting its
 * child cards in a genuinely responsive grid of its own instead of
 * delegating to hui-grid-card at all.
 */

const MIN_TILE_WIDTH = "140px";

class SolarchargerAutoGridCard extends HTMLElement {
  connectedCallback() {
    this.style.display = "block";
  }

  setConfig(config) {
    if (!config || !Array.isArray(config.cards)) {
      throw new Error("solarcharger-auto-grid-card: cards array is required");
    }
    this._config = config;
    this._lastCardConfigsKey = null; // force a rebuild of the hosted tiles
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
      this._tiles = this._config.cards.map((cardConfig) =>
        helpers.createCardElement(cardConfig)
      );

      if (!this.shadowRoot) {
        this.attachShadow({ mode: "open" });
        this.shadowRoot.innerHTML = `
          <style>
            h1 {
              font-size: 1.5rem;
              font-weight: 400;
              margin: 0 0 8px 0;
              color: var(--primary-text-color);
            }
            .grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(${MIN_TILE_WIDTH}, 1fr));
              gap: 8px;
            }
          </style>
          <h1 hidden></h1>
          <div class="grid"></div>
        `;
      }

      const grid = this.shadowRoot.querySelector(".grid");
      grid.innerHTML = "";
      this._tiles.forEach((tile) => grid.appendChild(tile));
      this._lastCardConfigsKey = serialized;
    }

    const heading = this.shadowRoot.querySelector("h1");
    heading.textContent = this._config.title || "";
    heading.hidden = !this._config.title;

    for (const tile of this._tiles) {
      tile.hass = this._hass;
    }
  }

  getCardSize() {
    const rows = Math.ceil((this._tiles?.length || 1) / 3);
    return rows + (this._config?.title ? 1 : 0);
  }
}

customElements.define("solarcharger-auto-grid-card", SolarchargerAutoGridCard);
