# Tasks

## 1. Integration side

- [ ] 1.1 Image entity attributes `screen_width` and `screen_height` per design decision 3; `GET /info` on the full tier if not yet there; verify: tests for every scenario of "Screen format of the frame" in this change's `frame-entities` delta against the fake frame
- [ ] 1.2 Static path and extra JS URL in `async_setup` per design decision 2, `frontend` and `http` in the manifest's dependencies; verify: a test that the URL is registered once with the manifest's version after setting up two frames, and that `GET /openframe_static/openframe-card.js` answers 200

## 2. Card model

- [ ] 2.1 `frontend/model.js` with `findEntities`, `cardState` and `strings` per design decision 1; verify: `node --test tests/frontend/` with recorded `hass` objects for every scenario of "Photo in the frame's shape", "States on the card", "Caption on the card" and "Languages and themes" › "German user", for the device of another integration, for an unavailable display light, and for the fallback without `translation_key`
- [ ] 2.2 `ci.yml` runs `node --test tests/frontend/`; verify: the job passes locally with `mise exec -- node --test tests/frontend/`

## 3. Card view and editor

- [ ] 3.1 `frontend/openframe-card.js`: the view per design decisions 1, 4 and 5, registration in `window.customCards`, `getStubConfig`, `getCardSize`, `getGridOptions`; verify: in a Home Assistant test instance with the fake frame or a real frame, every scenario of "Card loads by itself", "Controls on the card" and "Card on a phone" (browser width 360 pixels) holds, recorded with a screenshot per scenario in the pull request
- [ ] 3.2 `openframe-card-editor` with a device picker limited to the integration `openframe`, title and caption switch; verify: every scenario of "Choosing the frame" holds in the test instance, including the YAML options
- [ ] 3.3 `README.md`: the card, a screenshot and its YAML options; verify: the YAML example in the README renders the card in the test instance

## 4. Devices

- [ ] 4.1 Rows in `../openframe-private/DEVICE_TEST.md` with their references: the card on a phone while the frame changes photos (`dashboard-card` › Photo in the frame's shape › Landscape frame), display off and on from the card on the Frameo (`dashboard-card` › Controls on the card › Display on from the card); verify: the rows exist with their references
- [ ] 4.2 Run the rows of 4.1; ask before any persistent change on a device; verify: results entered, a finding in `../openframe-private/FINDINGS.md` for anything that differs

## 5. Integration

- [ ] 5.1 `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`, `node --test tests/frontend/`; verify: all green
- [ ] 5.2 `openspec validate add-home-assistant-card`; verify: exit 0 without warnings

## Workflow follow-up

- Start after `add-home-assistant-integration` is archived, so that `frame-entities` exists as a main spec.
- Archive the change after the device rows of 4.1 are done; `add-home-assistant-photo-management` builds on the card.
