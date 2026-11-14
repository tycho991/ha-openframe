// The openframe dashboard card and its editor: plain web components without a build step.
// What they show comes from model.js; this file only renders it and sends the button presses.

import {
  action,
  cardState,
  editorLabel,
  editorSchema,
  frameDevices,
  languageOf,
  strings,
} from "./model.js";

const ICONS = {
  previous: "mdi:skip-previous",
  play: "mdi:play",
  pause: "mdi:pause",
  next: "mdi:skip-next",
  displayOn: "mdi:monitor",
  displayOff: "mdi:monitor-off",
};

// Shown in a button when the frontend's `ha-icon` is not defined
const FALLBACK = {
  [ICONS.previous]: "⏮",
  [ICONS.play]: "▶",
  [ICONS.pause]: "⏸",
  [ICONS.next]: "⏭",
  [ICONS.displayOn]: "☀",
  [ICONS.displayOff]: "☾",
};

const STYLE = `
  [hidden] { display: none !important; }
  ha-card { overflow: hidden; color: var(--primary-text-color); }
  .title {
    padding: 12px 16px 8px; font-size: 1.2em; font-weight: 500;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .title:empty { display: none; }
  .box { position: relative; width: 100%; background: #000; overflow: hidden; }
  .box img {
    position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain;
    transition: filter 0.3s;
  }
  .box.dimmed img { filter: brightness(0.35); }
  .empty {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    color: #bbb;
  }
  .badges { position: absolute; top: 8px; left: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
  .badge {
    padding: 2px 8px; border-radius: 12px; font-size: 0.85em;
    background: rgba(0, 0, 0, 0.6); color: #fff;
  }
  .caption { padding: 8px 16px 0; min-width: 0; }
  .caption div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .album { color: var(--secondary-text-color); font-size: 0.9em; }
  .controls { display: flex; justify-content: space-around; padding: 8px; gap: 4px; }
  button {
    width: 48px; height: 48px; border: none; border-radius: 50%; padding: 0; cursor: pointer;
    background: none; color: var(--primary-text-color); font-size: 22px;
    display: flex; align-items: center; justify-content: center;
    --mdc-icon-size: 28px;
  }
  button:hover:not(:disabled) { background: rgba(127, 127, 127, 0.15); }
  button:focus-visible { outline: 2px solid var(--primary-color); }
  button:disabled { opacity: 0.35; cursor: default; }
  .error { padding: 16px; color: var(--error-color, #db4437); }
`;

class OpenframeCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = undefined;
    this._buttons = null;
  }

  static getConfigElement() {
    return document.createElement("openframe-card-editor");
  }

  static getStubConfig(hass) {
    const [deviceId] = frameDevices(hass);
    return deviceId ? { device_id: deviceId } : {};
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid configuration");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  _build() {
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="error" hidden></div>
        <div class="content">
          <div class="title"></div>
          <div class="box">
            <img alt="" hidden>
            <div class="empty" hidden></div>
            <div class="badges"></div>
          </div>
          <div class="caption" hidden><div class="name"></div><div class="album"></div></div>
          <div class="controls">
            <button data-action="previous"></button>
            <button data-action="playPause"></button>
            <button data-action="next"></button>
            <button data-action="display"></button>
          </div>
        </div>
      </ha-card>`;
    for (const button of root.querySelectorAll("button")) {
      button.addEventListener("click", () => this._press(button.dataset.action));
    }
    this._built = true;
  }

  _render() {
    if (!this._hass) {
      return;
    }
    if (!this._built) {
      this._build();
    }
    const root = this.shadowRoot;
    const state = cardState(this._hass, this._config);
    const error = root.querySelector(".error");
    const content = root.querySelector(".content");
    error.hidden = !state.error;
    content.hidden = Boolean(state.error);
    if (state.error) {
      error.textContent = state.error;
      return;
    }

    root.querySelector(".title").textContent = state.title;
    const box = root.querySelector(".box");
    box.style.aspectRatio = state.ratio;
    box.classList.toggle("dimmed", state.dimmed);
    const img = root.querySelector("img");
    // Only a changed URL is set, so the photo does not flicker on every state change
    if (state.photo && img.getAttribute("src") !== state.photo) {
      img.setAttribute("src", state.photo);
    }
    img.hidden = !state.photo;
    const empty = root.querySelector(".empty");
    empty.hidden = Boolean(state.photo) || state.buttons === null;
    empty.textContent = state.noPhoto ?? "";

    const badges = root.querySelector(".badges");
    badges.replaceChildren(
      ...state.badges.map((text) => {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = text;
        return badge;
      }),
    );

    const caption = root.querySelector(".caption");
    caption.hidden = !state.caption;
    if (state.caption) {
      root.querySelector(".name").textContent = state.caption.name;
      const album = root.querySelector(".album");
      album.textContent = state.caption.album ?? "";
      album.hidden = !state.caption.album;
    }

    this._buttons = state.buttons;
    const controls = root.querySelector(".controls");
    controls.hidden = state.buttons === null;
    if (state.buttons) {
      const { previous, playPause, next, display } = state.buttons;
      this._button("previous", previous, ICONS.previous);
      this._button("playPause", playPause, playPause.playing ? ICONS.pause : ICONS.play);
      this._button("next", next, ICONS.next);
      this._button("display", display, display.on ? ICONS.displayOff : ICONS.displayOn);
    }
  }

  _button(name, model, icon) {
    const button = this.shadowRoot.querySelector(`button[data-action="${name}"]`);
    button.hidden = !model.shown;
    button.disabled = !model.enabled;
    button.title = model.label;
    button.setAttribute("aria-label", model.label);
    if (button.dataset.icon === icon) {
      return;
    }
    button.dataset.icon = icon;
    if (customElements.get("ha-icon")) {
      const element = document.createElement("ha-icon");
      element.setAttribute("icon", icon);
      button.replaceChildren(element);
    } else {
      button.textContent = FALLBACK[icon];
    }
  }

  async _press(name) {
    if (!this._buttons || !this._hass) {
      return;
    }
    const [domain, service, entityId] = action(name, this._buttons);
    try {
      await this._hass.callService(domain, service, { entity_id: entityId });
    } catch {
      // The frontend shows the error, translated by the integration, as a toast
    }
  }
}

class OpenframeCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = undefined;
    this._form = null;
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) {
      return;
    }
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (event) => {
        this._config = { ...this._config, ...event.detail.value };
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.appendChild(this._form);
    }
    const language = languageOf(this._hass);
    this._form.hass = this._hass;
    this._form.schema = editorSchema();
    this._form.data = { show_caption: true, ...this._config };
    this._form.computeLabel = (field) => editorLabel(field.name, language);
  }
}

if (!customElements.get("openframe-card")) {
  customElements.define("openframe-card", OpenframeCard);
  customElements.define("openframe-card-editor", OpenframeCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "openframe-card",
    name: "openframe",
    description: strings(navigator.language).pickerDescription,
    preview: true,
    documentationURL: "https://github.com/tycho991/ha-openframe#dashboard-card",
  });
}
