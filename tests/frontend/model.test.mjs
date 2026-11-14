// The card's model against `hass` objects recorded from Home Assistant with the fake frame
// (`frame.json`), changed per scenario as the frame would change them.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  action,
  cardState,
  editorLabel,
  editorSchema,
  findEntities,
  frameDevices,
  strings,
} from "../../custom_components/openframe/frontend/model.js";

const RECORDED = JSON.parse(readFileSync(new URL("./frame.json", import.meta.url), "utf8"));
const DEVICE = Object.keys(RECORDED.devices)[0];
const IMAGE = "image.dev_frame_photo_on_screen";
const CAPTION = "sensor.dev_frame_photo_on_screen";
const DISPLAY = "light.dev_frame_display";
const SLIDESHOW = "switch.dev_frame_slideshow";
const SAFE_MODE = "binary_sensor.dev_frame_safe_mode";

/** A copy of the recording; `change` edits its states, entities or language. */
function hass(change = () => {}) {
  const copy = structuredClone(RECORDED);
  change(copy);
  return copy;
}

function setState(h, entityId, state, attributes = {}) {
  h.states[entityId] = {
    ...h.states[entityId],
    state,
    attributes: { ...h.states[entityId].attributes, ...attributes },
  };
}

const config = { type: "custom:openframe-card", device_id: DEVICE };

test("finds the frame's entities by translation key", () => {
  assert.deepEqual(findEntities(hass(), DEVICE), {
    image: IMAGE,
    caption: CAPTION,
    display: DISPLAY,
    slideshow: SLIDESHOW,
    previous: "button.dev_frame_previous_photo",
    next: "button.dev_frame_next_photo",
    safeMode: SAFE_MODE,
  });
});

test("finds renamed entities by translation key", () => {
  const h = hass((c) => {
    const entry = c.entities[DISPLAY];
    delete c.entities[DISPLAY];
    c.entities["light.living_room_frame"] = { ...entry, entity_id: "light.living_room_frame" };
  });
  assert.equal(findEntities(h, DEVICE).display, "light.living_room_frame");
});

test("falls back to the entity ID within the domain without translation_key", () => {
  const h = hass((c) => {
    for (const entry of Object.values(c.entities)) {
      delete entry.translation_key;
    }
  });
  const found = findEntities(h, DEVICE);
  assert.equal(found.display, DISPLAY, "light, not the display schedule switch");
  assert.equal(found.image, IMAGE);
  assert.equal(found.caption, CAPTION);
  assert.equal(found.next, "button.dev_frame_next_photo");
  assert.equal(found.safeMode, SAFE_MODE);
});

test("Choosing the frame › Device of another integration", () => {
  const h = hass((c) => {
    c.devices.other = { id: "other", name: "Hue bridge" };
    c.entities["light.hue"] = { entity_id: "light.hue", device_id: "other", platform: "hue" };
  });
  assert.deepEqual(cardState(h, { ...config, device_id: "other" }), {
    error: "The chosen device is not an openframe frame.",
  });
  assert.match(cardState(h, { type: "custom:openframe-card" }).error, /Choose an openframe frame/);
});

test("Choosing the frame › Card from the picker: the first frame and the device name", () => {
  const h = hass();
  assert.deepEqual(frameDevices(h), [DEVICE]);
  assert.equal(cardState(h, config).title, "Dev frame");
  assert.equal(cardState(h, { ...config, title: "Hall" }).title, "Hall");
});

test("the card picker prefers a frame that answers", () => {
  const h = hass((c) => {
    c.devices.offline = { id: "offline", name: "Offline frame" };
    c.entities = {
      "binary_sensor.offline_safe_mode": {
        entity_id: "binary_sensor.offline_safe_mode",
        device_id: "offline",
        platform: "openframe",
        translation_key: "safe_mode",
      },
      ...c.entities,
    };
    c.states["binary_sensor.offline_safe_mode"] = { state: "unavailable", attributes: {} };
  });
  assert.deepEqual(frameDevices(h), [DEVICE, "offline"]);
});

test("Photo in the frame's shape › Landscape frame", () => {
  const state = cardState(hass(), config);
  assert.equal(state.ratio, "1024 / 600");
  assert.equal(state.photo, RECORDED.states[IMAGE].attributes.entity_picture);
});

