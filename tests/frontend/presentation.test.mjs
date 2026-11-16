// The card's copy of the presentation formula against openframe's shared cases
// (tests/contract/presentation-cases.json at the pinned release).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  AUTO_MAX_CROP,
  presentationOf,
  screenFor,
  shownArea,
  zoomRange,
} from "../../custom_components/openframe/frontend/presentation.js";

const TABLE = JSON.parse(
  readFileSync(new URL("../contract/presentation-cases.json", import.meta.url), "utf8"),
);

test("matches every case of openframe's table within 1/10,000", () => {
  assert.ok(TABLE.cases.length >= 20);
  assert.equal(TABLE.autoMaxCrop, AUTO_MAX_CROP);
  for (const c of TABLE.cases) {
    const actual = presentationOf(c.photo, c.screen, c.crop, c.fillMode);
    for (const key of ["x", "y", "width", "height", "zoom"]) {
      assert.ok(
        Math.abs(actual[key] - c.expected[key]) < 1e-4,
        `${key} in ${c.scenario}: ${actual[key]} instead of ${c.expected[key]}`,
      );
    }
  }
});

test("gives the zoom range of the editor", () => {
  // 4000×3000 on 1920×1200: fully visible at 0.833, one original pixel per screen pixel at 2.083
  const range = zoomRange({ width: 4000, height: 3000 }, { width: 1920, height: 1200 });
  assert.ok(Math.abs(range.min - 0.8333) < 1e-4);
  assert.ok(Math.abs(range.max - 2.0833) < 1e-4);
  // A photo smaller than the screen allows 1 at most
  assert.equal(zoomRange({ width: 800, height: 600 }, { width: 1920, height: 1200 }).max, 1);
});

test("puts the screen in the frame's orientation", () => {
  assert.deepEqual(screenFor({ width: 1024, height: 600 }, "landscape"), { width: 1024, height: 600 });
  assert.deepEqual(screenFor({ width: 1024, height: 600 }, "portrait"), { width: 600, height: 1024 });
  assert.deepEqual(screenFor({ width: 600, height: 1024 }, "landscape"), { width: 1024, height: 600 });
});

test("knows where the shown part stands on the screen", () => {
  // A portrait photo in `auto` on a landscape frame: 1200 of 1920 pixels wide, borders left and right
  const photo = { width: 3000, height: 4000 };
  const screen = { width: 1920, height: 1200 };
  const area = shownArea(photo, screen, presentationOf(photo, screen, null, "auto"));
  assert.ok(Math.abs(area.width - 0.625) < 1e-6);
  assert.ok(Math.abs(area.height - 1) < 1e-6);
  assert.deepEqual(shownArea(photo, screen, presentationOf(photo, screen, null, "fill")), {
    width: 1,
    height: 1,
  });
});
