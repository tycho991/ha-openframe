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
)
from tests.fake_frame import FRAME_ID, FakeFrame


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
    assert (await client.get_state())["appVersion"] == "0.5.0"
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