test("Photo in the frame's shape › Portrait frame", () => {
  const h = hass((c) => setState(c, IMAGE, c.states[IMAGE].state, { screen_width: 600, screen_height: 1024 }));
  assert.equal(cardState(h, config).ratio, "600 / 1024");
});

test("no photo in an empty library", () => {
  const state = cardState(hass((c) => setState(c, IMAGE, "unknown")), config);
  assert.equal(state.photo, null);
  assert.equal(state.noPhoto, "No photo");
});

test("States on the card › Display off at night", () => {
  const h = hass((c) => setState(c, DISPLAY, "off", { brightness: null, cause: "schedule" }));
  const state = cardState(h, config);
  assert.equal(state.dimmed, true);
  assert.notEqual(state.photo, null, "the last photo stays");
  assert.deepEqual(state.badges, ["Display off"]);
});

test("States on the card › paused and safe mode", () => {
  const h = hass((c) => {
    setState(c, SLIDESHOW, "off");
    setState(c, SAFE_MODE, "on");
  });
  assert.deepEqual(cardState(h, config).badges, ["Paused", "Safe mode"]);
});

test("States on the card › Frame unreachable", () => {
  const h = hass((c) => {
    for (const id of Object.keys(c.states)) {
      setState(c, id, "unavailable");
    }
  });
  const state = cardState(h, config);
  assert.deepEqual(state.badges, ["Unavailable"]);
  assert.equal(state.buttons, null, "no controls");
  assert.equal(state.photo, null);
});

test("Controls on the card › Next at night", () => {
  const h = hass((c) => setState(c, DISPLAY, "off"));
  const { buttons } = cardState(h, config);
  assert.equal(buttons.previous.enabled, false);
  assert.equal(buttons.next.enabled, false);
  assert.equal(buttons.playPause.enabled, true);
  assert.equal(buttons.display.enabled, true);
  assert.equal(buttons.display.on, false);
  assert.equal(buttons.display.label, "Switch display on");
});

test("Controls on the card › the display button hides while the display light is unavailable", () => {
  const { buttons } = cardState(hass((c) => setState(c, DISPLAY, "unavailable")), config);
  assert.equal(buttons.display.shown, false);
  assert.equal(buttons.previous.shown, true);
  assert.equal(buttons.playPause.shown, true);
});

test("Controls on the card › the services the buttons call", () => {
  const { buttons } = cardState(hass(), config);
  assert.deepEqual(action("display", buttons), ["light", "toggle", DISPLAY]);
  assert.deepEqual(action("playPause", buttons), ["switch", "turn_off", SLIDESHOW]);
  assert.deepEqual(action("next", buttons), ["button", "press", "button.dev_frame_next_photo"]);
  const paused = cardState(hass((c) => setState(c, SLIDESHOW, "off")), config).buttons;
  assert.deepEqual(action("playPause", paused), ["switch", "turn_on", SLIDESHOW]);
});

test("Caption on the card › Photo with comment", () => {
  assert.deepEqual(cardState(hass(), config).caption, { name: "Summer 2025", album: "holiday/2025" });
});

test("Caption on the card › a photo outside albums has one line, and the caption can be off", () => {
  const h = hass((c) => setState(c, CAPTION, "IMG_0003.jpg", { album: null }));
  assert.deepEqual(cardState(h, config).caption, { name: "IMG_0003.jpg", album: null });
  assert.equal(cardState(hass(), { ...config, show_caption: false }).caption, null);
});

test("Languages and themes › German user", () => {
  const h = hass((c) => {
    c.locale.language = "de";
    setState(c, DISPLAY, "off");
  });
  assert.deepEqual(cardState(h, config).badges, ["Display aus"]);
  assert.equal(strings("fr").displayOff, "Display off");
  assert.equal(strings("de-AT").displayOff, "Display aus");
});

test("English and German have the same texts", () => {
  assert.deepEqual(Object.keys(strings("de")).sort(), Object.keys(strings("en")).sort());
});

test("the editor limits the device picker to openframe", () => {
  const [device, title, caption] = editorSchema();
  assert.deepEqual(device.selector, { device: { integration: "openframe" } });
  assert.equal(title.name, "title");
  assert.equal(caption.default, true);
  assert.equal(editorLabel("show_caption", "de"), "Bildunterschrift anzeigen");
});
