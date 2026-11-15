# Proposal

## Why

Two things about the frame's app update confused the owner in Home Assistant:

- An install request from Home Assistant opens a dialog on the frame, but nothing in Home Assistant says so. Nobody
  was at the frame, so the frame discarded the dialog after 10 minutes and refused further requests for 30 minutes, as
  openframe specifies. Home Assistant then showed "An installation was just cancelled. Try again in a few minutes."
  That message was wrong in two ways. Nobody had cancelled anything, and it gave neither the 30 minutes nor the way to
  install at once from the frame menu.
- In Settings › Updates the frame's app update and the integration's own update from the Marketplace are both titled
  "openframe". With an integration update waiting and the frames offering a newer app, the owner read the app's
  version as the integration's.

## What Changes

- **The install refusal names its cause.** When the frame refuses an install request with `install_cooldown`, the
  error message says what happened, taken from the update state the frame reports:
  - the dialog went unanswered for 10 minutes, or it was cancelled on the frame, or, if the state names neither,
    one of the two;
  - Home Assistant can ask again 30 minutes later;
  - the frame menu on the frame installs at once.
- **The update tells you to confirm on the frame.** The release notes of the app update start with one sentence:
  installing opens a dialog on the frame's screen, which has to be confirmed there within 10 minutes. The sentence is
  in Home Assistant's language. The frame's own notes follow as today.
- **The app update gets its own title.** The update entity's title becomes "openframe app". Settings › Updates then
  lists it as "openframe app 0.7.0" under the frame's name, and the integration stays "openframe".

### Out of scope

- The language of error messages. Home Assistant's frontend translates an integration's error messages into the
  language of the browser or app that shows them. `de.json` already has every message, and a test keeps `en.json` and
  `de.json` in step. The English message the owner saw came from a client set to English, so no change in the
  integration can affect it.
- The remaining time of the 30 minutes: the frame does not report it.
- Changing the cooldown or the 10-minute deadline: both belong to openframe (`app-update` › Unanswered dialog,
  › Pause after a declined dialog).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frame-entities`: "App update entity" gains the title and the sentence about confirming on the frame. A new
  requirement "Refused installation" covers the message for `install_cooldown`.

## Impact

- `custom_components/openframe/update.py`: the title, the sentence at the start of the release notes, and the
  translation it reads.
- `custom_components/openframe/entity.py`: `install_cooldown` maps to one of three messages, depending on the
  frame's last update error.
- `custom_components/openframe/translations/en.json` and `de.json`: three cooldown messages instead of one, and the
  sentence about confirming on the frame.
- `tests/fake_frame.py`: a switch that makes `POST /update/install` answer 409 `install_cooldown`, as the frame does
  for 30 minutes after a declined dialog.
- `tests/test_update.py`: the title, the release notes, and the three refusals.
- `README.md`: the update section names the dialog on the frame and the 30 minutes.
- No change to the contract, the card or openframe.
