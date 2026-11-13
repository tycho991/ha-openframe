# Design

## Context

The display is `DisplaySwitch` in `switch.py`, unique ID `<frame id>_display`, translation key `display`, available while `display.available` (device administrator), with the attributes `cause` and `next_change`. The coordinator reads `GET /display` every 15 seconds and the settings when `settingsVersion` in `GET /state` changes; `set_display` and `set_settings` put a command's answer into the data at once. `MIN_OPENFRAME_VERSION` is `0.5.0`; an outdated frame is recognised only by a 404, in the config flow (`GET /slideshow`) and in the coordinator (any read), with the abort `outdated_frame` and the repair issue `outdated_frame`. `tests/contract/` is pinned to `v0.5.0`, and `tests/fake_frame.py` checks every request and answer against it.

openframe 0.6.0 (see its change `add-display-brightness`) adds to `GET /display` a required `brightness` object (`available`, `autoSupported`, `level` 0 to 100, `auto`, `dimmed`); `PUT /display` takes `on` and/or `brightness` (1 to 100) with `minProperties: 1`, checks the whole body first, answers 409 `display_unavailable` before `brightness_unavailable`, and a brightness outside a dim period becomes the setting `brightness` with mode `manual`. The settings gain `brightness` (`mode` `system`/`manual`/`auto`, `level`) and `displaySchedule.dimLevel` and `dim` per window; a patch of mode `manual` or `auto` without the permission, or `auto` without a light sensor, is refused with 400 naming `brightness.mode`. See proposal.md for why.

## Goals / Non-Goals

**Goals:**
- One entity for the display that Home Assistant's light card, light groups, scenes and voice assistants understand.
- No state in the integration beyond what the frame reports: the light shows the frame's brightness, not the last value sent.

**Non-Goals:**
- Keeping `switch.<frame>_display` as an alias or a deprecated entity.
- Talking to frames before 0.6.0 with a reduced light.

## Decisions

### 1. A light with the unique ID of the switch, the switch removed from the registry

`light.py` adds `DisplayLight(OpenframeEntity, LightEntity)` with key and translation key `display`, so its unique ID stays `<frame id>_display`; the entity registry keys entries by domain, platform and unique ID, so the light and the old switch entry do not clash. `async_setup_entry` of the light platform looks up `("switch", DOMAIN, "<frame id>_display")` in the entity registry and removes it if present, before adding the light. Home Assistant cannot move an entity between domains, so a name, area or icon the user gave the switch is lost; the README says so.

*Alternative:* keep the switch for one release with a repair issue that points to the light. Rejected by the owner: ha-openframe 0.1.0 has few installations, and two entities for one display confuse scenes and voice assistants.

### 2. Colour modes, brightness scale and state

