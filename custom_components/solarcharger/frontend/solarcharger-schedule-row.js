/**
 * Custom Lovelace row: one weekday's charge-limit %, charge-endtime and
 * default charge-limit %, shown as a single compact row (day / limit / end
 * time / default) instead of separate rows split across side-by-side
 * "entities" cards -- avoids those cards drifting out of vertical alignment
 * with each other (a time selector's row is intrinsically taller than a
 * number selector's row).
 *
 * Read-only by design: tapping a value opens HA's standard more-info dialog
 * for that entity (the "hass-more-info" event, the same convention any
 * entity row uses), rather than editing inline -- reuses HA's own tested
 * more-info UI instead of hand-building two-way-bound input widgets here.
 *
 * Used as a `type: "custom:solarcharger-schedule-row"` entry in an
 * "entities" card's `entities:` array. Entities cards create rows via the
 * same generic create-element pipeline used for cards (createRowElement(),
 * alongside createCardElement()) -- verified from the compiled frontend
 * source, not assumed.
 *
 * A `header: true` config renders the same row shape as a plain column-label
 * row ("Limit" / "End time" / "Default") instead of a day's data -- used as
 * the first entity in the list to label the value columns.
 */

function formatTime(stateValue) {
  const match = /^(\d{1,2}):(\d{2})/.exec(stateValue || "");
  if (!match) return stateValue;
  let hours = parseInt(match[1], 10);
  const minutes = match[2];
  const period = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  return `${hours}:${minutes} ${period}`;
}

class SolarchargerScheduleRow extends HTMLElement {
  connectedCallback() {
    this.style.display = "block";
  }

  setConfig(config) {
    if (!config || (!config.header && !config.day)) {
      throw new Error("solarcharger-schedule-row: day is required (unless header: true)");
    }
    this._config = config;

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `
        <style>
          /* Grid, not flex: each row is a separate custom element with its
             own isolated shadow DOM, so there's no shared table/column
             context between them. Flexbox's column widths are influenced by
             each row's own content (rounding differs row-to-row even with
             matching flex-basis values); a grid's track sizes come purely
             from the column definition below, identical in every row and
             the header, so columns are guaranteed to line up exactly.
             Track sizes use rem, not em: .row.header below sets its own
             font-size, and em (unlike rem) resolves against the font-size of
             the element it's used on -- since that's this same .row, the
             header's tracks would silently render 15% narrower than a data
             row's, throwing off every column boundary except the last. */
          .row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 3.5rem 5.5rem 3.5rem;
            align-items: center;
            padding: 8px 16px;
            gap: 16px;
          }
          .row.header { color: var(--secondary-text-color); font-weight: 500; font-size: 0.85em; padding-top: 4px; padding-bottom: 4px; }
          /* overflow/ellipsis fits the longest day name ("Wednesday") in a
             narrow card without it overflowing into the Limit column. */
          .day {
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            color: var(--primary-text-color);
          }
          .row.header .day { color: inherit; }
          .value { color: var(--primary-text-color); text-align: end; }
          .row.header .value { color: inherit; }
          .value.clickable { cursor: pointer; }
          .value.clickable:hover { text-decoration: underline; }
        </style>
        <div class="row">
          <div class="day"></div>
          <div class="value limit"></div>
          <div class="value endtime"></div>
          <div class="value default"></div>
        </div>
      `;
      this.shadowRoot.querySelector(".limit").addEventListener("click", () =>
        this._showMoreInfo(this._config.limit_entity)
      );
      this.shadowRoot.querySelector(".endtime").addEventListener("click", () =>
        this._showMoreInfo(this._config.endtime_entity)
      );
      this.shadowRoot.querySelector(".default").addEventListener("click", () =>
        this._showMoreInfo(this._config.default_limit_entity)
      );
    }

    this.shadowRoot.querySelector(".row").classList.toggle("header", Boolean(config.header));

    if (config.header) {
      this.shadowRoot.querySelector(".day").textContent = "";
      this.shadowRoot.querySelector(".limit").textContent = "Limit";
      this.shadowRoot.querySelector(".endtime").textContent = "End time";
      this.shadowRoot.querySelector(".default").textContent = "Default";
      this.shadowRoot.querySelector(".limit").classList.remove("clickable");
      this.shadowRoot.querySelector(".endtime").classList.remove("clickable");
      this.shadowRoot.querySelector(".default").classList.remove("clickable");
      return;
    }

    this.shadowRoot.querySelector(".day").textContent = config.day;
    this.shadowRoot
      .querySelector(".limit")
      .classList.toggle("clickable", Boolean(config.limit_entity));
    this.shadowRoot
      .querySelector(".endtime")
      .classList.toggle("clickable", Boolean(config.endtime_entity));
    this.shadowRoot
      .querySelector(".default")
      .classList.toggle("clickable", Boolean(config.default_limit_entity));

    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  get hass() {
    return this._hass;
  }

  _showMoreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    if (!this._hass || !this._config || !this.shadowRoot || this._config.header) return;

    const limitState = this._config.limit_entity
      ? this._hass.states[this._config.limit_entity]
      : undefined;
    const endtimeState = this._config.endtime_entity
      ? this._hass.states[this._config.endtime_entity]
      : undefined;
    const defaultState = this._config.default_limit_entity
      ? this._hass.states[this._config.default_limit_entity]
      : undefined;

    this.shadowRoot.querySelector(".limit").textContent = limitState
      ? `${limitState.state}%`
      : "–";
    this.shadowRoot.querySelector(".endtime").textContent = endtimeState
      ? formatTime(endtimeState.state)
      : "–";
    this.shadowRoot.querySelector(".default").textContent = defaultState
      ? `${defaultState.state}%`
      : "–";
  }
}

customElements.define("solarcharger-schedule-row", SolarchargerScheduleRow);
