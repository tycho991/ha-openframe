# Proposal

## Why

openframe frames can only be controlled from their own web UI. Home Assistant cannot switch the display, react to the photo on screen or show the frame's state, so a frame cannot take part in automations such as "display off when nobody is home" or "pause while the TV runs". The earlier `pictureframe` app had a Home Assistant integration; the openframe API is not compatible with it, and openframe's bootstrap change left the integration for a follow-up. With `add-slideshow-control-api` in openframe, the API offers everything a first integration needs.

## What Changes

- **New repository `tycho991/ha-openframe`** with a custom integration `openframe` for Home Assistant 2026.10 and later, installable through HACS as a custom repository, with tests, CI, Renovate and releases.
- **Adding a frame by pairing.** The user enters the frame's address; Home Assistant asks the frame to show a pairing code, the user types the code, and the integration stores the token it receives. A frame is identified by its durable ID, so a changed address does not create a second frame. A revoked pairing leads to Home Assistant's re-authentication; a new address can be entered without pairing again; removing the frame from Home Assistant revokes its pairing on the frame.
- **One device per frame with entities** for: the display (on/off, with the reason and the next change), the slideshow (play/pause, next, previous), the photo on screen (image and sensor), the settings that make sense in automations (interval, order, transition, fill mode, orientation, clock, display schedule, automatic update check), photo counts, one switch per album, sync and status per remote source, app updates as an update entity, and the safe mode and transition fallback as problem sensors.
- **Local polling** of the frame with a short interval for display and slideshow and a full read only when the frame's versions change.
- **Contract with openframe.** The integration is tested against a copy of openframe's `api/openapi.yaml` pinned to an openframe release; frames older than the first release with `/slideshow` are refused with a clear message.

### Out of scope

- The dashboard card (`add-home-assistant-card`) and photo actions, the media browser and the crop editor (`add-home-assistant-photo-management`).
- Discovery of frames on the network: openframe does not announce itself over mDNS.
- Push updates from the frame; the integration polls.
- Submission to Home Assistant core or the HACS default list.
- Changing the frame's name, language, clock layout, caption layout, display schedule times, cache budget or remote sources from Home Assistant; the web UI does that.

## Capabilities

### New Capabilities

- `frame-connection`: adding a frame by pairing, its identity, re-authentication, a changed address, removal, the minimum frame version, polling and availability.
- `frame-entities`: the device of a frame and its entities for display, slideshow, photo on screen, settings, library, albums, sources, updates and health.
- `integration-distribution`: installation through HACS, versions and releases, the supported Home Assistant version and the contract with the openframe API.

### Modified Capabilities

None.

## Impact

- New repository: `custom_components/openframe/` (config flow, API client, coordinator, entity platforms `binary_sensor`, `button`, `image`, `number`, `select`, `sensor`, `switch`, `update`, diagnostics, translations `en` and `de`), `tests/`, `pyproject.toml` with `uv.lock`, `hacs.json`, `.github/workflows/`, `renovate.json`, `release-please-config.json`, `README.md`, `LICENSE` (MIT), `CLAUDE.md`.
- Depends on openframe's `add-slideshow-control-api` being released; the integration's minimum frame version is that release.
- Each Home Assistant instance appears as a paired device named "Home Assistant" in the frame's web UI.
- `../openframe-private/DEVICE_TEST.md`: rows for the integration against the real frames.
