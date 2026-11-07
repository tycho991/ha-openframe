# Design

## Context

After `add-home-assistant-integration` and `add-home-assistant-card` the integration has an API client, a coordinator whose data includes the photo on screen (`GET /slideshow` returns the full `Photo` record), and a card of plain ES modules served from `/openframe_static/`. openframe's photo API offers `GET /photos` (pages of at most 500, filters `album`, `subalbums`, `visible`, sort `date_desc`), `PATCH /photos/{id}` (`hidden`, `comment`, `crop`), `DELETE /photos/{id}` (409 `read_only_source` for remote photos), `POST /photos` (multipart `file[]` and `album`, 415, 507, 503), `PATCH /albums` (`name`, `hidden`) and `GET /photos/{id}/image?size=thumb|display|full` with the token. A section is `{x, y, zoom}`; openframe's `Presentation.of` in `:core` and `presentation.ts` in the web UI compute the shown window and the zoom range, and both are tested against `api/fixtures/presentation-cases.json`. See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- The editor in the card shows exactly what the frame will show, by the same formula and the same test cases as openframe.
- The frame's address and token never leave Home Assistant's backend.
- No request to the frame for a media browser folder the user does not open.

**Non-Goals:**
- Caching photos in Home Assistant beyond the HTTP caching headers the proxy passes on.
- Showing the media browser's photos in their displayed section; it shows originals.

## Decisions

### 1. Services registered once, targeting devices

`services.py` registers all actions in `async_setup` with `homeassistant.helpers.service.async_register_admin_service`, so that users without administrator rights are refused and automations (no user in the context) run. Each action takes a device target (`target: device: integration: openframe` in `services.yaml`), resolved to config entries through the device registry. `photo_id` is optional for the photo actions; with an ID exactly one frame must be targeted (`ServiceValidationError` otherwise). Without an ID each frame's `coordinator.data.slideshow.photo` is used; the coordinator's last poll is at most 15 seconds old, so the action reads `GET /slideshow` once before acting, so that it hits the photo on the wall at that moment.

| Action | Fields | Frame request | Response |
|---|---|---|---|
| `set_photo_hidden` | `photo_id?`, `hidden` | `PATCH /photos/{id}` | photo |
| `set_photo_comment` | `photo_id?`, `comment` (empty removes) | `PATCH /photos/{id}` (`null` for empty) | photo |
| `set_photo_crop` | `photo_id?`, `x`, `y`, `zoom` or `reset` | `PATCH /photos/{id}` | photo |
| `delete_photo` | `photo_id?` | `DELETE /photos/{id}` | none |
| `upload_photo` | `file_path` (list), `album?` | `POST /photos` | `{photos: [{id, path, album}]}` |
| `set_album_hidden` | `album`, `hidden` | `PATCH /albums` | none |

The voluptuous schemas check ranges before the frame is asked (`x`, `y` in [0, 1], `zoom` in (0, 4], `x`/`y`/`zoom` all present or `reset` true). Responses are `SupportsResponse.OPTIONAL` except for `upload_photo` (`ONLY` is not used; the upload is useful without a response too). Frame errors map to translated `HomeAssistantError`s: 404 → `photo_not_found`, 409 `read_only_source` → `read_only_source`, 415 → `unsupported_format` with the frame's message, 507 → `storage_full`, 400 with `fields` → the field names. After a successful action the coordinator's full tier is forced.

*Alternative:* entity services on the image entity. Rejected: the actions belong to the frame, not to one entity, and `upload_photo` has nothing to do with the photo on screen.

### 2. Uploads read files in the executor

`upload_photo` checks every path with `hass.config.is_allowed_path` first, then reads the files in the executor and sends one multipart request with all of them, with a 120-second timeout. The frame stores all or nothing, so a partial upload cannot happen. The content type is guessed from the file name; the frame decides what it accepts.

### 3. One authenticated image proxy

`OpenframeImageView(HomeAssistantView)` at `/api/openframe/{entry_id}/photos/{photo_id}/{size}` with `requires_auth = True` fetches `GET /photos/{id}/image?size=…` with the entry's token and streams the answer with its `Content-Type`, `ETag` and `Cache-Control`; `If-None-Match` is passed on. `size` is limited to `thumb` and `full`, `photo_id` to openframe's ID pattern. The media browser and the editor get URLs signed with `homeassistant.components.http.auth.async_sign_path` (expiry 1 hour), because an `<img>` cannot send the session header.

*Alternative:* the frame's own signed URLs. Rejected: the frame is not reachable from outside the LAN, and the URL would reveal its address.

### 4. Media source

`media_source.py` implements `OpenframeMediaSource` with identifiers `{entry_id}`, `{entry_id}/album/{path}`, `{entry_id}/all` and `{entry_id}/photo/{id}`. A frame folder lists the albums from `GET /albums` whose path has no `/`, plus "All photos" (`GET /photos?sort=date_desc&limit=500`). An album folder lists the albums one level below it and the photos of `GET /photos?album={path}&subalbums=false&limit=500`. With a single frame the root shows the frame's folder directly. Each photo is a `BrowseMediaSource` with `media_class` image, `media_content_type` `image/jpeg`, the thumbnail URL of decision 3, `can_play` true; `async_resolve_media` returns the signed `full` URL. Folders are read when opened, not polled.

### 5. WebSocket command for the editor

`openframe/photo` (`device_id`; admin only) reads `GET /slideshow` and returns the photo on screen with its width, height, section and presentation, the screen size in the current orientation and the signed `full` URL. The editor needs these values, which are not entity attributes, and needs them fresh when it opens. The command takes no photo ID: the card opens the editor only for the photo on screen.

### 6. Editor in the card

`frontend/presentation.js` is a port of `presentation.ts` from openframe's web UI: zoom range `[z_min, z_max]`, the shown window for `{x, y, zoom}`, and the fill-mode defaults. `node --test` runs it against `tests/contract/presentation-cases.json`, which `tools/update-contract.sh` copies from `api/fixtures/` at the pinned tag, within 1/10,000. `frontend/crop-editor.js` follows design decision 9 of openframe's `photo-crop` change: the viewport has the frame's aspect ratio and stays fixed, the photo is drawn with a CSS transform; one pointer drags the focus point (movement divided by the current scale), two pointers pinch, the wheel and −/+ zoom, all clamped. It opens as a full-screen overlay in the card's shadow root, keeps the photo it was opened for, and saves with `openframe.set_photo_crop`. Crop and hide buttons appear only when `hass.user.is_admin` is true.

### 7. Hide button

The hide button asks for confirmation inside the card (two-step button, not `window.confirm`, which kiosk browsers often block), then calls `openframe.set_photo_hidden` with the frame as target and no photo ID, and shows "Photo hidden" for a few seconds.

## Risks / Trade-offs

- [The photo on screen changes between the action's `GET /slideshow` and its `PATCH`] → The window is one round trip on the LAN; a photo change in it hits the photo that was on screen a moment before, which is what the user saw.
- [The JavaScript copy of the presentation formula drifts from openframe's] → Both are tested against the same fixture at the pinned tag; a changed fixture fails the contract update (as for the API in `add-home-assistant-integration`, decision 7).
- [A media browser folder with 500 photos asks the frame for 500 thumbnails] → The browser loads them lazily as they scroll into view, the proxy passes on the frame's `ETag` and `immutable` caching, and the frame renders thumbnails once.
- [Uploads of many large files hit Home Assistant's memory] → The files are read one after another into the multipart stream; the frame refuses more than its free space allows (507).
