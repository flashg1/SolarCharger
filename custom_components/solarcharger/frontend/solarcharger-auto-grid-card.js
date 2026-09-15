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
 *
 * `columns` in config is optional and lets a caller opt back into a fixed
 * column count instead: 0 (or omitted) keeps the auto-fit behaviour above,
 * a positive integer switches to a plain `repeat(N, 1fr)` -- see
 * solarcharger-shared.js, which is the only caller that ever sets it.
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
              padding: 4px 8px;
              /* Kept in sync by hand with the card_mod background on the
                 Charge schedule entities card in solarcharger-shared.js --
                 that one can't reach this same value via a plain CSS custom
                 property the way font-size does (there's no inherited
                 --ha-card-header-background var), so it's card_mod-only and
                 needs its own copy of this color. */
              background-color: rgba(var(--rgb-primary-color), 0.15);
              border-radius: var(--ha-border-radius-sm, 4px);
              color: var(--primary-text-color);
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
            }
            .grid {
              display: grid;
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

    // Not gated behind the `serialized` check above -- config.columns can
    // change on its own (eg. via the card editor) without the entity/tile
    // list changing, and this is cheap enough to just always re-apply.
    const grid = this.shadowRoot.querySelector(".grid");
    const columns = Number(this._config.columns) || 0;
    // minmax(0, 1fr), not a bare 1fr -- a grid track's automatic minimum size
    // otherwise defaults to its item's max-content size (eg. a tile's
    // unwrapped title text), so one long entity name would blow out its
    // whole column instead of staying equal-width and letting the tile's own
    // ellipsis/truncation handle the overflow. Same reasoning as hui-grid-card's
    // own `repeat(N, minmax(0, 1fr))`, noted in the file header above.
    grid.style.gridTemplateColumns =
      columns > 0 ? `repeat(${columns}, minmax(0, 1fr))` : `repeat(auto-fit, minmax(${MIN_TILE_WIDTH}, 1fr))`;

    for (const tile of this._tiles) {
      tile.hass = this._hass;
    }
  }

  getCardSize() {
    const columns = Number(this._config?.columns) || 3;
    const rows = Math.ceil((this._tiles?.length || 1) / columns);
    return rows + (this._config?.title ? 1 : 0);
  }
}

customElements.define("solarcharger-auto-grid-card", SolarchargerAutoGridCard);
