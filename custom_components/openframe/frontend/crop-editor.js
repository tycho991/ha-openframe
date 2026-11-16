// The crop editor: a dialog over the dashboard that edits the section of the photo the frame showed
// when it opened. The logic is in crop-model.js; this element draws it and sends the input.
//
// The frame's shape stays fixed in the middle of a larger stage, and the whole photo moves behind
// it: what the frame will show is inside, the rest of the photo is dimmed around it. The dialog
// opens with showModal(), in the browser's top layer, so no transform of the dashboard can clip it.
// It keeps the photo it was opened for: the WebSocket answer is read once.

import { ZOOM_STEP, changeCrop, editorView, pinch, wheelFactor } from "./crop-model.js";

// The frame's share of the stage's width at most, and the stage's height around the frame
const FRAME_WIDTH = 0.7;
const STAGE_HEIGHT = 1.5;

const STYLE = `
  dialog {
    border: 0; border-radius: 12px; padding: 16px; box-sizing: border-box;
    width: min(1100px, calc(100vw - 16px)); max-width: calc(100vw - 16px);
    max-height: calc(100dvh - 16px);
    background: var(--card-background-color, #fff); color: var(--primary-text-color, #000);
  }
  dialog::backdrop { background: rgba(0, 0, 0, 0.6); }
  @media (max-width: 600px) {
    dialog { padding: 8px; width: calc(100vw - 8px); max-width: calc(100vw - 8px); }
  }
  h2 { margin: 0 0 4px; font-size: 1.2em; font-weight: 500; }
  .hint { margin: 0 0 12px; color: var(--secondary-text-color, #666); font-size: 0.9em; }
  .stage {
    position: relative; width: 100%; overflow: hidden; background: #000;
    touch-action: none; cursor: grab; user-select: none;
  }
  .stage:active { cursor: grabbing; }
  img {
    position: absolute; left: 0; top: 0; max-width: none; transform-origin: 0 0;
    pointer-events: none;
  }
  .viewport {
    position: absolute; pointer-events: none; outline: 2px solid rgba(255, 255, 255, 0.9);
    box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.6);
  }
  .row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .actions { justify-content: flex-end; }
  button {
    min-width: 44px; min-height: 40px; padding: 0 14px; border-radius: 20px; cursor: pointer;
    border: 1px solid var(--divider-color, #ccc); background: none; font: inherit;
    color: var(--primary-text-color, #000);
  }
  button.primary {
    background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4);
    color: var(--text-primary-color, #fff);
  }
  button:disabled { opacity: 0.4; cursor: default; }
  button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); }
  .zoom button { width: 44px; padding: 0; font-size: 1.3em; }
  .error { margin: 12px 0 0; color: var(--error-color, #db4437); }
`;

class OpenframeCropEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._pointers = new Map();
    this._frame = { left: 0, top: 0, width: 0, height: 0 };
  }

  /**
   * Opens the editor for `data` (the answer of `openframe/photo`) of the frame `deviceId`; the
   * element removes itself when the dialog closes.
   */
  open({ hass, deviceId, data, text }) {
    this._hass = hass;
    this._deviceId = deviceId;
    this._photo = data.photo;
    this._size = { width: data.photo.width, height: data.photo.height };
    this._screen = data.screen;
    this._fillMode = data.fillMode;
    // The section being edited, null for automatic; nothing is stored before "Save"
    this._crop = data.photo.crop;
    this._build(text);
    this._dialog.showModal();
    this._layout();
  }

  _build(text) {
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>${STYLE}</style>
      <dialog aria-label="${text.cropTitle}">
        <h2>${text.cropTitle}</h2>
        <p class="hint">${text.cropHint}</p>
        <div class="stage" role="application" aria-label="${text.cropTitle}">
          <img alt="" draggable="false">
          <div class="viewport"></div>
        </div>
        <div class="row zoom">
          <button type="button" data-action="zoomOut" aria-label="${text.cropZoomOut}"
            title="${text.cropZoomOut}">−</button>
          <button type="button" data-action="zoomIn" aria-label="${text.cropZoomIn}"
            title="${text.cropZoomIn}">+</button>
        </div>
        <p class="error" role="alert" hidden></p>
        <div class="row actions">
          <button type="button" data-action="cancel">${text.cropCancel}</button>
          <button type="button" data-action="automatic">${text.cropAutomatic}</button>
          <button type="button" class="primary" data-action="save">${text.cropSave}</button>
        </div>
      </dialog>`;
    this._dialog = root.querySelector("dialog");
    this._stage = root.querySelector(".stage");
    this._viewport = root.querySelector(".viewport");
    this._img = root.querySelector("img");
    this._error = root.querySelector(".error");
    this._img.src = this._photo.url;
    this._img.alt = this._photo.path;

    const press = {
      zoomOut: () => this._change(0, 0, 1 / ZOOM_STEP),
      zoomIn: () => this._change(0, 0, ZOOM_STEP),
      cancel: () => this._dialog.close(),
      automatic: () => this._save(null),
      save: () => this._save(this._crop),
    };
    for (const button of root.querySelectorAll("button")) {
      button.addEventListener("click", press[button.dataset.action]);
    }
    this._dialog.addEventListener("close", () => this.remove());

    const stage = this._stage;
    stage.addEventListener("pointerdown", (e) => this._down(e));
    stage.addEventListener("pointermove", (e) => this._move(e));
    stage.addEventListener("pointerup", (e) => this._pointers.delete(e.pointerId));
    stage.addEventListener("pointercancel", (e) => this._pointers.delete(e.pointerId));
    // Not passive, so the page does not scroll while the wheel zooms
    stage.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        this._change(0, 0, wheelFactor(e.deltaY));
      },
      { passive: false },
    );
    new ResizeObserver(() => this._layout()).observe(stage);
  }

  /** Places the frame's shape in the middle of the stage, as large as the dialog allows. */
  _layout() {
    const { width, height } = this._screen;
    const stageWidth = this._stage.clientWidth;
    const frameWidth = Math.min(
      stageWidth * FRAME_WIDTH,
      ((window.innerHeight * 0.5) / STAGE_HEIGHT) * (width / height),
    );
    const frameHeight = (frameWidth * height) / width;
    const stageHeight = frameHeight * STAGE_HEIGHT;
    this._stage.style.height = `${stageHeight}px`;
    this._frame = {
      left: (stageWidth - frameWidth) / 2,
      top: (stageHeight - frameHeight) / 2,
      width: frameWidth,
      height: frameHeight,
    };
    Object.assign(this._viewport.style, {
      left: `${this._frame.left}px`,
      top: `${this._frame.top}px`,
      width: `${frameWidth}px`,
      height: `${frameHeight}px`,
    });
    this._draw();
  }

  _down(e) {
    try {
      // Keeps the drag when the finger leaves the stage
      this._stage.setPointerCapture(e.pointerId);
    } catch {
      // A pointer the browser no longer knows as active: the drag works within the stage
    }
    this._pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  }

  _move(e) {
    const last = this._pointers.get(e.pointerId);
    if (!last) {
      return;
    }
    const now = { x: e.clientX, y: e.clientY };
    const other = [...this._pointers].find(([id]) => id !== e.pointerId)?.[1];
    if (other) {
      const { dx, dy, factor } = pinch(last, now, other);
      this._change(dx, dy, factor);
    } else {
      this._change(now.x - last.x, now.y - last.y, 1);
    }
    this._pointers.set(e.pointerId, now);
  }

  _change(dx, dy, factor) {
    this._crop = changeCrop(
      this._size,
      this._screen,
      this._crop,
      this._fillMode,
      this._frame.width,
      dx,
      dy,
      factor,
    );
    this._draw();
  }

  _draw() {
    const view = editorView(this._size, this._screen, this._crop, this._fillMode, this._frame.width);
    const img = this._img;
    img.style.width = `${view.width}px`;
    img.style.height = `${view.height}px`;
    img.style.transform = `translate(${this._frame.left + view.left}px, ${this._frame.top + view.top}px)`;
    // What the frame will show, for tests and screenshots
    for (const key of ["x", "y", "width", "height", "zoom"]) {
      this._viewport.dataset[key] = String(view.shown[key]);
    }
    const root = this.shadowRoot;
    root.querySelector('[data-action="zoomOut"]').disabled = view.atMin;
    root.querySelector('[data-action="zoomIn"]').disabled = view.atMax;
  }

  async _save(crop) {
    const buttons = this.shadowRoot.querySelectorAll(".actions button");
    for (const button of buttons) {
      button.disabled = true;
    }
    this._error.hidden = true;
    const data = crop ? { ...crop } : { reset: true };
    try {
      await this._hass.callService(
        "openframe",
        "set_photo_crop",
        { photo_id: this._photo.id, ...data },
        { device_id: this._deviceId },
      );
      this._dialog.close();
    } catch (err) {
      // The message of the integration's translated error; the editor stays open
      this._error.textContent = err?.message ?? String(err);
      this._error.hidden = false;
      for (const button of buttons) {
        button.disabled = false;
      }
    }
  }
}

if (!customElements.get("openframe-crop-editor")) {
  customElements.define("openframe-crop-editor", OpenframeCropEditor);
}
