"""WebSocket command for the card's crop editor.

``openframe/photo`` gives the editor what it needs to show exactly what the frame shows, fresh
when it opens: the photo on screen with its size, section and presentation, a signed URL of its
full size, the screen in its current orientation and the fill mode. It takes no photo ID: the card
opens the editor only for the photo on screen.
"""

from __future__ import annotations

import asyncio
from typing import Any

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import OpenframeConfigEntry
from .entity import run_command
from .image import screen_size
from .image_proxy import photo_url

# The fields of the photo the editor reads
PHOTO_FIELDS = ("id", "album", "path", "width", "height", "version", "crop", "presentation")


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_photo)


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "openframe/photo", "device_id": str})
@websocket_api.async_response
async def websocket_photo(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The photo on screen of a frame, for the crop editor."""
    entry = _entry_of_device(hass, msg["device_id"])
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "No openframe frame")
        return
    coordinator = entry.runtime_data
    client = coordinator.client
    # Both fresh, as the last poll may be 15 seconds old; a refusal (safe mode) or no answer is
    # sent as the translated error of the entities
    slideshow, settings = await run_command(
        coordinator, asyncio.gather(client.get_slideshow(), client.get_settings())
    )
    photo = slideshow["photo"]
    width, height = screen_size(coordinator.data.info, settings)
    connection.send_result(
        msg["id"],
        {
            "photo": None
            if photo is None
            else {key: photo[key] for key in PHOTO_FIELDS}
            | {"url": photo_url(hass, entry.entry_id, photo, "full")},
            "screen": {"width": width, "height": height},
            "fillMode": settings["fillMode"],
        },
    )


def _entry_of_device(hass: HomeAssistant, device_id: str) -> OpenframeConfigEntry | None:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    return next(
        (
            entry
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            if entry.entry_id in device.config_entries
        ),
        None,
    )
