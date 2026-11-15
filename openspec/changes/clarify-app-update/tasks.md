# Tasks

## 1. Fake frame

- [ ] 1.1 `tests/fake_frame.py`: a field `install_cooldown` that makes `POST /update/install` answer 409 `install_cooldown` after the checks that come first in openframe (`update_not_ready`, `install_not_allowed`); verify: a test in `tests/test_fake_frame.py`, and the response passes the contract check

## 2. Refused installation

- [ ] 2.1 `entity.py`: `install_cooldown` becomes `install_cooldown_unanswered`, `install_cooldown_cancelled` or `install_cooldown` by the code in the coordinator's `update["error"]` per design decision 1; the three texts in `en.json` and `de.json`; verify: tests for `frame-entities` › Refused installation › Dialog not confirmed, › Dialog cancelled and › Cause not reported, each checking the translation key of the raised error and that the frame shows no dialog

## 3. Update entity

- [ ] 3.1 `update.py`: title "openframe app" per design decision 3; verify: a test for › App update entity › Two updates named openframe that checks the attribute `title`
- [ ] 3.2 `update.py`: the sentence `install_confirm_on_frame` at the start of the release notes in Home Assistant's language, English as the fallback, per design decision 2; the sentence in `en.json` and `de.json`; verify: a test for › App update entity › Confirmation on the frame with `hass.config.language` set to `de`, and the existing test › Update ready adjusted to the English sentence before the fenced notes

## 4. Documentation

- [ ] 4.1 `README.md`: the row of the `app` update names the title "openframe app", the confirmation on the frame within 10 minutes, the 30-minute pause after a dialog that was cancelled or not confirmed, and "Install update" in the frame menu; verify: the README matches the texts in `en.json`

## 5. Devices

- [ ] 5.1 Rows in `../openframe-private/DEVICE_TEST.md` with their references: Settings › Updates and the update dialog on the owner's Home Assistant with the next openframe release (› App update entity › Two updates named openframe, › Confirmation on the frame), and an install request left unanswered, then a second request (› Refused installation › Dialog not confirmed); verify: the rows exist with their references
- [ ] 5.2 Run the rows of 5.1 after the release, asking before every persistent change on a frame or on the owner's Home Assistant; verify: results entered, and a finding in `../openframe-private/FINDINGS.md` for anything that differs

## 6. Integration

- [ ] 6.1 `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`, `node --test 'tests/frontend/*.test.mjs'`; verify: all green, including the translation key test
- [ ] 6.2 `openspec validate clarify-app-update`; verify: exit 0 without warnings

## Workflow follow-up

- The implementation's pull request title is `fix: name the cause of a refused installation and the app update's title`.
- Close findings 87 and 88 in `../openframe-private/FINDINGS.md` after 5.2, with the reason for the English message (the client's language, not the integration).
- Archive the change after the device rows.
