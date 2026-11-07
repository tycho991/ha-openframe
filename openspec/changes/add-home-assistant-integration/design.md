# Design

## Context

The repository is empty apart from OpenSpec and mise. The frame side is openframe's versioned JSON API under `/api/v1` (`api/openapi.yaml` in `tycho991/openframe`): `GET /info` and the pairing endpoints work without a token, everything else needs `Authorization: Bearer`. Errors are `{"error": {"code", "message", "fields"}}`. `GET /state` returns `libraryVersion`, `settingsVersion`, `appVersion` and `safeMode`, which change when the library, the settings or the app change; `PATCH /settings` merges partial objects, also inside `clock` and `displaySchedule`. `GET /slideshow` and `POST /slideshow` come with openframe's `add-slideshow-control-api`. The frames are weak (Frameo `PFF_1024` on Android 6, Lenovo Yoga Tablet 2 on Android 5), and openframe's server handles requests on a small thread pool.

`pictureframe`'s integration is the model for the structure: a thin aiohttp client, one coordinator that polls cheaply and reads the heavy parts on a version change, entity descriptions per platform, translated errors. Its code is not copied: the API, the auth and the entity set differ. See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- At most three small requests per frame every 15 seconds in the normal case.
- Every request and response the integration uses is checked against openframe's contract in the tests, so a change of the API fails here before a user sees it.
- The repository follows the conventions of openframe: English throughout, OpenSpec, mise, Renovate, GitHub Actions pinned to SHAs, Conventional Commits, release-please.

**Non-Goals:**
- Support for Home Assistant versions older than 2026.10.
- A YAML configuration; frames are added only through the UI.
- Using the signed image URLs of the API from the browser; all frame traffic goes through Home Assistant.

## Decisions

### 1. Repository layout and toolchain

`custom_components/openframe/` at the repository root (HACS requires it there), `tests/` beside it, `pyproject.toml` with `[tool.uv] package = false` and a dev group with `pytest-homeassistant-custom-component` pinned to the release that matches Home Assistant 2026.10, plus `ruff`. Python 3.14 and uv through `.mise.toml`, as in `ha-olight-sphere`. The integration has no runtime requirements: it uses Home Assistant's aiohttp session. The integration domain is `openframe`, `integration_type` `device`, `iot_class` `local_polling`, `config_flow` true.

*Alternative:* a subfolder of the openframe repository. Rejected by the user: HACS cannot install from a subfolder, and the release tags of openframe belong to the app.

### 2. API client

`api.py` holds `OpenframeClient(session, host, port, token=None)` with one method per endpoint, `base_url` with brackets for IPv6 literals, a 10-second timeout (60 seconds for sync, update check and install). Errors map to `OpenframeConnectionError` (no answer, not JSON), `OpenframeAuthError` (401) and `OpenframeResponseError(status, code, message, fields)`. The token never appears in an exception text or log line; the client's `repr` omits it. Dataclasses for the parts the entities read are not introduced: the coordinator keeps the JSON dicts as the contract defines them, and the contract tests keep them honest.

### 3. Config flow

