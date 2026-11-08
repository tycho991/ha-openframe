# Tasks

## 1. Repository scaffold

- [x] 1.1 `pyproject.toml` (Python 3.14, `[tool.uv] package = false`, dev group with `pytest-homeassistant-custom-component` for Home Assistant 2026.10, `openapi-core`, `ruff`; pytest and ruff settings), `uv.lock`, `LICENSE` (MIT), `README.md` (install through HACS and by hand, pairing, entity table, minimum openframe and Home Assistant versions), `CLAUDE.md` with the rules of design decision 8; verify: `uv sync` succeeds and `uv run pytest` runs (no tests yet)
- [x] 1.2 `custom_components/openframe/manifest.json` (domain `openframe`, `config_flow`, `integration_type` `device`, `iot_class` `local_polling`, `version` `0.0.0`, documentation and issue tracker URLs), `const.py`, empty `__init__.py` with `async_setup_entry`/`async_unload_entry`, `hacs.json`, `version.txt`; verify: `uv run python -c "import json; json.load(open('custom_components/openframe/manifest.json'))"` succeeds
- [x] 1.3 `tests/contract/openapi.yaml` copied from openframe at the release that contains `/slideshow`, `tests/contract/OPENFRAME_VERSION` with that tag, `tools/update-contract.sh <tag>` that downloads both; verify: running the script with the pinned tag leaves `git diff` empty

## 2. Fake frame and API client

- [ ] 2.1 `tests/fake_frame.py`: aiohttp test server with in-memory state for `/info`, `/pairing`, `/pairing/code`, `/clients/{id}`, `/state`, `/display`, `/slideshow`, `/settings`, `/albums`, `/photos` (totals), `/photos/{id}/image`, `/sources`, `/sources/{id}/sync`, `/update`, `/update/check`, `/update/install`, `/safe-mode/exit`; every request and response validated with `openapi-core` against `tests/contract/openapi.yaml`; switches for safe mode, no device administrator, an outdated frame (404 on `/slideshow`), a revoked token and an unreachable frame; verify: a test sends a response with an extra field and sees the validation fail naming the field (`integration-distribution` › Contract with the openframe API › Response outside the contract)
- [ ] 2.2 `api.py` per design decision 2; verify: tests against the fake frame for every method, for 401 → `OpenframeAuthError`, a 409 with code and fields → `OpenframeResponseError`, a timeout and a non-JSON answer → `OpenframeConnectionError`, an IPv6 literal in `base_url`, and that no exception text or `repr` contains the token

## 3. Connection

- [ ] 3.1 Config flow steps `user` and `pair`, the outdated-frame check and revocation (design decision 3), translations of all errors in `translations/en.json` and `translations/de.json`; verify: tests for every scenario of "Adding a frame by its address", "Pairing with the code on the frame" and "Minimum frame version" in `frame-connection`
- [ ] 3.2 Re-authentication and reconfiguration flows and `async_remove_entry`; verify: tests for every scenario of "Re-authentication after a revoked pairing", "Changed address" and "Removing a frame"
- [ ] 3.3 `OpenframeCoordinator` with the three tiers of design decision 4, safe mode as `slideshow = None`, `ConfigEntryAuthFailed` on 401; verify: tests with a frozen clock for "Polling the frame" (request counts per tier on the fake frame, the full tier on a changed `settingsVersion`, the faster sources tier while syncing) and "Availability"
- [ ] 3.4 `diagnostics.py` with the token and client ID redacted; verify: test for "Token kept private" › "Diagnostics", and a test that the log of a failed setup does not contain the token

## 4. Entities

