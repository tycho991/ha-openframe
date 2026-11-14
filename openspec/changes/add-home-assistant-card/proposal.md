# Proposal

## Why

After `add-home-assistant-integration` a frame has the right entities, but a dashboard built from Home Assistant's standard cards shows the photo, the controls and the display state as separate tiles. The photo appears in the image card's shape, not in the frame's, and nothing shows at a glance that the display is off or the slideshow paused. `pictureframe` had its own card for this.

## What Changes

- **A card `openframe-card`** that the integration brings along and loads by itself: the photo on screen in the frame's aspect ratio, dimmed with a badge while the display is off, badges for "paused", "safe mode" and "unavailable", the caption below the photo, and buttons for previous, play/pause, next and display on/off (the display light of ha-openframe 0.2.0).
- **Card editor and card picker.** The card appears as "openframe" in Home Assistant's card picker; its editor offers a device picker limited to openframe frames, a title and whether to show the caption.
- **The frame's screen format as entity attributes.** The image entity of the photo on screen gets the frame's screen width and height in the current orientation, so the card can draw the frame's shape.
- Texts of the card in English and German, following the user's Home Assistant language.

### Out of scope

- The crop editor in the card (`add-home-assistant-photo-management`).
- A photo grid or browsing photos in the card; the media browser comes with `add-home-assistant-photo-management`.
- Settings in the card; the configuration entities and the frame's web UI cover them.
- A build step or npm dependencies for the card.

## Capabilities

### New Capabilities

- `dashboard-card`: the card's content, controls, states, editor, loading and languages.

### Modified Capabilities

- `frame-entities`: the image entity of the photo on screen carries the frame's screen format.

## Impact

- Builds on ha-openframe 0.2.0 (`add-display-light`): the display is the light with the translation key `display`.
- `custom_components/openframe/frontend/` with the card as plain ES modules; `__init__.py` registers the static path and the extra JS URL once per Home Assistant start; `image.py` gains the attributes.
- `manifest.json` gains the dependencies `frontend` and `http`.
- `tests/`: Python tests for the registration and the attributes, `node --test` tests for the card's logic; `ci.yml` runs them.
- `README.md`: the card and its YAML options.
- `../openframe-private/DEVICE_TEST.md`: the card on a phone and on a wall tablet.
