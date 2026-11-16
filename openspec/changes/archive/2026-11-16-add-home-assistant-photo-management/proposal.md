# Proposal

## Why

With the integration and the card, Home Assistant shows and controls a frame, but it cannot touch the photos. A photo that should not be on the wall can only be hidden in the frame's web UI, a camera snapshot or a downloaded photo cannot be sent to the frame from an automation, and the photos cannot be looked at from Home Assistant. `pictureframe`'s integration had photo services, a media browser and a crop editor in its card; this change brings them to openframe, built on openframe's existing photo API.

## What Changes

- **Photo actions** (Home Assistant services of the domain `openframe`): hide or show a photo, set or remove its comment, set or remove its section (focus point and zoom), delete a photo of the local folder, upload files from Home Assistant's allowed folders into an album, and hide or show an album. The photo actions act on the photo on screen when no photo ID is given, so "hide the photo that is on the wall now" is one action without looking up an ID. Actions that change a photo return its updated record.
- **Media browser.** Each frame appears in Home Assistant's media browser with its albums as folders and its photos as images, newest first, with thumbnails; opening a photo shows it in full size. Photos are served through Home Assistant to signed-in users only, so the browser never talks to the frame directly.
- **Card: crop and hide.** The card gets a crop button that opens an editor for the photo on screen, which works like the section editor of openframe's web UI (the frame's shape stays fixed, the photo moves and zooms, "Automatic" removes the section), and a button that hides the photo on screen.

### Out of scope

- Moving photos between albums and renaming albums: openframe's API has no such operation.
- Retrying quarantined photos, skipped files and the photo grid of the web UI.
- Uploading from the media browser's own upload button.
- Videos: openframe shows no videos.
- Batch actions on many photos at once; automations can loop over IDs.

## Capabilities

### New Capabilities

- `photo-actions`: the services for photos and albums, their targets, the default to the photo on screen, their responses and errors.
- `media-browser`: frames, albums and photos in Home Assistant's media browser, and serving photos to signed-in users.

### Modified Capabilities

- `dashboard-card`: the crop editor and the hide button on the card.

## Impact

- `custom_components/openframe/`: `services.py` and `services.yaml` with translations, `media_source.py`, an authenticated `HomeAssistantView` that proxies photo images, a WebSocket command `openframe/photo` for the editor, API client methods for `PATCH /photos/{id}`, `DELETE /photos/{id}`, `POST /photos`, `GET /photos` pages and `PATCH /albums`; `manifest.json` gains `media_source` in its dependencies.
- `frontend/`: the crop editor, `presentation.js` as a copy of openframe's presentation formula, the hide button.
- `tests/contract/`: `presentation-cases.json` from openframe's `api/fixtures/` at the pinned tag, used by the editor's tests; `tools/update-contract.sh` downloads it too.
- `README.md`: actions with automation examples, the media browser, the editor.
- `../openframe-private/DEVICE_TEST.md`: rows for upload, crop and the media browser against a real frame.
