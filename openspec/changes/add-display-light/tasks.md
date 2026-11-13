# Tasks

## 1. Contract and fake frame

- [x] 1.1 Run `tools/update-contract.sh v0.6.0`; verify: `tests/contract/OPENFRAME_VERSION` reads `v0.6.0`, and `git diff --stat` shows only the two files in `tests/contract/`
- [x] 1.2 `tests/fake_frame.py` per design decision 6: `display["brightness"]` with switches for the permission, the light sensor and a dim period, `brightness` and `dimLevel`/`dim` in the settings, `PUT /display` with optional `on` and `brightness` and openframe's order of checks, 400 for `brightness.mode` in `PATCH /settings`; verify: `tests/test_fake_frame.py` covers each 409 and 400 and an empty body, and every existing test passes against the v0.6.0 contract

## 2. Minimum version

- [x] 2.1 `MIN_OPENFRAME_VERSION` `0.6.0`; the config flow reads `GET /display` after the slideshow and aborts with `outdated_frame` without `brightness`, revoking the pairing; the coordinator raises the repair issue on a display state without `brightness` (design decision 5); texts of the abort and the issue in `en.json` and `de.json`; verify: tests for `frame-connection` › Minimum frame version › Frame before the brightness and › Frame downgraded after setup with a fake frame whose display state lacks `brightness`, and that the issue goes away once it has it again

## 3. The light

- [x] 3.1 `api.py`: `set_display(on: bool | None = None, brightness: int | None = None)` that sends only the given fields; verify: a test against the fake frame for each of the three combinations
- [x] 3.2 `light.py` with `DisplayLight` per design decisions 2 and 3, platform `light` in `__init__.py`, `DisplaySwitch` removed from `switch.py`; translations of the light and its attributes `cause`, `next_change`, `dimmed`, `auto`, and the exception `brightness_unavailable`, in `en.json` and `de.json`; verify: tests for every scenario of `frame-entities` › Display light, › Brightness of the display light and › Errors of commands, and a test that every percent from 1 to 100 round-trips through the 1 to 255 scale
- [x] 3.3 Removal of the old switch's registry entry per design decision 1; verify: a test for › Former display switch › Update from a version with the switch, with a registry entry `switch.photo_frame_display` created before setup, and that a frame without such an entry sets up without error

## 4. Brightness settings

- [x] 4.1 `select.py` and `number.py` per design decision 4: `value`/`patch` lambdas for the existing descriptions, `brightness_mode` with its options rule, `dim_level`; translations of the select's options and both names in `en.json` and `de.json`; verify: tests for every scenario of › Brightness settings as configuration entities, and the existing tests of `tests/test_settings.py` (each setting sends only its field) pass for the new entities as well

## 5. Documentation

- [x] 5.1 `README.md`: minimum openframe 0.6.0 and the order "frames first, then the integration", the light and the two configuration entities in the entity table instead of the switch, the automation examples with `light.turn_off`/`light.turn_on` and one with `brightness_pct`, a note that `switch.<frame>_display` became `light.<frame>_display` and how to find automations, scripts and dashboards that use it; verify: every entity ID and service in the README exists in a test instance with the fake frame

## 6. Devices

- [x] 6.1 Rows in `../openframe-private/DEVICE_TEST.md` with their references: the light on and off and at 30 % from Home Assistant on both frames (`frame-entities` › Display light › Display off from an automation, › Brightness of the display light › Dim from an automation), the light in the evening while the schedule dims (› Dimmed by the schedule), the update from ha-openframe 0.1.0 on the owner's Home Assistant (› Former display switch › Update from a version with the switch); verify: the rows exist with their references
- [x] 6.2 Run the rows of 6.1; ask before any persistent change on a frame or on the owner's Home Assistant; verify: results entered, a finding in `../openframe-private/FINDINGS.md` for anything that differs

## 7. Integration

- [x] 7.1 `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`; verify: all green, including the translation key test
- [x] 7.2 `openspec validate add-display-light`; verify: exit 0 without warnings

## Workflow follow-up

- The implementation's pull request title is `feat!: replace the display switch with a light with brightness`, so the release notes mark the breaking change; with `bump-minor-pre-major` the release becomes 0.2.0.
- Close a Renovate pull request that raises `tests/contract/OPENFRAME_VERSION` to `v0.6.0` in favour of this change.
- After this change is merged: update `add-home-assistant-card` (`/opsx:update`) so that its display button toggles the light (`light.toggle`) and finds it by the translation key `display` in the domain `light`.
- Sync the delta specs and archive the change after review (`/opsx:archive`).
