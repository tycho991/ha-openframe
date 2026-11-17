# Design

## Context

See proposal.md for the motivation. What is in place:

- `AppUpdate` in `update.py` has `_attr_title = "openframe"`. Its release notes are the frame's notes, fenced as
  plain text (`async_release_notes`).
- `OpenframeEntity.command` turns a refusal whose code is in `KNOWN_REFUSALS` into a `HomeAssistantError` with that
  code as its translation key. `install_cooldown` maps to the single text "An installation was just cancelled. Try
  again in a few minutes."
- openframe refuses client install requests with 409 `install_cooldown` for 30 minutes after a dialog was cancelled
  or left unanswered (`app-update` › Pause after a declined dialog). An unanswered dialog is discarded after
  10 minutes. Either way the update state reports it in `error.code`: `install_unanswered` or `install_cancelled`. The
  entry "Install update …" in the frame menu stays available.
- Home Assistant's frontend shows an integration's error in the user's language. It translates the error's
  `translation_domain` and `translation_key` with `loadBackendTranslation("exceptions", …)`, both in the toast of
  `hass.callService` and in the update dialog (`_localizeInstallError`). The backend's own message is always English.
- The update dialog of Home Assistant 2026.11 does not show the attribute `release_summary`. It shows the release
  notes.

## Goals / Non-Goals

**Goals:**

- The refusal says why the frame refuses, how long, and how to install anyway.
- Someone who installs from Home Assistant knows before pressing "Install" that the frame asks for a confirmation.
- The frame's app update and the integration's update cannot be mistaken for each other in Settings › Updates.

**Non-Goals:**

- The remaining minutes of the cooldown (the frame does not report them).
- A change in openframe or in the contract.

## Decisions

### 1. The cooldown message follows the frame's last update error

When `install_cooldown` comes back, `command` reads `coordinator.data.update["error"]` and raises one of three
translation keys:

- `install_cooldown_unanswered` if the code is `install_unanswered`: "Nobody confirmed the installation dialog on the
  frame within 10 minutes. Home Assistant can ask again 30 minutes after that; on the frame, "Install update" in the
  frame menu installs at once."
- `install_cooldown_cancelled` if the code is `install_cancelled`: "The installation was cancelled on the frame. Home
  Assistant can ask again 30 minutes after that; on the frame, "Install update" in the frame menu installs at once."
- `install_cooldown` otherwise: the same, opening with "The last installation dialog on the frame was cancelled or not
  confirmed."

The state comes from the coordinator's last poll. A dialog is discarded 10 minutes after the request, and the
coordinator polls the update state every minute. So by the time a cooldown can be hit, the poll has almost always
seen the error. The generic text covers the rest, and a later check that clears the error.

The specific part lives in `entity.py` next to the other refusals, as a small mapping from the error code to the
key. `KNOWN_REFUSALS` keeps `install_cooldown`.

- *Alternative:* one text that names both causes. Rejected: finding 87 came from a message that named the wrong
  cause, and the frame tells us the right one.

### 2. The sentence about confirming on the frame opens the release notes

`async_release_notes` returns the sentence, a blank line and then the fenced notes as today: "Installing opens a
dialog on the frame's screen: confirm it there within 10 minutes." The sentence is in Home Assistant's language
(`hass.config.language`). It is stored in the translations under `exceptions.install_confirm_on_frame` and read with
`translation.async_get_translations(hass, language, "exceptions", {DOMAIN})`, with English as the fallback.

- *Alternative:* `release_summary`. Rejected: the update dialog of Home Assistant 2026.11 does not show it.
- *Alternative:* an English constant. Rejected: every other text of the integration is translated, and the owner
  uses German.
- *Why the `exceptions` section:* hassfest allows only its fixed sections in the translation files, and `exceptions`
  is the one that holds free sentences with a `message`. The release notes come from a websocket call that does not
  know the user's language, so the backend has to pick one. The system language is the closest.

### 3. The title is "openframe app"

`_attr_title = "openframe app"`. Settings › Updates shows the device name as the headline and "‹area› · ‹title›
‹version›" below it. That gives "openframe app 0.7.0" under the frame's name, next to the integration's
"openframe 0.3.1". The title is a name, so it stays untranslated, as Home Assistant's own titles ("Home Assistant
Core") are.

- *Alternative:* no title, so that only the device name shows. Rejected: the row would show the version alone,
  without saying what it is the version of.

### 4. The language of errors stays with the frontend

No change. The test that `en.json` and `de.json` have the same keys covers the new keys.

## Risks / Trade-offs

- [The poll has not seen the error yet] → The generic text, which is still correct.
- [A future Home Assistant shows `release_summary` again] → Moving the sentence there is a small follow-up; the
  release notes stay right in the meantime.
- [Automations that compare the title] → Unlikely. The title is display text, not the entity ID or state.

## Migration Plan

None. The texts change with the update of the integration.