Steps: `user` (host, port) → `GET /info`; `apiVersion` must be 1, otherwise `not_openframe`; `async_set_unique_id(info.id)` and abort if configured → `POST /pairing/code` → `pair` (six-digit code, with the frame's name in the description) → `POST /pairing` with `deviceName: "Home Assistant"` → `GET /slideshow` with the new token; 404 ends the flow with `outdated_frame` and revokes the new pairing with `DELETE /clients/{id}` so that no orphan stays on the frame → `async_create_entry(title=info.name, data={host, port, token, client_id})`.

Errors in `pair`: `invalid_code` (401 `invalid_code`), `expired_code` (401 `expired_code`; the flow requests a new code), `locked` (429). `reauth` → `reauth_confirm` asks the frame for a code and reuses the `pair` step; the frame at the stored address must have the entry's unique ID (`wrong_frame` otherwise); the token and client ID are replaced with `async_update_reload_and_abort`. `reconfigure` takes host and port, checks `GET /info` for the same ID and keeps the token. `async_remove_entry` sends `DELETE /clients/{client_id}` with a five-second timeout and ignores every error.

*Alternative:* pairing by the QR code's secret. Rejected: the secret is in the fragment of a URL the user would have to copy from a phone; typing six digits is simpler. *Alternative:* an invitation from the web UI pasted into Home Assistant. Possible later as a second path; not needed now.

### 4. One coordinator with three tiers

`OpenframeCoordinator(DataUpdateCoordinator[FrameData])` with `update_interval` 15 seconds:

```
every tick (15 s):     GET /state, GET /display, GET /slideshow
every 4th tick (60 s): GET /sources, GET /update        (every tick while a source syncs
                                                         or phase is checking/downloading/installing)
on a version change:   GET /settings, GET /albums, GET /info,
  or every 10 min      GET /photos?limit=1, GET /photos?visible=true&limit=1   (totals only)
```

`GET /slideshow` answering 503 `safe_mode` is not a failure: `FrameData.slideshow` becomes `None` and the slideshow entities become unavailable. A 401 anywhere raises `ConfigEntryAuthFailed`; other errors raise `UpdateFailed`, whose logging (once on loss, once on recovery) is the coordinator's own. After a command an entity calls `coordinator.async_set_updated_data` with the state the command returned (`POST /slideshow`, `PUT /display`, `PATCH /settings`, `PATCH /albums`), or `async_request_refresh` where the answer is not a full state; a settings or album change also forces the full tier on the next tick.

*Alternative:* one coordinator per tier. Rejected: entities would depend on several coordinators, and availability would need to be combined by hand. *Alternative:* reading everything every 15 seconds. Rejected: settings, albums, the photo totals and sources together are about eight requests, which the Frameo would serve every 15 seconds for no gain.

### 5. Image entity reads through the token

`CurrentPhoto(ImageEntity)` implements `async_image()` and fetches `GET /photos/{id}/image?size=display` with the token, so the image is the part of the photo the frame shows. `image_last_updated` changes when the photo ID or its `urls.display` changes (the display URL carries the image version and the key of the shown part), so Home Assistant's frontend reloads exactly then. The last bytes are cached per URL. The signed URL is not given to Home Assistant as `image_url`, because it expires after two hours and the frame is not reachable from outside the LAN.

### 6. Entities

All entities derive from `OpenframeEntity(CoordinatorEntity)` with `has_entity_name`, `translation_key` and `unique_id = f"{frame_id}_{key}"`. The device has `identifiers {(DOMAIN, frame_id)}`, `name` from the info, `manufacturer` "openframe", `model` "openframe", `sw_version` = `appVersion` of `/state` (updated in the device registry when it changes), `hw_version` = `Android {androidVersion}`, `configuration_url` = the frame's address.

| Platform | Keys |
|---|---|
| `switch` | `display`, `slideshow`, `clock`, `display_schedule`, `auto_update_check`, `album_<name>` (dynamic) |
| `button` | `next_photo`, `previous_photo`, `check_update`, `leave_safe_mode`, `sync_<source>` (dynamic) |
| `image` | `current_photo` |
| `sensor` | `current_photo`, `photos`, `photos_visible`, `photos_hidden`, `albums`, `last_sync_<source>` (dynamic, timestamp) |
| `binary_sensor` | `safe_mode` (problem), `transition_fallback` (problem, diagnostic), `sync_problem_<source>` (dynamic) |
| `number` | `interval` (5 to 86400 s, box), `transition_duration` (0 to 5000 ms, box) |
| `select` | `order`, `transition`, `fill_mode`, `orientation` |
| `update` | `app` |

Settings entities have `EntityCategory.CONFIG`; `check_update`, `transition_fallback` and the photo totals have `EntityCategory.DIAGNOSTIC`. Album switches use the album path in the unique ID and as translation placeholder; a path with `/` gets `entity_registry_enabled_default = False`. Dynamic entities are added by a listener on the coordinator that compares known keys with the current albums and sources; an entity whose album or source disappears reports itself unavailable and is not removed, so automations that reference it do not break silently. The update entity supports `INSTALL` and `RELEASE_NOTES` while `installAllowed` is true and `phase` is not `unsupported`; `in_progress` is true for `downloading` and `installing`; `release_notes()` returns `latest.notes` as plain text.

### 7. Contract tests

`tests/contract/openapi.yaml` is a copy of openframe's `api/openapi.yaml` at the tag in `tests/contract/OPENFRAME_VERSION`. `tests/fake_frame.py` is an `aiohttp` test server that implements the endpoints the integration uses with in-memory state, and validates every request and response against the copied contract with `openapi-core` (dev dependency). Config flow and entity tests run Home Assistant against the fake frame instead of mocking the client, so the client is tested too. A CI step downloads `api/openapi.yaml` at the pinned tag and fails if the copy differs. Renovate updates `OPENFRAME_VERSION` through a custom regex manager on openframe's GitHub releases; a workflow on Renovate's branches (like openframe's `renovate-artifacts`) downloads the matching contract and pushes it, so the pull request's tests run against the new contract.

*Alternative:* mocking responses with `aioclient_mock`. Rejected: mocks drift from the API without anyone noticing. *Alternative:* running openframe's real `:core` server in the tests. Rejected: it needs a JVM and a Gradle build in this repository's CI.

### 8. Releases and CI

release-please with `release-type: simple`, `version.txt`, and `custom_components/openframe/manifest.json` (`$.version`) as an extra file; releases are not drafts, because HACS ignores drafts. The owner merges the release pull request. `hacs.json` sets `name`, `homeassistant: "2026.10.0"` and `render_readme`. Workflows: `ci.yml` (ruff, pytest, the contract check), `validate.yml` (`home-assistant/actions/hassfest` and `hacs/action` with category `integration`), `pr-title.yml`, `release-please.yml`, `openspec-drift.yml`, `renovate-artifacts.yml` for the contract (decision 7). Every `uses:` is pinned to a commit SHA with a version comment, every checkout has `persist-credentials: false`. A `CLAUDE.md` states these rules and the private-data rules of openframe (no host names, IP addresses or real photo names).

## Risks / Trade-offs

- [The Frameo serves three requests every 15 seconds] → Each is a small JSON answer from memory; openframe's endurance run measures the server under the web UI's polling, which is heavier. A device row checks the CPU load with the integration running for a day.
- [A user adds the frame while its pairing code is locked] → The flow says to wait a minute; the frame's lockout is 60 seconds.
- [`pytest-homeassistant-custom-component` lags behind Home Assistant] → It is pinned and updated by Renovate; the minimum version in `hacs.json` changes only deliberately.
- [The frame's name changes in the web UI] → The device name stays what Home Assistant has (the user may have renamed it); the info is read again on the full tier, and the config entry title is not changed.
- [openframe changes an endpoint the integration uses in a breaking way] → openframe's API is versioned (`/api/v1`, `apiVersion`), and the contract update fails here first (decision 7).

## Migration Plan

New repository; nothing to migrate. Users of `pictureframe`'s integration remove it and add the frame again with openframe.