- [ ] 4.1 `entity.py` (base class and device info per design decision 6, `sw_version` following `appVersion`); verify: tests for "One device per frame"
- [ ] 4.2 `switch` (`display`, `slideshow`) and `button` (`next_photo`, `previous_photo`) with the state from the command's answer; verify: tests for every scenario of "Display switch", "Slideshow controls" and "Fresh state after a command"
- [ ] 4.3 `image` and `sensor` `current_photo` per design decision 5; verify: tests for every scenario of "Photo on screen", including that `image_last_updated` changes with a new section of the same photo and not on an unchanged poll
- [ ] 4.4 Settings entities: `number` (`interval`, `transition_duration`), `select` (`order`, `transition`, `fill_mode`, `orientation`), `switch` (`clock`, `display_schedule`, `auto_update_check`), each sending only its own field; verify: tests for every scenario of "Settings as configuration entities", checking the request body on the fake frame
- [ ] 4.5 Library: photo total sensors, album count, dynamic album switches; verify: tests for "Photo counts" and every scenario of "One switch per album", including a removed album becoming unavailable
- [ ] 4.6 Sources: dynamic sync buttons, last sync sensors and problem sensors; verify: tests for every scenario of "Remote sources"
- [ ] 4.7 `update` entity and `check_update` button; verify: tests for every scenario of "App update entity" and "Checking for an update", including `in_progress` while `downloading`
- [ ] 4.8 Health: `safe_mode` and `transition_fallback` binary sensors, `leave_safe_mode` button; translated `HomeAssistantError`s for refused and unanswered commands; verify: tests for every scenario of "Health of the frame" and "Errors of commands"
- [ ] 4.9 Complete the entity table and the automation examples in `README.md`; verify: every entity key of design decision 6 appears in the table, and both translation files have the same keys (a test)

## 5. CI, releases, dependencies

- [ ] 5.1 Workflows `ci.yml` (ruff check, ruff format check, pytest, contract copy equals the pinned tag), `validate.yml` (hassfest, HACS action), `pr-title.yml` (`openspec-drift.yml` exists from the template), all `uses:` pinned to SHAs with version comments and checkouts with `persist-credentials: false`; verify: `uv run ruff check`, `uv run ruff format --check` and `uv run pytest` pass locally, and `actionlint` (if available) reports nothing
- [ ] 5.2 `release-please-config.json` and `.release-please-manifest.json` with `manifest.json` as extra file and non-draft releases, `release-please.yml`; verify: the config validates against release-please's schema and names `custom_components/openframe/manifest.json`
- [ ] 5.3 `renovate.json` with the pip/uv, GitHub Actions and mise managers and the custom regex manager for `OPENFRAME_VERSION`; `renovate-artifacts.yml` that runs `tools/update-contract.sh` on Renovate's branches and pushes the contract; verify: `npx --yes --package renovate -- renovate-config-validator` passes

## 6. Devices

- [ ] 6.1 Rows in `../openframe-private/DEVICE_TEST.md` with their references: pairing and the entities against both frames (`frame-connection` › Pairing with the code on the frame › Correct code), the display switch on the Frameo (`frame-entities` › Display switch › Display off from an automation), next photo from Home Assistant (`frame-entities` › Slideshow controls › Previous photo), revoked pairing (`frame-connection` › Re-authentication after a revoked pairing), and the CPU load of the Frameo over a day with the integration polling (design, Risks); verify: the rows exist with their references
- [ ] 6.2 Run the rows of 6.1 with a Home Assistant test instance; ask before any persistent change on a device; verify: results entered, a finding in `../openframe-private/FINDINGS.md` for anything that differs

## 7. Integration

- [ ] 7.1 `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`; verify: all green
- [ ] 7.2 `openspec validate add-home-assistant-integration`; verify: exit 0 without warnings

## Workflow follow-up

- Implement after openframe's `add-slideshow-control-api` is released; pin its tag in `tests/contract/OPENFRAME_VERSION`.
- `tycho991/ha-openframe` exists as a public repository with openframe's merge settings (squash only, PR title as subject, head branches deleted).
- Archive the change after the device rows of 6.1 are done; then `add-home-assistant-card` can start.
