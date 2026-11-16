"""The photo and album actions: target, photo on screen, permissions and responses."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.openframe.const import DOMAIN
from tests.conftest import entity_id, mock_entry, tick
from tests.fake_frame import FRAME_ID, FakeFrame

OTHER_ID = f"{FRAME_ID}-2"


def device_id(hass: HomeAssistant, frame_id: str = FRAME_ID) -> str:
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, frame_id)
    assert entry is not None
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, frame_id), entry.entry_id)
    assert device is not None
    return device.id


async def act(
    hass: HomeAssistant,
    service: str,
    devices: list[str],
    *,
    response: bool = False,
    context: Context | None = None,
    **data: Any,
) -> ServiceResponse:
    """Call an action with frames as target, as an automation would."""
    return await hass.services.async_call(
        DOMAIN,
        service,
        {"device_id": devices, **data},
        blocking=True,
        return_response=response,
        context=context,
    )


@pytest.fixture
async def other(
    hass: HomeAssistant, entry: MockConfigEntry, socket_enabled: None
) -> AsyncGenerator[FakeFrame]:
    """A second frame, set up after the first one."""
    frame = FakeFrame()
    frame.info["id"] = OTHER_ID
    frame.info["name"] = "Other frame"
    await frame.start()
    try:
        base = mock_entry(frame)
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Other frame",
            unique_id=OTHER_ID,
            data=base.data,
            minor_version=2,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield frame
    finally:
        await frame.stop()
    assert not frame.contract_errors, "\n".join(frame.contract_errors)


# -- Target of a photo action ----------------------------------------------------------------


async def test_photo_id_with_two_frames(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame
) -> None:
    """photo-actions › Target of a photo action › Two frames with a photo ID."""
    photo = frame.add_photo("a/1.jpg")
    other.add_photo("a/1.jpg")
    frame.reset_requests()
    other.reset_requests()
    devices = [device_id(hass), device_id(hass, OTHER_ID)]
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "set_photo_hidden", devices, photo_id=photo.id, hidden=True)
    assert caught.value.translation_key == "photo_id_one_frame"
    assert not any(p.hidden for p in frame.photos + other.photos)
    assert frame.requests == other.requests == []


async def test_unknown_photo(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """photo-actions › Target of a photo action › Unknown photo."""
    frame.add_photo("a/1.jpg")
    with pytest.raises(HomeAssistantError) as caught:
        await act(
            hass, "set_photo_hidden", [device_id(hass)], photo_id="local-" + "0" * 40, hidden=True
        )
    assert caught.value.translation_key == "photo_not_found"


async def test_target_without_a_frame(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "set_photo_hidden", [], hidden=True)
    assert caught.value.translation_key == "no_frame"


async def test_photo_id_is_checked_before_the_frame_is_asked(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.reset_requests()
    with pytest.raises(Exception, match="photo_id"):
        await act(hass, "set_photo_hidden", [device_id(hass)], photo_id="../etc", hidden=True)
    assert frame.requests == []


# -- Photo on screen by default --------------------------------------------------------------


async def test_hide_the_photo_on_the_wall(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Photo on screen by default › Hide the photo on the wall: the action hits
    the photo on screen when it runs, not the one of the last poll."""
    frame.add_photo("a/1.jpg")
    frame.add_photo("a/2.jpg")
    frame.add_photo("a/3.jpg")
    frame.current = 1
    on_wall = frame.on_screen()
    assert on_wall is not None
    frame.reset_requests()
    await act(hass, "set_photo_hidden", [device_id(hass)], hidden=True)
    assert on_wall.hidden is True
    assert on_wall not in frame.visible_photos()
    assert frame.requests == [("GET", "/slideshow"), ("PATCH", f"/photos/{on_wall.id}")]


async def test_photo_on_screen_of_each_frame(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame
) -> None:
    mine = frame.add_photo("a/1.jpg")
    theirs = other.add_photo("b/1.jpg")
    response = await act(
        hass,
        "set_photo_hidden",
        [device_id(hass), device_id(hass, OTHER_ID)],
        response=True,
        hidden=True,
    )
    assert mine.hidden and theirs.hidden
    assert response is not None
    assert {(p["device_id"], p["id"]) for p in response["photos"]} == {
        (device_id(hass), mine.id),
        (device_id(hass, OTHER_ID), theirs.id),
    }