- `supported_color_modes` is `{BRIGHTNESS}` while `brightness.available`, else `{ONOFF}`; `color_mode` follows. Home Assistant reads both as state attributes on each update, so granting or withdrawing the permission on the frame shows within one tick.
- `is_on` is `display.on`. `brightness` is `None` while the display is off or in mode `ONOFF`; otherwise `max(1, round(level * 255 / 100))`, so a reported level of 0 (Android's raw value 0) does not read as off.
- A brightness sent by Home Assistant (1 to 255, or `brightness_pct` that Home Assistant converts) becomes `max(1, round(brightness * 100 / 255))`.
- Attributes: `cause`, `next_change` as before, `dimmed` and `auto` from `brightness`; translated like `cause`.

### 3. Turning on and off

- `async_turn_off` sends `{"on": false}`.
- `async_turn_on(brightness=b)` sends one `PUT /display`: `"on": true` when `display.available` or no brightness was given, and `"brightness": <percent>` when a brightness was given. So a frame without device administrator but with the permission can still be dimmed, and a plain turn on keeps today's behaviour, including the 409 `display_unavailable`. A brightness while the light is in mode `ONOFF` does not reach the integration: Home Assistant drops attributes of unsupported colour modes.
- `available` is `super().available and (display.available or brightness.available)`.
- The answer of `PUT /display` goes into the data with `set_display`. Because a brightness outside a dim period changes the settings, the light then calls `request_full()` so the brightness mode select shows `manual` on the next tick instead of after up to 15 seconds plus the settings check.

*Alternative:* available only while `display.available`, as the switch. Rejected: it hides the brightness on a frame that has the permission but no device administration, although openframe allows that combination.

### 4. Brightness mode and dim level

- `select.py` gains `brightness_mode` (category config) with the options `system`, `manual`, `auto`, translated as "Android's setting", "Fixed level", "Automatic". `auto` is in `options` only while `brightness.autoSupported` is true or the stored mode is `auto`, so the current option is always offered. A choice sends `{"brightness": {"mode": <option>}}`; a 400 from the frame becomes the existing `refused` error with the frame's message.
- `number.py` gains `dim_level` (category config, 1 to 100, step 1, `%`, mode slider) from `displaySchedule.dimLevel`, sent as `{"displaySchedule": {"dimLevel": <value>}}`.
- `SettingNumberDescription` and `SettingSelectDescription` carry a flat `field` today. They gain `value` and `patch` lambdas like `SettingSwitchDescription`, with the flat fields expressed through them, so each entity still sends only its own field, nested or not. The select's options become a lambda of the frame data for the `auto` rule above.

*Alternative:* a number for the fixed level and time entities for the dim times. Rejected with the owner: the light sets the level, and the dim times belong with the on and off times in the frame's web UI.

### 5. Recognising a frame before 0.6.0 by the missing field

- The config flow reads `GET /display` after `GET /slideshow` in `_finish_pairing`; an answer without `brightness` revokes the new pairing and aborts with `outdated_frame`, like a 404.
- The coordinator checks the display answer on each tick: without `brightness` it sets the repair issue and raises `UpdateFailed`, as for a 404; with it the issue is removed.
- `MIN_OPENFRAME_VERSION` becomes `0.6.0`. The texts of the abort and the repair issue say that the frame lacks something the integration needs, instead of naming an endpoint.

*Alternative:* compare `appVersion` from `GET /state` with 0.6.0. Rejected: development builds carry other version names, and the field is what the integration actually needs.

### 6. Contract and fake frame at v0.6.0

`tools/update-contract.sh v0.6.0` replaces `tests/contract/`. The fake frame gains `display["brightness"]` with all five fields and a switch for the permission and the light sensor, `brightness` and `dimLevel`/`dim` in its settings, `PUT /display` with the order of checks of openframe (body, then 409 `display_unavailable`, then 409 `brightness_unavailable`, then acting; a brightness sets the level and mode `manual` unless the fake is told it is in a dim period), and the 400 for `brightness.mode` in `PATCH /settings`. Its answers are checked against the new contract like all others.

If Renovate opens its own pull request that raises `OPENFRAME_VERSION` to `v0.6.0`, it fails against the old fake frame; it is closed in favour of this change.

## Risks / Trade-offs

- [Automations that use `switch.<frame>_display` break after the update] → The changelog marks the change as breaking (`feat!:`), and the README names the new entity ID and the search for the old one in automations, scripts and dashboards.
- [`supported_color_modes` changes while Home Assistant runs, which some frontends cache] → It changes only when the permission is granted or withdrawn on the frame; the light card picks it up on the next state update.
- [Rounding between 1 to 255 and 1 to 100 makes a sent value come back slightly different] → The mapping in both directions is tested for every percent from 1 to 100 to round-trip exactly.
- [A frame on 0.5.0 loses its entities until it is updated, including the update entity that could install 0.6.0] → The repair issue names openframe 0.6.0; the frame finds the new version by its automatic update check, and its web UI installs it.

## Migration Plan

Frames are updated to openframe 0.6.0 first, which ha-openframe 0.1.0's update entity can still do; ha-openframe 0.1.0 works with 0.6.0 because the new fields are additive. Then users update the integration through HACS and restart Home Assistant; the switch disappears and the light appears with the same device. The README states this order. Rollback: installing ha-openframe 0.1.0 again brings back the switch (its registry entry is created anew) and leaves the light as an orphaned entity that the user can remove.
