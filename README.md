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

| Entity | Platform | What it does |
|---|---|---|
| Display | switch | Display on or off; attributes `cause` (`schedule`, `manual`, `wake`, `none`) and `next_change`. Unavailable while openframe is not a device administrator. |
| Slideshow | switch | On while the slideshow plays, off while it is paused. |
| Next photo, Previous photo | button | Step through the slideshow. Fails while the display is off. |
| Photo on screen | image | The photo as the frame shows it. |
| Photo on screen | sensor | Comment of the photo, or its file name; attributes `album`, `taken_at`, `place`, `photo_id`. |
| Interval | number | Seconds per photo (5 to 86400). |
| Transition duration | number | Milliseconds (0 to 5000). |
| Order | select | `shuffle`, `chronological`. |
| Transition | select | `fade`, `slide`, `none`. |
| Fill mode | select | `auto`, `fill`, `fit`. |
| Orientation | select | `landscape`, `portrait`. |
| Clock | switch | Clock on the frame on or off. |
| Display schedule | switch | Display schedule on or off; its times are set in the web UI. |
| Automatic update check | switch | The frame checks for a new version by itself. |
| Photos, Visible photos, Hidden photos | sensor | Photo totals (diagnostic). |
| Albums | sensor | Number of albums. |
| Album *name* | switch | On while the album is shown, attribute `photos`. Sub-albums are disabled by default. |
| Sync *source* | button | Start a sync of a remote source. |
| Last sync *source* | sensor | Time of the last sync; attributes `added`, `updated`, `removed`. |
| Sync problem *source* | binary_sensor | On while the last sync failed; attribute `error`. |
| App | update | Installed and latest openframe version with release notes; installing opens Android's installation dialog on the frame. |
| Check for update | button | Ask the frame to check for an update now (diagnostic). |
| Safe mode | binary_sensor | On while the frame runs in safe mode after repeated crashes. |
| Leave safe mode | button | Start the frame normally again; available only in safe mode. |
| Transition fallback | binary_sensor | On while the frame changes photos instantly because its display could not keep up (diagnostic). |

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
