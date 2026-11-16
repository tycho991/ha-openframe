"""The frames' photos in the media browser (`media-browser`)."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.media_player import BrowseError
from homeassistant.components.media_source import (
    BrowseMediaSource,
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from tests.conftest import tick
from tests.fake_frame import FakeFrame

ROOT = "media-source://openframe"


async def browse(hass: HomeAssistant, identifier: str = "") -> BrowseMediaSource:
    return await async_browse_media(hass, f"{ROOT}/{identifier}" if identifier else ROOT)


def titles(folder: BrowseMediaSource) -> list[str]:
    return [child.title for child in folder.children or []]


# -- Frames and albums as folders ------------------------------------------------------------


async def test_nested_albums(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """media-browser › Frames and albums as folders › Nested albums; a single frame skips the
    frame level."""
    frame.add_photo("holiday/beach.jpg", taken_at="2024-08-01T10:00:00Z")
    frame.add_photo("holiday/2024/hut.jpg")
    frame.add_photo("home/garden.jpg")
    root = await browse(hass)
    assert root.title == entry.title
    assert titles(root) == ["All photos", "holiday", "home"]
    holiday = await browse(hass, f"{entry.entry_id}/album/holiday")
    assert titles(holiday) == ["2024", "beach.jpg"]
    assert [c.can_expand for c in holiday.children or []] == [True, False]
    sub = await browse(hass, f"{entry.entry_id}/album/holiday/2024")
    assert titles(sub) == ["hut.jpg"]


async def test_hidden_photo_and_album(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """media-browser › Frames and albums as folders › Hidden photo."""
    frame.add_photo("holiday/beach.jpg", hidden=True)
    frame.add_photo("private/1.jpg")
    frame.album_settings["private"] = True
    assert titles(await browse(hass)) == ["All photos", "holiday", "private (hidden)"]
    assert titles(await browse(hass, f"{entry.entry_id}/album/holiday")) == ["beach.jpg (hidden)"]


async def test_two_frames(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame
) -> None:
    """One folder per frame; the root asks no frame."""
    frame.reset_requests()
    other.reset_requests()
    root = await browse(hass)
    assert root.title == "openframe"
    assert titles(root) == [entry.title, "Other frame"]
    assert frame.requests == other.requests == []
    other.add_photo("b/1.jpg")
    other_folder = (root.children or [])[1]
    assert titles(await async_browse_media(hass, other_folder.media_content_id)) == [
        "All photos",
        "b",
    ]


# -- Photos in a folder ----------------------------------------------------------------------


async def test_newest_first_titled_by_comment_or_name(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("a/old.jpg", taken_at="2023-01-01T10:00:00Z")
    frame.add_photo("a/new.jpg", taken_at="2025-01-01T10:00:00Z", comment="Summer 2025")
    frame.add_photo("a/middle.jpg", taken_at="2024-01-01T10:00:00Z")
    folder = await browse(hass, f"{entry.entry_id}/album/a")
    assert titles(folder) == ["Summer 2025", "middle.jpg", "old.jpg"]
    photo = (folder.children or [])[0]
    assert (photo.can_play, photo.media_content_type) == (True, "image/jpeg")
    assert photo.thumbnail is not None
    assert photo.thumbnail.startswith(f"/api/openframe/{entry.entry_id}/photos/")
    assert "/thumb?v=1&authSig=" in photo.thumbnail
    assert titles(await browse(hass, f"{entry.entry_id}/all")) == titles(folder)


async def test_large_album(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """media-browser › Photos in a folder › Large album."""
    for number in range(1200):
        frame.add_photo(
            f"holiday/{number:04}.jpg",
            taken_at=f"2025-01-01T10:{number // 60 % 60:02}:{number % 60:02}Z",
        )
    folder = await browse(hass, f"{entry.entry_id}/album/holiday")
    assert folder.title == "holiday (500 of 1200)"
    assert len(folder.children or []) == 500
    # The 500 newest, newest first
    assert titles(folder)[0] == "1199.jpg"
    assert titles(folder)[-1] == "0700.jpg"
    assert folder.not_shown == 700


# -- Frame not available ---------------------------------------------------------------------


async def test_frame_in_safe_mode(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """media-browser › Frame not available › Frame in safe mode."""
    frame.add_photo("a/1.jpg")
    frame.safe_mode = True
    await tick(hass, freezer)
    for identifier in ("", f"{entry.entry_id}/all", f"{entry.entry_id}/album/a"):
        with pytest.raises(BrowseError, match="The frame is in safe mode"):
            await browse(hass, identifier)


async def test_frame_does_not_answer(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("a/1.jpg")
    frame.unreachable = True
    with pytest.raises(BrowseError, match="The frame does not answer"):
        await browse(hass, f"{entry.entry_id}/album/a")


async def test_photo_that_cannot_be_rendered(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """media-browser › Frame not available › Photo that cannot be rendered."""
    frame.add_photo("a/broken.jpg", quarantined=True, taken_at="2025-01-01T10:00:00Z")
    frame.add_photo("a/fine.jpg", taken_at="2024-01-01T10:00:00Z")
    broken, fine = (await browse(hass, f"{entry.entry_id}/album/a")).children or []
    assert broken.thumbnail is None
    assert fine.thumbnail is not None


async def test_unknown_folders(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("a/1.jpg")
    for identifier in ("nonexistent", f"{entry.entry_id}/album/nowhere", f"{entry.entry_id}/x"):
        with pytest.raises(BrowseError):
            await browse(hass, identifier)


# -- Opening a photo -------------------------------------------------------------------------


async def test_open_a_photo(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """media-browser › Opening a photo › Open: the whole photo in the full size; and › Photos only
    for signed-in users › Image source in the browser: the URL points to Home Assistant."""
    photo = frame.add_photo("a/1.jpg", version=4)
    [item] = (await browse(hass, f"{entry.entry_id}/album/a")).children or []
    media = await async_resolve_media(hass, item.media_content_id, None)
    assert media.mime_type == "image/jpeg"
    assert media.url.startswith(f"/api/openframe/{entry.entry_id}/photos/{photo.id}/full?v=4&")
    assert str(frame.port) not in media.url
    client = await hass_client_no_auth()
    response = await client.get(media.url)
    assert response.status == 200
    assert (await response.read()).endswith(f":{photo.version}:{photo.part}:full".encode())


async def test_resolve_refuses_what_is_not_a_photo(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    for identifier in (
        entry.entry_id,
        f"{entry.entry_id}/photo/local-1234/1",
        f"{entry.entry_id}/photo/local-{'0' * 40}/x",
        f"nonexistent/photo/local-{'0' * 40}/1",
    ):
        with pytest.raises(Unresolvable):
            await async_resolve_media(hass, f"{ROOT}/{identifier}", None)
