# ha-openframe

Home Assistant integration for [openframe](https://github.com/tycho991/openframe) picture frames.
Each frame becomes one device whose entities show and control the display, the slideshow, the
photo on screen, the settings that are useful in automations, the library and the frame's health.
All traffic stays on the local network: Home Assistant polls the frame.

## Requirements

- Home Assistant 2026.10 or later.
- openframe 0.5.0 or later on the frame. Older frames lack the slideshow API and are refused
  during setup.

## Installation

### HACS

1. In HACS, open the menu › Custom repositories, add `https://github.com/tycho991/ha-openframe`
   with the type Integration.
2. Download "openframe" and restart Home Assistant.

### By hand

Copy `custom_components/openframe` from a release into the `custom_components` folder of your
Home Assistant configuration and restart Home Assistant.

## Adding a frame

1. Settings › Devices & services › Add integration › openframe.
2. Enter the frame's IP address or host name and its port (8080 unless changed).
3. The frame shows a six-digit pairing code. Type it into Home Assistant.

The frame lists Home Assistant as a paired device named "Home Assistant" in its web UI. If the
pairing is revoked there, Home Assistant asks to pair again. If the frame gets a new IP address,
use Reconfigure on the frame's entry; no new pairing is needed. Removing the frame from Home
Assistant revokes its pairing on the frame.

## Entities

Entity IDs follow the frame's name, for example `switch.photo_frame_display` for a frame named
"Photo frame". The key is the end of each entity's unique ID.

| Key | Platform | What it does |
|---|---|---|
| `display` | switch | Display on or off; attributes `cause` (`schedule`, `manual`, `wake`, `none`) and `next_change`. Unavailable while openframe is not a device administrator. |
| `slideshow` | switch | On while the slideshow plays, off while it is paused. |
| `next_photo`, `previous_photo` | button | Step through the slideshow. Fails while the display is off. |
| `current_photo` | image | The photo as the frame shows it. |
| `current_photo` | sensor | Comment of the photo, or its file name; attributes `album`, `taken_at`, `place`, `photo_id`. |
| `interval` | number | Seconds per photo (5 to 86400). |
| `transition_duration` | number | Milliseconds (0 to 5000). |
| `order` | select | `shuffle`, `chronological`. |
| `transition` | select | `fade`, `slide`, `none`. |
| `fill_mode` | select | `auto`, `fill`, `fit`. |
| `orientation` | select | `landscape`, `portrait`. |
| `clock` | switch | Clock on the frame on or off. |
| `display_schedule` | switch | Display schedule on or off; its times are set in the web UI. Unavailable while openframe is not a device administrator. |
| `auto_update_check` | switch | The frame checks for a new version by itself. |
| `photos`, `photos_visible`, `photos_hidden` | sensor | Photo totals (diagnostic). |
| `albums` | sensor | Number of albums. |
| `album_<name>` | switch | On while the album is shown, attribute `photos`. One per album; sub-albums are disabled by default. |
| `sync_<source>` | button | Start a sync of a remote source. |
| `last_sync_<source>` | sensor | Time of the last sync; attributes `added`, `updated`, `removed`. |
| `sync_problem_<source>` | binary_sensor | On while the last sync failed; attribute `error`. |
| `app` | update | Installed and latest openframe version with release notes; installing opens Android's installation dialog on the frame, which someone confirms there. |
| `check_update` | button | Ask the frame to check for an update now (diagnostic). |
| `safe_mode` | binary_sensor | On while the frame runs in safe mode after repeated crashes. |
| `leave_safe_mode` | button | Start the frame normally again; available only in safe mode. |
| `transition_fallback` | binary_sensor | On while the frame changes photos instantly because its display could not keep up (diagnostic). |

A new album or source gets its entities within 15 seconds. The entities of a removed album or
source stay and are unavailable, so automations that use them do not break silently; delete them
on the device page when they are no longer needed.

## Automation examples

Display off when nobody is home, on again when someone comes back:

```yaml
automation:
  - alias: Frame off when away
    triggers:
      - trigger: state
        entity_id: zone.home
        to: "0"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.photo_frame_display
  - alias: Frame on when back
    triggers:
      - trigger: numeric_state
        entity_id: zone.home
        above: 0
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.photo_frame_display
```

Pause the slideshow while the TV runs:

```yaml
automation:
  - alias: Pause the frame while the TV runs
    triggers:
      - trigger: state
        entity_id: media_player.tv
    actions:
      - action: >-
          {{ 'switch.turn_off' if trigger.to_state.state == 'playing' else 'switch.turn_on' }}
        target:
          entity_id: switch.photo_frame_slideshow
```

Next photo with a button on the wall:

```yaml
automation:
  - alias: Next photo
    triggers:
      - trigger: event
        event_type: zha_event
        event_data:
          command: single
    actions:
      - action: button.press
        target:
          entity_id: button.photo_frame_next_photo
```

## Development

```bash
mise trust && mise install
uv sync
uv run pytest
```

[mise](https://mise.jdx.dev) pins Node, OpenSpec, Python and uv (`.mise.toml`). After Renovate
raises the OpenSpec version, run `mise run openspec-sync` on its branch and commit the
regenerated skills; the `openspec-drift` check fails until then.

The tests run Home Assistant against a fake frame (`tests/fake_frame.py`) that checks every
request and response against openframe's API contract in `tests/contract/`, pinned to the openframe
release in `tests/contract/OPENFRAME_VERSION`. `tools/update-contract.sh <tag>` downloads another
release's contract.

Changes follow OpenSpec: `/opsx:propose`, `openspec validate <change>`, `/opsx:apply`,
`/opsx:archive`.

## License

MIT, see [LICENSE](LICENSE).
