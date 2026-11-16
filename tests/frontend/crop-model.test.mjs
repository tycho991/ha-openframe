// The crop editor's model: what the viewport shows, and how drag, pinch, wheel and −/+ are clamped
// (`dashboard-card` › Crop editor on the card).

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ZOOM_STEP,
  changeCrop,
  editorView,
  pinch,
  wheelFactor,
} from "../../custom_components/openframe/frontend/crop-model.js";
import { presentationOf, shownArea } from "../../custom_components/openframe/frontend/presentation.js";

const PORTRAIT = { width: 3000, height: 4000 };
const LANDSCAPE = { width: 4000, height: 3000 };
const SCREEN = { width: 1920, height: 1200 };
const VIEWPORT = 960;

function close(actual, expected, what) {
  assert.ok(Math.abs(actual - expected) < 1e-6, `${what}: ${actual} instead of ${expected}`);
}

test("Open the editor: the part the frame shows fills the frame's shape", () => {
  // A portrait photo on a landscape frame with a section on its upper part
  const crop = { x: 0.5, y: 0.2, zoom: 1 };
  const view = editorView(PORTRAIT, SCREEN, crop, "auto", VIEWPORT);
  const shown = presentationOf(PORTRAIT, SCREEN, crop, "auto");
  assert.deepEqual(view.shown, shown);
  close(view.viewportHeight, (VIEWPORT * SCREEN.height) / SCREEN.width, "viewport height");
  // The shown window starts at the viewport's corner and is as large as the viewport
  close(view.left + shown.x * view.width, 0, "left edge of the shown part");
  close(view.top + shown.y * view.height, 0, "top edge of the shown part");
  close(shown.width * view.width, VIEWPORT, "width of the shown part");
  close(shown.height * view.height, view.viewportHeight, "height of the shown part");
});

test("Open the editor without a section: the fill mode's part, centred with its borders", () => {
  const view = editorView(PORTRAIT, SCREEN, null, "auto", VIEWPORT);
  const area = shownArea(PORTRAIT, SCREEN, view.shown);
  assert.ok(area.width < 1, "borders left and right");
  close(view.left + view.shown.x * view.width, ((1 - area.width) / 2) * VIEWPORT, "left border");
});

test("dragging moves the focus point against the finger and stops at the edge", () => {
  let crop = { x: 0.5, y: 0.5, zoom: 1.5 };
  // Dragging the photo to the right shows more of its left side
  crop = changeCrop(LANDSCAPE, SCREEN, crop, "auto", VIEWPORT, 50, 0, 1);
  assert.ok(crop.x < 0.5);
  // Far beyond the edge, the shown part stays at the photo's left edge
  crop = changeCrop(LANDSCAPE, SCREEN, crop, "auto", VIEWPORT, 100_000, 0, 1);
  const atEdge = presentationOf(LANDSCAPE, SCREEN, crop, "auto");
  close(atEdge.x, 0, "left edge");
  // and follows the finger back at once, without first undoing the movement beyond the edge
  const back = changeCrop(LANDSCAPE, SCREEN, crop, "auto", VIEWPORT, -10, 0, 1);
  assert.ok(presentationOf(LANDSCAPE, SCREEN, back, "auto").x > 0);
});

test("Zoom limits: zoomed out fully, the whole photo is visible with borders", () => {
  let crop = { x: 0.3, y: 0.3, zoom: 1 };
  crop = changeCrop(PORTRAIT, SCREEN, crop, "auto", VIEWPORT, 0, 0, 0.001);
  const view = editorView(PORTRAIT, SCREEN, crop, "auto", VIEWPORT);
  assert.equal(view.atMin, true);
  close(crop.zoom, view.range.min, "zoom at its minimum");
  assert.deepEqual([view.shown.width, view.shown.height], [1, 1]);
  const area = shownArea(PORTRAIT, SCREEN, view.shown);
  assert.ok(area.width < 1, "black borders left and right");
  // Zooming out further changes nothing
  assert.deepEqual(changeCrop(PORTRAIT, SCREEN, crop, "auto", VIEWPORT, 0, 0, 1 / ZOOM_STEP), crop);
});

test("zooming in stops at one original pixel per screen pixel", () => {
  let crop = { x: 0.5, y: 0.5, zoom: 1 };
  for (let i = 0; i < 20; i++) {
    crop = changeCrop(LANDSCAPE, SCREEN, crop, "fill", VIEWPORT, 0, 0, ZOOM_STEP);
  }
  const view = editorView(LANDSCAPE, SCREEN, crop, "fill", VIEWPORT);
  assert.equal(view.atMax, true);
  close(crop.zoom, view.range.max, "zoom at its maximum");
});

test("two fingers pinch around their midpoint", () => {
  const other = { x: 0, y: 0 };
  assert.deepEqual(pinch({ x: 100, y: 0 }, { x: 200, y: 0 }, other), { dx: 50, dy: 0, factor: 2 });
  assert.deepEqual(pinch({ x: 0, y: 0 }, { x: 10, y: 0 }, other), { dx: 5, dy: 0, factor: 1 });
});

test("the wheel zooms in when turned away and out when turned back", () => {
  assert.equal(wheelFactor(0), 1);
  assert.ok(wheelFactor(-100) > 1);
  assert.ok(wheelFactor(100) < 1);
});
