// The crop editor's logic as pure functions, testable with `node --test`; crop-editor.js only draws
// what editorView() returns and turns pointer, wheel and button input into changeCrop() calls.
//
// As in openframe's web UI (openspec change photo-crop, design decision 9), the viewport has the
// frame's aspect ratio and stays fixed while the photo moves. One pointer drags the focus point by
// the movement divided by the current scale, two pointers pinch, the wheel and −/+ zoom; everything
// is clamped by the presentation formula, so the editor shows what the frame will show.

import { clamp, presentationOf, shownArea, zoomRange } from "./presentation.js";

// Zoom factor of one press of − or +
export const ZOOM_STEP = 1.25;
const EPSILON = 1e-6;

/**
 * Where the photo stands in a viewport `viewportWidth` pixels wide: its drawn size and offset in
 * viewport pixels, the shown presentation, and whether the zoom is at one of its limits.
 */
export function editorView(photo, screen, crop, fillMode, viewportWidth) {
  const range = zoomRange(photo, screen);
  const shown = presentationOf(photo, screen, crop, fillMode);
  const area = shownArea(photo, screen, shown);
  // Pixels of the photo to pixels of the viewport
  const scale =
    (Math.max(screen.width / photo.width, screen.height / photo.height) *
      shown.zoom *
      viewportWidth) /
    screen.width;
  const viewportHeight = (viewportWidth * screen.height) / screen.width;
  return {
    shown,
    range,
    scale,
    viewportHeight,
    width: photo.width * scale,
    height: photo.height * scale,
    left: ((1 - area.width) / 2) * viewportWidth - shown.x * photo.width * scale,
    top: ((1 - area.height) / 2) * viewportHeight - shown.y * photo.height * scale,
    atMin: shown.zoom <= range.min + EPSILON,
    atMax: shown.zoom >= range.max - EPSILON,
  };
}

/**
 * The section after moving the shown part by `dx`, `dy` viewport pixels and zooming by `factor`.
 * It is stored as what is shown, so a focus point beyond the edge does not pile up and the photo
 * follows the finger back at once.
 */
export function changeCrop(photo, screen, crop, fillMode, viewportWidth, dx, dy, factor) {
  const { shown, range, scale } = editorView(photo, screen, crop, fillMode, viewportWidth);
  const zoom = clamp(shown.zoom * factor, range.min, range.max);
  const next = presentationOf(
    photo,
    screen,
    {
      x: shown.x + shown.width / 2 - (scale > 0 ? dx / (photo.width * scale) : 0),
      y: shown.y + shown.height / 2 - (scale > 0 ? dy / (photo.height * scale) : 0),
      zoom,
    },
    fillMode,
  );
  // The zoom stays exact, so its limits (the whole photo) are reached exactly
  return { x: round(next.x + next.width / 2), y: round(next.y + next.height / 2), zoom: next.zoom };
}

/**
 * The movement and zoom of one pointer moving from `last` to `now` while `other` rests: the
 * midpoint of two fingers moves by half of the movement, the zoom follows their distance.
 */
export function pinch(last, now, other) {
  const before = Math.hypot(last.x - other.x, last.y - other.y);
  const after = Math.hypot(now.x - other.x, now.y - other.y);
  return {
    dx: (now.x - last.x) / 2,
    dy: (now.y - last.y) / 2,
    factor: before > 0 ? after / before : 1,
  };
}

/** The zoom factor of a wheel movement. */
export function wheelFactor(deltaY) {
  return Math.exp(-deltaY * 0.002);
}

function round(value) {
  return Math.round(value * 10_000) / 10_000;
}
