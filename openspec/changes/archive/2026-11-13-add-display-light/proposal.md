# Proposal

## Why

openframe 0.6.0 can set the brightness of a frame's display, through `PUT /display` and the settings, and the display schedule can dim it in the evening. In Home Assistant the display is still a switch, so a frame cannot be dimmed like a lamp, cannot join a light group or a scene, and the brightness mode and the dim level cannot be used in automations. openframe's change `add-display-brightness` was made for this follow-up.

## What Changes

- **BREAKING: The display becomes a light.** The switch `display` is replaced by a light `display` with on/off and brightness: turning it on or off switches the display, a brightness sets it at once as openframe's `PUT /display` does. Its entity ID changes from `switch.<frame>_display` to `light.<frame>_display`; the integration removes the old switch, and automations that use it have to be changed.
- **What the light reports.** Its brightness is Android's brightness as the frame reports it. As attributes it keeps the reason and the next change, and adds whether the schedule dims at the moment and whether Android's automatic brightness is on. While the frame may not modify system settings, the light switches only on and off.
- **Brightness settings as configuration entities.** A select for the brightness mode (Android's setting, a fixed level, automatic; automatic only on a frame with a light sensor) and a number for the schedule's dim level.
- **Minimum openframe version 0.6.0.** A frame on an older openframe, which reports no brightness, is refused during setup and gets a repair issue once added, as a frame without the slideshow API does today.
- **Contract at openframe v0.6.0.** `tests/contract/` moves to the tag `v0.6.0`; the fake frame gains the brightness in the display state and the settings, the brightness in `PUT /display` and the conflict `brightness_unavailable`.
- Texts in English and German, the README's entity table and its automation examples.

### Out of scope

- The dim times of the schedule's windows and the level of the mode "fixed level" as entities: the dim times stay in the frame's web UI like the on and off times, and the light sets the level.
- Colour or colour temperature: the display has none.
- A transition (`transition` of `light.turn_on`): openframe sets the brightness at once.
- Supporting frames before openframe 0.6.0.
- The card (`add-home-assistant-card`): its display button is moved to the light by updating that change, not here.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frame-entities`: the display switch becomes a light with brightness and the new attributes, the old switch is removed, the brightness mode and dim level are configuration entities, and the error example names the light.
- `frame-connection`: the minimum frame version also covers a frame that lacks a field the integration needs, and names openframe 0.6.0.

## Impact

- `custom_components/openframe/`: new `light.py` (the light replaces `DisplaySwitch` in `switch.py`), the platform `light` in `__init__.py`, removal of the old switch's registry entry, `set_display` in `api.py` with optional `on` and `brightness`, the brightness mode in `select.py`, the dim level in `number.py`, the version check in `config_flow.py` and `coordinator.py`, `MIN_OPENFRAME_VERSION` in `const.py`, `translations/en.json` and `de.json` (light, attributes, select, number, `brightness_unavailable`, the outdated texts).
- `tests/contract/`: `openapi.yaml` and `OPENFRAME_VERSION` at `v0.6.0`; `tests/fake_frame.py` and the tests of the display, the settings, the config flow and the coordinator.
- `README.md`: the entity table, the automation examples (`light.turn_off` instead of `switch.turn_off`), the minimum openframe version, a note on the replaced switch.
- Users: automations, scripts and dashboards that use `switch.<frame>_display` must use `light.<frame>_display`; frames must run openframe 0.6.0 or later.
- `../openframe-private/DEVICE_TEST.md`: rows for the light against a real frame.
- `add-home-assistant-card`: its display button has to toggle the light; that change is updated after this one.