async def test_frame_without_photos(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Photo on screen by default › Frame without photos."""
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "set_photo_hidden", [device_id(hass)], hidden=True)
    assert caught.value.translation_key == "no_photo_on_screen"
    assert caught.value.translation_placeholders == {"frame": entry.title}
    # Home Assistant drops the full stop of a translated message
    assert str(caught.value) == f"{entry.title} shows no photo"


async def test_one_frame_without_a_photo_does_not_stop_the_other(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame
) -> None:
    theirs = other.add_photo("b/1.jpg")
    with pytest.raises(ServiceValidationError) as caught:
        await act(
            hass, "set_photo_hidden", [device_id(hass), device_id(hass, OTHER_ID)], hidden=True
        )
    assert caught.value.translation_key == "no_photo_on_screen"
    assert theirs.hidden is True


async def test_photo_on_screen_in_safe_mode(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("a/1.jpg")
    frame.safe_mode = True
    with pytest.raises(HomeAssistantError) as caught:
        await act(hass, "set_photo_hidden", [device_id(hass)], hidden=True)
    assert caught.value.translation_key == "safe_mode"


# -- Photo actions for administrators --------------------------------------------------------


async def test_non_admin_user_is_refused(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, hass_read_only_user: MockUser
) -> None:
    """photo-actions › Photo actions for administrators › Non-admin user."""
    photo = frame.add_photo("a/1.jpg")
    frame.reset_requests()
    context = Context(user_id=hass_read_only_user.id)
    for service, data in (
        ("delete_photo", {"photo_id": photo.id}),
        ("set_photo_hidden", {"hidden": True}),
        ("set_photo_comment", {"comment": "x"}),
        ("set_photo_crop", {"reset": True}),
        ("upload_photo", {"file_path": ["/media/a.jpg"]}),
        ("set_album_hidden", {"album": "a", "hidden": True}),
    ):
        with pytest.raises(Unauthorized):
            await act(hass, service, [device_id(hass)], context=context, **data)
    assert frame.photos == [photo]
    assert frame.requests == []


async def test_automation_and_admin_may_act(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, hass_admin_user: MockUser
) -> None:
    """photo-actions › Photo actions for administrators › Automation."""
    photo = frame.add_photo("a/1.jpg")
    await act(hass, "set_photo_hidden", [device_id(hass)], photo_id=photo.id, hidden=True)
    assert photo.hidden is True
    admin = Context(user_id=hass_admin_user.id)
    await act(
        hass, "set_photo_hidden", [device_id(hass)], context=admin, photo_id=photo.id, hidden=False
    )
    assert photo.hidden is False


# -- Responses of photo actions --------------------------------------------------------------


async def test_response_in_a_script(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Responses of photo actions › Response in a script."""
    photo = frame.add_photo("holiday/IMG_0042.jpg")
    response = await act(
        hass, "set_photo_comment", [device_id(hass)], response=True, comment="Summer 2025"
    )
    assert response == {
        "photos": [
            {
                "device_id": device_id(hass),
                "id": photo.id,
                "album": "holiday",
                "path": "holiday/IMG_0042.jpg",
                "hidden": False,
                "visible": True,
                "comment": "Summer 2025",
                "crop": None,
            }
        ]
    }


async def test_no_response_unless_asked(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("a/1.jpg")
    assert await act(hass, "set_photo_comment", [device_id(hass)], comment="x") is None
    assert frame.photos[0].comment == "x"


# -- Hiding and showing a photo --------------------------------------------------------------


async def test_show_again(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """photo-actions › Hiding and showing a photo › Show again, unless its album is hidden."""
    photo = frame.add_photo("a/1.jpg", hidden=True)
    in_hidden_album = frame.add_photo("b/2.jpg", hidden=True)
    frame.album_settings["b"] = True
    await act(hass, "set_photo_hidden", [device_id(hass)], photo_id=photo.id, hidden=False)
    assert frame.visible(photo)
    await act(
        hass, "set_photo_hidden", [device_id(hass)], photo_id=in_hidden_album.id, hidden=False
    )
    assert in_hidden_album.hidden is False
    assert not frame.visible(in_hidden_album)


# -- Comment of a photo ----------------------------------------------------------------------


async def test_new_comment(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """photo-actions › Comment of a photo › New comment (on the photo on screen)."""
    photo = frame.add_photo("a/1.jpg")
    await act(hass, "set_photo_comment", [device_id(hass)], comment="Summer 2025")
    assert photo.comment == "Summer 2025"
    assert ("PATCH", f"/photos/{photo.id}", {"comment": "Summer 2025"}) in frame.bodies


async def test_remove_the_comment(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Comment of a photo › Remove the comment."""
    photo = frame.add_photo("a/1.jpg", comment="Old")
    await act(hass, "set_photo_comment", [device_id(hass)], comment="")
    assert photo.comment is None
    assert ("PATCH", f"/photos/{photo.id}", {"comment": None}) in frame.bodies


async def test_comment_too_long_names_the_frames_reason(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    photo = frame.add_photo("a/1.jpg", comment="Kept")
    with pytest.raises(HomeAssistantError) as caught:
        await act(hass, "set_photo_comment", [device_id(hass)], comment="x" * 501)
    assert caught.value.translation_key == "refused"
    assert "At most 500 characters" in str(caught.value)
    assert photo.comment == "Kept"


# -- Section of a photo ----------------------------------------------------------------------


async def test_focus_on_the_upper_part(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Section of a photo › Focus on the upper part."""
    photo = frame.add_photo("a/1.jpg")
    part = photo.part
    await act(hass, "set_photo_crop", [device_id(hass)], x=0.5, y=0.2, zoom=1)
    section = {"x": 0.5, "y": 0.2, "zoom": 1.0}
    assert photo.crop == section
    assert ("PATCH", f"/photos/{photo.id}", {"crop": section}) in frame.bodies
    # The frame shows another part from the photo's next appearance on
    assert photo.part != part


async def test_reset_the_section(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Section of a photo › Reset."""
    photo = frame.add_photo("a/1.jpg", crop={"x": 0.5, "y": 0.2, "zoom": 1.0})
    response = await act(hass, "set_photo_crop", [device_id(hass)], response=True, reset=True)
    assert photo.crop is None
    assert ("PATCH", f"/photos/{photo.id}", {"crop": None}) in frame.bodies
    assert response is not None
    assert response["photos"][0]["crop"] is None


@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"x": 0.5, "y": 0.5, "zoom": 5}, "zoom"),
        ({"x": 0.5, "y": 0.5, "zoom": 0}, "zoom"),
        ({"x": 1.5, "y": 0.5, "zoom": 1}, "x"),
        ({"x": 0.5, "y": -0.1, "zoom": 1}, "y"),
    ],
)
async def test_section_out_of_range(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    values: dict[str, float],
    field: str,
) -> None:
    """photo-actions › Section of a photo › Zoom out of range: refused naming the field, the
    frame is not asked."""
    frame.add_photo("a/1.jpg")
    frame.reset_requests()
    with pytest.raises(Exception, match=f"'{field}'"):
        await act(hass, "set_photo_crop", [device_id(hass)], **values)
    assert frame.requests == []


@pytest.mark.parametrize(
    "values",
    [{"x": 0.5}, {"x": 0.5, "y": 0.5}, {}, {"x": 0.5, "y": 0.5, "zoom": 1, "reset": True}],
)
async def test_whole_section_or_reset(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, values: dict[str, Any]
) -> None:
    frame.add_photo("a/1.jpg")
    frame.reset_requests()
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "set_photo_crop", [device_id(hass)], **values)
    assert caught.value.translation_key == "crop_or_reset"
    assert frame.requests == []


# -- Deleting a photo ------------------------------------------------------------------------


async def test_delete_a_local_photo(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Deleting a photo › Local photo."""
    photo = frame.add_photo("uploads/door.jpg")
    other = frame.add_photo("uploads/garden.jpg")
    await act(hass, "delete_photo", [device_id(hass)], photo_id=photo.id)
    assert frame.photos == [other]


async def test_delete_the_photo_on_screen(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("uploads/door.jpg")
    await act(hass, "delete_photo", [device_id(hass)])
    assert frame.photos == []


async def test_photo_of_a_nextcloud_share(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Deleting a photo › Photo of a Nextcloud share."""
    photo = frame.add_photo("shared/1.jpg", source="nc1")
    with pytest.raises(HomeAssistantError) as caught:
        await act(hass, "delete_photo", [device_id(hass)], photo_id=photo.id)
    assert caught.value.translation_key == "read_only_source"
    assert "can only be hidden" in str(caught.value)
    assert frame.photos == [photo]


# -- Hiding an album -------------------------------------------------------------------------


async def test_hide_a_sub_album(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Hiding an album › Hide a sub-album (its switch is disabled)."""
    frame.add_photo("holiday/1.jpg")
    frame.add_photo("holiday/2024/2.jpg")
    frame.add_photo("holiday/2025/3.jpg")
    await act(hass, "set_album_hidden", [device_id(hass)], album="holiday/2024", hidden=True)
    assert ("PATCH", "/albums", {"name": "holiday/2024", "hidden": True}) in frame.bodies
    assert [p.path for p in frame.visible_photos()] == ["holiday/1.jpg", "holiday/2025/3.jpg"]


async def test_unknown_album(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    frame.add_photo("holiday/1.jpg")
    with pytest.raises(HomeAssistantError) as caught:
        await act(hass, "set_album_hidden", [device_id(hass)], album="nowhere", hidden=True)
    assert caught.value.translation_key == "album_not_found"


async def test_frame_does_not_answer(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("holiday/1.jpg")
    frame.unreachable = True
    with pytest.raises(HomeAssistantError) as caught:
        await act(hass, "set_album_hidden", [device_id(hass)], album="holiday", hidden=True)
    assert caught.value.translation_key == "no_answer"


# -- Fresh entities after a photo action -----------------------------------------------------


async def test_hidden_by_an_action(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """photo-actions › Fresh entities after a photo action › Hidden by an action: the action
    forces the full read, also if the library version had not moved."""
    for number in range(120):
        frame.add_photo(f"a/{number:03}.jpg")
    await tick(hass, freezer)
    visible = entity_id(hass, "sensor", "photos_visible")
    assert hass.states.get(visible).state == "120"
    version = frame.library_version
    await act(hass, "set_photo_hidden", [device_id(hass)], photo_id=frame.photos[5].id, hidden=True)
    frame.library_version = version
    await tick(hass, freezer)
    assert hass.states.get(visible).state == "119"


async def test_deleted_by_an_action(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.add_photo("a/1.jpg")
    frame.add_photo("a/2.jpg")
    await tick(hass, freezer)
    version = frame.library_version
    await act(hass, "delete_photo", [device_id(hass)], photo_id=frame.photos[0].id)
    frame.library_version = version
    await tick(hass, freezer)
    assert hass.states.get(entity_id(hass, "sensor", "photos")).state == "1"


async def test_album_switch_follows_the_action_at_once(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.add_photo("holiday/1.jpg")
    await tick(hass, freezer)
    switch = entity_id(hass, "switch", "album_holiday")
    assert hass.states.get(switch).state == STATE_ON
    await act(hass, "set_album_hidden", [device_id(hass)], album="holiday", hidden=True)
    assert hass.states.get(switch).state == STATE_OFF


# -- Uploading photos ------------------------------------------------------------------------

JPEG = b"\xff\xd8\xff\xe0 a photo"


@pytest.fixture
def media(hass: HomeAssistant, tmp_path: Path) -> Path:
    """A folder Home Assistant may read, with a camera snapshot in it."""
    folder = tmp_path / "media"
    (folder / "snapshots").mkdir(parents=True)
    (folder / "snapshots" / "door.jpg").write_bytes(JPEG)
    hass.config.allowlist_external_dirs = {str(folder.resolve())}
    return folder


async def test_camera_snapshot_to_the_frame(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, media: Path
) -> None:
    """photo-actions › Uploading photos › Camera snapshot to the frame."""
    response = await act(
        hass,
        "upload_photo",
        [device_id(hass)],
        response=True,
        file_path=str(media / "snapshots" / "door.jpg"),
        album="visitors",
    )
    [photo] = frame.photos
    assert (photo.path, photo.album) == ("visitors/door.jpg", "visitors")
    assert response == {
        "photos": [{"id": photo.id, "path": "visitors/door.jpg", "album": "visitors"}]
    }
    [(_, _, body)] = [b for b in frame.bodies if b[:2] == ("POST", "/photos")]
    assert b'filename="door.jpg"' in body
    assert b"Content-Type: image/jpeg" in body
    assert JPEG in body


async def test_several_files_in_one_request(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, media: Path
) -> None:
    (media / "garden.png").write_bytes(b"\x89PNG a photo")
    files = [str(media / "snapshots" / "door.jpg"), str(media / "garden.png")]
    assert await act(hass, "upload_photo", [device_id(hass)], file_path=files) is None
    assert [p.path for p in frame.photos] == ["door.jpg", "garden.png"]
    assert frame.count("POST", "/photos") == 1


@pytest.mark.parametrize(
    "path",
    ["{config}/secrets.yaml", "{media}/../secrets.yaml", "/etc/passwd"],
)
async def test_folder_not_allowed(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, media: Path, path: str
) -> None:
    """photo-actions › Uploading photos › Folder not allowed: nothing is sent, also not the
    allowed files of the same call."""
    path = path.format(config=hass.config.config_dir, media=media)
    frame.reset_requests()
    with pytest.raises(ServiceValidationError) as caught:
        await act(
            hass,
            "upload_photo",
            [device_id(hass)],
            file_path=[str(media / "snapshots" / "door.jpg"), path],
        )
    assert caught.value.translation_key == "path_not_allowed"
    assert caught.value.translation_placeholders == {"path": path}
    assert frame.requests == []


async def test_unsupported_file(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, media: Path
) -> None:
    """photo-actions › Uploading photos › Unsupported file: the frame's message, nothing stored."""
    (media / "notes.txt").write_text("not a photo")
    files = [str(media / "snapshots" / "door.jpg"), str(media / "notes.txt")]
    with pytest.raises(HomeAssistantError) as caught:
        await act(hass, "upload_photo", [device_id(hass)], file_path=files)
    assert caught.value.translation_key == "unsupported_format"
    assert "notes.txt has no supported format" in str(caught.value)
    assert frame.photos == []


async def test_missing_file(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, media: Path
) -> None:
    frame.reset_requests()
    missing = str(media / "snapshots" / "gone.jpg")
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "upload_photo", [device_id(hass)], file_path=missing)
    assert caught.value.translation_key == "file_not_readable"
    assert frame.requests == []


async def test_upload_goes_to_one_frame(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame, media: Path
) -> None:
    frame.reset_requests()
    other.reset_requests()
    with pytest.raises(ServiceValidationError) as caught:
        await act(
            hass,
            "upload_photo",
            [device_id(hass), device_id(hass, OTHER_ID)],
            file_path=str(media / "snapshots" / "door.jpg"),
        )
    assert caught.value.translation_key == "upload_one_frame"
    assert frame.requests == other.requests == []


@pytest.mark.parametrize(
    ("switch", "key"), [("storage_full", "storage_full"), ("safe_mode", "safe_mode")]
)
async def test_frame_refuses_the_upload(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    media: Path,
    switch: str,
    key: str,
) -> None:
    setattr(frame, switch, True)
    with pytest.raises(HomeAssistantError) as caught:
        await act(
            hass, "upload_photo", [device_id(hass)], file_path=str(media / "snapshots" / "door.jpg")
        )
    assert caught.value.translation_key == key
    assert frame.photos == []


async def test_upload_refreshes_the_counts(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    media: Path,
    freezer: FrozenDateTimeFactory,
) -> None:
    version = frame.library_version
    await act(
        hass, "upload_photo", [device_id(hass)], file_path=str(media / "snapshots" / "door.jpg")
    )
    frame.library_version = version
    await tick(hass, freezer)
    assert hass.states.get(entity_id(hass, "sensor", "photos")).state == "1"
