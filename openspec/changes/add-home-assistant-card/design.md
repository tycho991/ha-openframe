# Design

## Context

After `add-home-assistant-integration` each frame is a device whose entities have stable `translation_key`s (`current_photo` image and sensor, the `display` light (since ha-openframe 0.2.0, `add-display-light`), the `slideshow` switch, `next_photo` and `previous_photo` buttons, `safe_mode` binary sensor). Home Assistant's frontend gives a card `hass.entities` (entity registry entries with `device_id`, `platform` and `translation_key`), `hass.states` and `hass.callService`. An image entity's state object has an `entity_picture` with an access token that changes when `image_last_updated` changes. Custom cards are web components; the frontend loads extra modules registered with `frontend.add_extra_js_url`. `GET /info` of the frame returns `screen` (width, height in the natural orientation), and the settings hold `orientation`. See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- No build step and no npm dependency: the card is plain JavaScript that the Marketplace (or HACS on Home Assistant 2026.10) installs as it is in the repository.
- The card finds a frame's entities by itself from the device, so renamed entity IDs do not break it.
- The card's logic is testable without a browser.

**Non-Goals:**
- Supporting more than one frame per card.
- Offline caching of photos in the browser beyond what the image entity already does.

## Decisions

### 1. Plain ES modules, a view and a pure model

`frontend/openframe-card.js` defines `openframe-card` and `openframe-card-editor` as `HTMLElement`s with a shadow root; `frontend/model.js` holds pure functions: `findEntities(hass, deviceId)` (by `platform === "openframe"`, the entity's domain and `translation_key`, so the display is `display` in the domain `light`), `cardState(hass, entities)` (photo URL, aspect ratio, badges, which buttons are shown and enabled, caption lines) and `strings(language)`. The view renders only what `cardState` returns and updates the DOM in place on each `hass` change instead of re-creating it, so the image does not flicker. `node --test` tests the model with recorded `hass` objects; Node is already in `.mise.toml`.

*Alternative:* Lit from a CDN or borrowed from the frontend's own elements. Rejected: a CDN is blocked in many installations and adds a runtime dependency; borrowing internals breaks with frontend updates. *Alternative:* TypeScript with a bundler and a committed bundle. Rejected: a build step and a generated file to keep in sync for about 400 lines of UI.

### 2. Loading the card once

`async_setup` (not per entry) registers `/openframe_static/` with `hass.http.async_register_static_paths` pointing to `frontend/`, and calls `add_extra_js_url(hass, f"/openframe_static/openframe-card.js?v={version}")` with the manifest's version, read outside the event loop, so a new release busts the browser cache. A flag in `hass.data` keeps it from registering twice. The card registers itself in `window.customCards` for the card picker, with a stub config that picks the first openframe device.

### 3. Screen format as attributes

The image entity gets `screen_width` and `screen_height` from `GET /info` (`screen`), swapped when `settings.orientation` is `portrait`. The info is read on the full tier, which also runs on a settings change, so an orientation change shows within one tick. The card uses the ratio as the photo box's `aspect-ratio` and draws the image with `object-fit: contain` on black; since the display size of the photo is exactly the part the frame shows, with its black borders as part of the box, this reproduces the frame.

*Alternative:* a WebSocket command that returns the screen format. Rejected: two static numbers on an entity are simpler, and the card already reads the image entity.

### 4. Commands go through the entities' services

Play/pause calls `switch.turn_on`/`turn_off` on the slideshow switch, previous and next call `button.press`, the display button calls `light.toggle` on the display light. Errors (`HomeAssistantError` with a translated message) are shown by the frontend's own toast. The card adds no WebSocket commands.

### 5. Layout

The card is a column: the photo box with the badges in its top left corner, the caption in up to two lines with ellipsis, and a row of four 48-pixel icon buttons (`ha-icon-button` is not used; plain `button`s with `ha-icon` keep the component independent of frontend internals, falling back to text if `ha-icon` is not defined). `getCardSize` returns 6, `getGridOptions` returns 12 columns by default and a minimum of 6. Colours come from `--primary-text-color`, `--secondary-text-color`, `--card-background-color` and `--primary-color`.

## Risks / Trade-offs

- [`hass.entities` lacks `translation_key` in some frontend versions] → It exists in 2026.10, the minimum version; the model falls back to matching the entity ID's suffix within the domain and the tests cover both.
- [The display button shows although switching can fail] → The light stays available without device administrator while the brightness may be set, and its state does not tell whether switching works. A refused press shows the frame's message as a toast. An attribute on the light for this is left to a change of its own.
- [The browser keeps an old card after an update] → The `?v=` parameter changes with every release; the README says to reload the page.
- [The extra JS URL loads the card on every dashboard, also without a frame] → The module is small and defines only two elements.
