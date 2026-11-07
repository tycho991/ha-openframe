# Tasks

## 1. Contract and client

- [ ] 1.1 `tools/update-contract.sh` also copies `api/fixtures/presentation-cases.json` to `tests/contract/`; the CI contract check compares it too; verify: running the script with the pinned tag leaves `git diff` empty, and the CI step fails on an edited copy
- [ ] 1.2 Fake frame: `PATCH`/`DELETE /photos/{id}`, `POST /photos` (multipart, 415, 507), `GET /photos` pages with `album`, `subalbums`, `visible`, `cursor`, `PATCH /albums`, `GET /photos/{id}/image` with `ETag`/`If-None-Match`; client methods for them; verify: client tests for each method against the fake frame, all requests and responses validated against the contract

## 2. Photo actions

- [ ] 2.1 `services.py` and `services.yaml` per design decisions 1 and 2, translations in `en.json` and `de.json`, registered as admin services in `async_setup`; verify: tests for every scenario of "Target of a photo action", "Photo on screen by default", "Photo actions for administrators" and "Responses of photo actions" in `photo-actions`
- [ ] 2.2 `set_photo_hidden`, `set_photo_comment`, `set_photo_crop`, `delete_photo`, `set_album_hidden` with the error mapping of design decision 1 and the forced full tier; verify: tests for every scenario of "Hiding and showing a photo", "Comment of a photo", "Section of a photo", "Deleting a photo", "Hiding an album" and "Fresh entities after a photo action"
- [ ] 2.3 `upload_photo` with the path check and executor reads; verify: tests for every scenario of "Uploading photos", including that the fake frame receives no request for a refused path
- [ ] 2.4 `README.md`: the actions with automation examples (hide the photo on screen from a button, snapshot of a doorbell camera to an album); verify: each example passes Home Assistant's config check in a test instance

## 3. Image proxy and media browser

- [ ] 3.1 `OpenframeImageView` per design decision 3; verify: tests that a request without session or signature gets 401 without a request to the fake frame, that a signed URL works until it expires, that `ETag`, `Cache-Control` and 304 pass through, and that a `size` other than `thumb` or `full` and a malformed photo ID get 400 (`media-browser` › Photos only for signed-in users)
- [ ] 3.2 `media_source.py` per design decision 4, `media_source` in the manifest's dependencies; verify: tests for every scenario of "Frames and albums as folders", "Photos in a folder" and "Opening a photo", that a single frame skips the frame level, and that the resolved URL points to Home Assistant (`media-browser` › Photos only for signed-in users › Image source in the browser)

## 4. Card

- [ ] 4.1 WebSocket command `openframe/photo` per design decision 5; verify: tests for the answer with a photo on screen, without one, in safe mode, and refused for a non-admin user
- [ ] 4.2 `frontend/presentation.js` per design decision 6; verify: `node --test tests/frontend/` reads `tests/contract/presentation-cases.json` and every case matches within 1/10,000
- [ ] 4.3 `frontend/crop-editor.js` and the crop button per design decision 6; verify: in a Home Assistant test instance, every scenario of "Crop editor on the card", "Saving a section from the card" and "Crop editor not offered" holds, with a screenshot per scenario in the pull request, and a `node --test` test of the drag and zoom clamping in the editor's model
- [ ] 4.4 Hide button per design decision 7; verify: every scenario of "Hiding the photo on screen from the card" holds in the test instance, and the card model's tests cover its visibility
- [ ] 4.5 `README.md`: the media browser and the editor with screenshots; verify: the sections exist and name the minimum versions

## 5. Devices

- [ ] 5.1 Rows in `../openframe-private/DEVICE_TEST.md` with their references: upload of a snapshot to the Frameo (`photo-actions` › Uploading photos › Camera snapshot to the frame), a section saved in the card and checked on the Lenovo (`dashboard-card` › Saving a section from the card › Save), the media browser with a library of about 1,000 photos (`media-browser` › Photos in a folder › Large album); verify: the rows exist with their references
- [ ] 5.2 Run the rows of 5.1; ask before any persistent change on a device, including uploads and deletions in the photo folder; verify: results entered, a finding in `../openframe-private/FINDINGS.md` for anything that differs

## 6. Integration

- [ ] 6.1 `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`, `node --test tests/frontend/`; verify: all green
- [ ] 6.2 `openspec validate add-home-assistant-photo-management`; verify: exit 0 without warnings

## Workflow follow-up

- Start after `add-home-assistant-card` is archived, so that `dashboard-card` exists as a main spec.
- Archive the change after the device rows of 5.1 are done.
