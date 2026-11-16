"""The crop editor's WebSocket command `openframe/photo`."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import (
    ClientSessionGenerator,
    WebSocketGenerator,
)

from custom_components.openframe.const import DOMAIN
from tests.fake_frame import FRAME_ID, FakeFrame


def device_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, FRAME_ID), entry.entry_id)
    assert device is not None
    return device.id


async def ask(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, device: str, token: str | None = None
) -> dict[str, Any]:
    client = await (hass_ws_client(hass) if token is None else hass_ws_client(hass, token))
    await client.send_json_auto_id({"type": "openframe/photo", "device_id": device})
    return await client.receive_json()


async def test_photo_on_screen(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """The photo on the wall when the editor opens, not the one of the last poll, with what the
    presentation formula needs and a signed URL of the full size."""
    frame.add_photo("a/1.jpg")
    photo = frame.add_photo("a/2.jpg", crop={"x": 0.5, "y": 0.2, "zoom": 1.0}, version=3)
    frame.settings["orientation"] = "portrait"
    frame.current = 1
    answer = await ask(hass, hass_ws_client, device_id(hass, entry))
    assert answer["success"], answer
    result = answer["result"]
    url = result["photo"].pop("url")
    assert result == {
        "photo": {
            "id": photo.id,
            "album": "a",
            "path": "a/2.jpg",
            "width": 4000,
            "height": 3000,
            "version": 3,
            "crop": {"x": 0.5, "y": 0.2, "zoom": 1.0},
            "presentation": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0, "zoom": 1.0},
        },
        # The settings when the editor opens: portrait since the last poll
        "screen": {"width": 600, "height": 1024},
        "fillMode": "auto",
    }
    assert url.startswith(f"/api/openframe/{entry.entry_id}/photos/{photo.id}/full?v=3&authSig=")
    response = await (await hass_client_no_auth()).get(url)
    assert response.status == 200


async def test_no_photo_on_screen(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    answer = await ask(hass, hass_ws_client, device_id(hass, entry))
    assert answer["success"], answer
    assert answer["result"]["photo"] is None


async def test_safe_mode(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    frame.add_photo("a/1.jpg")
    frame.safe_mode = True
    answer = await ask(hass, hass_ws_client, device_id(hass, entry))
    assert answer["success"] is False
    assert answer["error"]["translation_key"] == "safe_mode"
    assert answer["error"]["message"] == "The frame is in safe mode"


async def test_refused_for_a_non_admin_user(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    frame.add_photo("a/1.jpg")
    frame.reset_requests()
    answer = await ask(hass, hass_ws_client, device_id(hass, entry), hass_read_only_access_token)
    assert answer["success"] is False
    assert answer["error"]["code"] == "unauthorized"
    assert frame.requests == []


async def test_unknown_device(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    answer = await ask(hass, hass_ws_client, "nonexistent")
    assert answer["success"] is False
    assert answer["error"]["code"] == "not_found"
