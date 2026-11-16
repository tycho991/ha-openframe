"""The image proxy (`media-browser` › Photos only for signed-in users)."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.openframe.image_proxy import photo_url
from tests.fake_frame import FakeFrame, FakePhoto

IMMUTABLE = "private, max-age=31536000, immutable"


def path(entry: MockConfigEntry, photo: FakePhoto | str, size: str = "thumb", v: int = 1) -> str:
    photo_id = photo if isinstance(photo, str) else photo.id
    return f"/api/openframe/{entry.entry_id}/photos/{photo_id}/{size}?v={v}"


def signed(hass: HomeAssistant, entry: MockConfigEntry, photo: FakePhoto) -> str:
    """A signed URL as the media browser gets it; outside a request Home Assistant signs it for
    its content user."""
    return photo_url(hass, entry.entry_id, {"id": photo.id, "version": photo.version}, "thumb")


def image_requests(frame: FakeFrame) -> list[tuple[str, str]]:
    return [r for r in frame.requests if r[1].endswith("/image")]


async def test_without_signing_in(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """media-browser › Photos only for signed-in users › Without signing in: 401, the frame is
    not asked."""
    photo = frame.add_photo("a/1.jpg")
    client = await hass_client_no_auth()
    frame.reset_requests()
    for url in (path(entry, photo), path(entry, photo) + "&authSig=forged"):
        response = await client.get(url)
        assert response.status == 401
    assert frame.requests == []


async def test_signed_in_user_gets_the_image_with_its_caching(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """The URL carries the photo's version, the frame is asked with it and answers immutable;
    its ETag and a 304 pass through."""
    photo = frame.add_photo("a/1.jpg", version=3)
    client = await hass_client()
    response = await client.get(path(entry, photo, "full", v=3))
    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert (await response.read()).startswith(b"\xff\xd8")
    assert response.headers["Cache-Control"] == IMMUTABLE
    etag = response.headers["ETag"]
    again = await client.get(path(entry, photo, "full", v=3), headers={"If-None-Match": etag})
    assert again.status == 304
    assert again.headers["ETag"] == etag
    stale = await client.get(path(entry, photo, "full", v=2))
    assert stale.headers["Cache-Control"] == "private, no-cache"


async def test_signed_url_works_until_it_expires(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    photo = frame.add_photo("a/1.jpg", version=2)
    url = signed(hass, entry, photo)
    assert f"/photos/{photo.id}/thumb?v=2&authSig=" in url
    client = await hass_client_no_auth()
    assert (await client.get(url)).status == 200
    freezer.tick(timedelta(minutes=59))
    assert (await client.get(url)).status == 200
    freezer.tick(timedelta(minutes=2))
    frame.reset_requests()
    assert (await client.get(url)).status == 401
    assert image_requests(frame) == []


async def test_signature_covers_the_version(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    photo = frame.add_photo("a/1.jpg", version=2)
    url = signed(hass, entry, photo)
    client = await hass_client_no_auth()
    assert (await client.get(url.replace("v=2", "v=3"))).status == 401


async def test_frame_refusals_pass_through(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    quarantined = frame.add_photo("a/1.jpg", quarantined=True)
    fine = frame.add_photo("a/2.jpg")
    client = await hass_client()
    assert (await client.get(path(entry, quarantined))).status == 503
    assert (await client.get(path(entry, fine))).status == 200
    assert (await client.get(path(entry, "local-" + "0" * 40))).status == 404
    frame.safe_mode = True
    assert (await client.get(path(entry, fine))).status == 503
    frame.safe_mode = False
    frame.unreachable = True
    assert (await client.get(path(entry, fine))).status == 504


async def test_bad_requests(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """A size other than thumb or full, a malformed photo ID or version: 400, frame not asked."""
    photo = frame.add_photo("a/1.jpg")
    client = await hass_client()
    frame.reset_requests()
    for url in (
        path(entry, photo, "display"),
        path(entry, photo, "huge"),
        path(entry, "local-1234"),
        path(entry, "LOCAL-" + "0" * 40),
        path(entry, photo).replace("v=1", "v=abc"),
    ):
        assert (await client.get(url)).status == 400, url
    assert frame.requests == []


async def test_unknown_entry(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    photo = frame.add_photo("a/1.jpg")
    client = await hass_client()
    response = await client.get(f"/api/openframe/nonexistent/photos/{photo.id}/thumb?v=1")
    assert response.status == 404
