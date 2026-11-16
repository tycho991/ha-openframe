"""The API client against the fake frame."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import aiohttp
import pytest

from custom_components.openframe import api
from custom_components.openframe.api import (
    OpenframeAuthError,
    OpenframeClient,
    OpenframeConnectionError,
    OpenframeResponseError,
    UploadFile,
)
from tests.fake_frame import FRAME_ID, FakeFrame

JPEG = b"\xff\xd8\xff\xe0 a photo"


@pytest.fixture
async def session() -> AsyncGenerator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
def client(frame: FakeFrame, session: aiohttp.ClientSession) -> OpenframeClient:
    _, token = frame.pair_directly()
    return OpenframeClient(session, frame.host, frame.port, token)


async def test_info_and_pairing_without_token(
    frame: FakeFrame, session: aiohttp.ClientSession
) -> None:
    client = OpenframeClient(session, frame.host, frame.port)
    assert (await client.get_info())["id"] == FRAME_ID
    await client.show_pairing_code()
    assert frame.code is not None
    answer = await client.pair(frame.code, "Home Assistant")
    assert answer["client"]["name"] == "Home Assistant"
    assert frame.clients[answer["client"]["id"]]["token"] == answer["token"]


async def test_wrong_code_is_a_response_error_not_an_auth_error(
    frame: FakeFrame, session: aiohttp.ClientSession
) -> None:
    client = OpenframeClient(session, frame.host, frame.port)
    await client.show_pairing_code()
    with pytest.raises(OpenframeResponseError) as caught:
        await client.pair("000000" if frame.code != "000000" else "111111", "Home Assistant")
    assert not isinstance(caught.value, OpenframeAuthError)
    assert (caught.value.status, caught.value.code) == (401, "invalid_code")


async def test_reading_methods(frame: FakeFrame, client: OpenframeClient) -> None:
    frame.add_photo("holiday/IMG_0042.jpg", comment="Summer 2025")
    frame.add_photo("holiday/IMG_0043.jpg", hidden=True)
    frame.add_source("nc1", "Shared photos")
    assert (await client.get_state())["appVersion"] == "0.6.0"
    assert (await client.get_display())["on"] is True
    slideshow = await client.get_slideshow()
    assert slideshow["photo"]["comment"] == "Summer 2025"
    assert (await client.get_settings())["intervalSeconds"] == 30
    assert [a["name"] for a in await client.get_albums()] == ["holiday"]
    assert await client.count_photos() == 2
    assert await client.count_photos(visible=True) == 1
    assert await client.count_photos(visible=False) == 1
    image = await client.get_photo_image(slideshow["photo"]["id"])
    assert image.startswith(b"\xff\xd8")
    assert [s["id"] for s in await client.get_sources()] == ["nc1"]
    assert (await client.get_update())["phase"] == "idle"


async def test_commands(frame: FakeFrame, client: OpenframeClient) -> None:
    frame.add_photo("a/1.jpg")
    frame.add_photo("a/2.jpg")
    frame.add_source("nc1", "Shared photos")
    frame.safe_mode = False
    assert (await client.control_slideshow("next"))["photo"]["path"] == "a/2.jpg"
    assert (await client.control_slideshow("pause"))["paused"] is True
    assert (await client.set_display(False))["cause"] == "manual"
    assert (await client.patch_settings({"intervalSeconds": 60}))["intervalSeconds"] == 60
    albums = await client.patch_album("a", True)
    assert albums[0]["hidden"] is True
    assert await client.sync_source("nc1") == {"started": True}
    assert (await client.check_update())["phase"] == "checking"
    frame.update["phase"] = "ready"
    assert (await client.install_update())["phase"] == "installing"
    frame.safe_mode = True
    await client.exit_safe_mode()
    assert frame.safe_mode is False


async def test_list_photos_filters_and_pages(frame: FakeFrame, client: OpenframeClient) -> None:
    frame.add_photo("family/a.jpg", taken_at="2025-01-01T10:00:00Z")
    frame.add_photo("family/2025/b.jpg", taken_at="2025-03-01T10:00:00Z")
    frame.add_photo("family/2025/c.jpg", taken_at="2025-02-01T10:00:00Z", hidden=True)
    frame.add_photo("other/d.jpg", taken_at="2025-04-01T10:00:00Z")

    def paths(page: dict) -> list[str]:
        return [p["path"] for p in page["items"]]

    page = await client.list_photos(album="family", sort="date_desc")
    assert paths(page) == ["family/2025/b.jpg", "family/2025/c.jpg", "family/a.jpg"]
    assert paths(await client.list_photos(album="family", subalbums=False)) == ["family/a.jpg"]
    assert paths(await client.list_photos(album="family", visible=False)) == ["family/2025/c.jpg"]
    assert paths(await client.list_photos(sort="name_asc", limit=2)) == [
        "family/2025/b.jpg",
        "family/2025/c.jpg",
    ]
    seen: list[str] = []
    cursor = None
    while True:
        page = await client.list_photos(sort="date_asc", limit=3, cursor=cursor)
        assert page["total"] == 4
        seen += paths(page)
        if (cursor := page["nextCursor"]) is None:
            break
    assert seen == ["family/a.jpg", "family/2025/c.jpg", "family/2025/b.jpg", "other/d.jpg"]
    assert ("GET", "/photos", None) not in frame.bodies


async def test_patch_photo(frame: FakeFrame, client: OpenframeClient) -> None:
    photo = frame.add_photo("a/1.jpg", comment="Old")
    answer = await client.patch_photo(photo.id, {"hidden": True, "comment": "  New\n\ntext "})
    assert (answer["hidden"], answer["visible"], answer["comment"]) == (True, False, "New text")
    crop = {"x": 0.25, "y": 0.75, "zoom": 1.5}
    assert (await client.patch_photo(photo.id, {"crop": crop}))["crop"] == crop
    answer = await client.patch_photo(photo.id, {"crop": None, "comment": None})
    assert (answer["crop"], answer["comment"]) == (None, None)
    assert [body for _, path, body in frame.bodies if path.startswith("/photos/")] == [
        {"hidden": True, "comment": "  New\n\ntext "},
        {"crop": crop},
        {"crop": None, "comment": None},
    ]


async def test_patch_photo_refusals(frame: FakeFrame, client: OpenframeClient) -> None:
    photo = frame.add_photo("a/1.jpg", comment="Kept")
    with pytest.raises(OpenframeResponseError) as caught:
        await client.patch_photo(photo.id, {"hidden": True, "comment": "x" * 501})
    assert (caught.value.status, set(caught.value.fields)) == (400, {"comment"})
    assert (photo.hidden, photo.comment) == (False, "Kept")
    with pytest.raises(OpenframeResponseError) as caught:
        await client.patch_photo("local-" + "0" * 40, {"hidden": True})
    assert (caught.value.status, caught.value.code) == (404, "not_found")


async def test_delete_photo(frame: FakeFrame, client: OpenframeClient) -> None:
    local = frame.add_photo("a/1.jpg")
    remote = frame.add_photo("a/2.jpg", source="nc1")
    assert await client.delete_photo(local.id) is None
    assert frame.photos == [remote]
    with pytest.raises(OpenframeResponseError) as caught:
        await client.delete_photo(remote.id)
    assert (caught.value.status, caught.value.code) == (409, "read_only_source")
    with pytest.raises(OpenframeResponseError) as caught:
        await client.delete_photo(local.id)
    assert caught.value.status == 404


async def test_upload_photos(frame: FakeFrame, client: OpenframeClient) -> None:
    frame.add_photo("family/2025/door.jpg")
    files = [
        UploadFile("door.jpg", JPEG, "image/jpeg"),
        UploadFile("garden.png", b"\x89PNG a photo", "image/png"),
    ]
    stored = await client.upload_photos(files, album=" family / 2025 /../")
    assert [p["path"] for p in stored] == ["family/2025/door-1.jpg", "family/2025/garden.png"]
    assert [p["album"] for p in stored] == ["family/2025", "family/2025"]
    assert [p["path"] for p in await client.upload_photos([files[0]])] == ["door.jpg"]
    assert len(frame.photos) == 4


async def test_upload_refusals_store_nothing(frame: FakeFrame, client: OpenframeClient) -> None:
    good = UploadFile("a.jpg", JPEG, "image/jpeg")
    bad = UploadFile("notes.txt", b"plain text", "text/plain")
    with pytest.raises(OpenframeResponseError) as caught:
        await client.upload_photos([good, bad])
    assert (caught.value.status, caught.value.code) == (415, "unsupported_format")
    assert "notes.txt" in caught.value.message
    frame.storage_full = True
    with pytest.raises(OpenframeResponseError) as caught:
        await client.upload_photos([good])
    assert (caught.value.status, caught.value.code) == (507, "insufficient_storage")
    frame.safe_mode = True
    with pytest.raises(OpenframeResponseError) as caught:
        await client.upload_photos([good])
    assert (caught.value.status, caught.value.code) == (503, "safe_mode")
    assert frame.photos == []


async def test_upload_has_a_long_timeout(
    frame: FakeFrame, client: OpenframeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "TIMEOUT", 0.1)
    frame.delay = 0.3
    await client.upload_photos([UploadFile("a.jpg", JPEG, "image/jpeg")])
    monkeypatch.setattr(api, "UPLOAD_TIMEOUT", 0.1)
    with pytest.raises(OpenframeConnectionError):
        await client.upload_photos([UploadFile("b.jpg", JPEG, "image/jpeg")])


async def test_fetch_photo_image_caching(frame: FakeFrame, client: OpenframeClient) -> None:
    photo = frame.add_photo("a/1.jpg", version=3)
    image = await client.fetch_photo_image(photo.id, "thumb", version=3)
    assert (image.status, image.content_type) == (200, "image/jpeg")
    assert image.body.startswith(b"\xff\xd8")
    assert image.cache_control == "private, max-age=31536000, immutable"
    assert image.etag
    again = await client.fetch_photo_image(photo.id, "thumb", version=3, if_none_match=image.etag)
    assert (again.status, again.body, again.etag) == (304, b"", image.etag)
    stale = await client.fetch_photo_image(photo.id, "full", version=2)
    assert stale.cache_control == "private, no-cache"
    assert ("GET", f"/photos/{photo.id}/image") in frame.requests


async def test_fetch_photo_image_unavailable(frame: FakeFrame, client: OpenframeClient) -> None:
    photo = frame.add_photo("a/1.jpg", quarantined=True)
    with pytest.raises(OpenframeResponseError) as caught:
        await client.fetch_photo_image(photo.id, "thumb", version=1)
    assert (caught.value.status, caught.value.code) == (503, "render_failed")
    frame.safe_mode = True
    with pytest.raises(OpenframeResponseError) as caught:
        await client.fetch_photo_image(photo.id, "thumb", version=1)
    assert (caught.value.status, caught.value.code) == (503, "safe_mode")
    with pytest.raises(OpenframeResponseError) as caught:
        await client.fetch_photo_image("local-" + "0" * 40, "thumb")
    assert caught.value.status in (404, 503)


async def test_set_display_sends_only_what_is_given(
    frame: FakeFrame, client: OpenframeClient
) -> None:
    await client.set_display(False)
    await client.set_display(brightness=40)
    answer = await client.set_display(True, 60)
    assert answer["on"] is True
    assert answer["brightness"]["level"] == 60
    assert [body for method, path, body in frame.bodies if path == "/display"] == [
        {"on": False},
        {"brightness": 40},
        {"on": True, "brightness": 60},
    ]


async def test_delete_client(frame: FakeFrame, session: aiohttp.ClientSession) -> None:
    client_id, token = frame.pair_directly()
    await OpenframeClient(session, frame.host, frame.port, token).delete_client(client_id)
    assert client_id not in frame.clients


async def test_revoked_token_is_an_auth_error(frame: FakeFrame, client: OpenframeClient) -> None:
    frame.revoke_all()
    with pytest.raises(OpenframeAuthError):
        await client.get_state()


async def test_conflict_carries_code_and_fields(frame: FakeFrame, client: OpenframeClient) -> None:
    frame.display["available"] = False
    with pytest.raises(OpenframeResponseError) as caught:
        await client.set_display(False)
    assert (caught.value.status, caught.value.code) == (409, "display_unavailable")
    with pytest.raises(OpenframeResponseError) as caught:
        await client.patch_settings({"displaySchedule": {"enabled": True}})
    assert caught.value.code == "validation_failed"
    assert set(caught.value.fields) == {"displaySchedule.enabled"}


async def test_timeout_is_a_connection_error(
    frame: FakeFrame, client: OpenframeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "TIMEOUT", 0.1)
    frame.delay = 1
    with pytest.raises(OpenframeConnectionError):
        await client.get_state()


async def test_dropped_connection_is_a_connection_error(
    frame: FakeFrame, client: OpenframeClient
) -> None:
    frame.unreachable = True
    with pytest.raises(OpenframeConnectionError):
        await client.get_state()


async def test_non_json_answer_is_a_connection_error(
    frame: FakeFrame, client: OpenframeClient
) -> None:
    frame.not_json = True
    with pytest.raises(OpenframeConnectionError):
        await client.get_state()


def test_ipv6_literal_in_base_url(session: aiohttp.ClientSession) -> None:
    client = OpenframeClient(session, "fd00::215", 8080, "secret")
    assert client.base_url == "http://[fd00::215]:8080/api/v1"
    assert client.frame_url == "http://[fd00::215]:8080/"
    assert OpenframeClient(session, "192.168.100.215", 8080).base_url == (
        "http://192.168.100.215:8080/api/v1"
    )


async def test_token_never_in_repr_or_errors(frame: FakeFrame, client: OpenframeClient) -> None:
    token = client._token
    assert token is not None
    assert token not in repr(client)
    texts = []
    frame.revoke_all()
    for setup in (
        lambda: None,
        lambda: setattr(frame, "not_json", True),
        lambda: setattr(frame, "unreachable", True),
    ):
        setup()
        with pytest.raises(api.OpenframeError) as caught:
            await client.get_state()
        error: BaseException | None = caught.value
        while error is not None:
            texts.append(f"{error!s} {error!r}")
            error = error.__cause__ or error.__context__
    assert texts
    assert [t for t in texts if token in t] == []
