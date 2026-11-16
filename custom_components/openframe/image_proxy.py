"""The frame's photo images, served through Home Assistant.

The browser never sees the frame's address or token: the media browser and the card's editor get
URLs of this view, signed by Home Assistant for an hour, because an ``<img>`` cannot send the
session header. The URLs carry the photo's image version, so the frame answers ``immutable`` and a
changed file gets a new URL; the frame's ``ETag`` and ``Cache-Control`` are passed on.
"""

from __future__ import annotations

import re
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from aiohttp import hdrs, web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .api import OpenframeAuthError, OpenframeConnectionError, OpenframeResponseError
from .const import DOMAIN, PHOTO_ID_PATTERN

PHOTO_URL = "/api/openframe/{entry_id}/photos/{photo_id}/{size}"
SIZES = ("thumb", "full")
SIGNATURE_LIFETIME = timedelta(hours=1)
# Refusals of the frame that the view passes on with their status
PASSED_ON = (HTTPStatus.NOT_FOUND, HTTPStatus.SERVICE_UNAVAILABLE)


def photo_url(hass: HomeAssistant, entry_id: str, photo: dict[str, Any], size: str) -> str:
    """A signed URL of the view for a photo record of the API, valid for an hour."""
    path = PHOTO_URL.format(entry_id=entry_id, photo_id=photo["id"], size=size)
    return async_sign_path(hass, f"{path}?v={photo['version']}", SIGNATURE_LIFETIME)


class OpenframeImageView(HomeAssistantView):
    """A rendered size of a photo, read from its frame with the entry's token."""

    url = PHOTO_URL
    name = "api:openframe:photo"
    requires_auth = True

    async def get(
        self, request: web.Request, entry_id: str, photo_id: str, size: str
    ) -> web.Response:
        version = request.query.get("v")
        if (
            size not in SIZES
            or not re.fullmatch(PHOTO_ID_PATTERN, photo_id)
            or (version is not None and not version.isdecimal())
        ):
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        try:
            image = await entry.runtime_data.client.fetch_photo_image(
                photo_id,
                size,
                version=None if version is None else int(version),
                if_none_match=request.headers.get(hdrs.IF_NONE_MATCH),
            )
        except OpenframeAuthError:
            entry.async_start_reauth(hass)
            return web.Response(status=HTTPStatus.BAD_GATEWAY)
        except OpenframeResponseError as err:
            # A photo the frame cannot render, or safe mode: the browser shows no image
            status = err.status if err.status in PASSED_ON else HTTPStatus.BAD_GATEWAY
            return web.Response(status=status)
        except OpenframeConnectionError:
            return web.Response(status=HTTPStatus.GATEWAY_TIMEOUT)
        headers = {
            name: value
            for name, value in ((hdrs.ETAG, image.etag), (hdrs.CACHE_CONTROL, image.cache_control))
            if value is not None
        }
        if image.status == HTTPStatus.NOT_MODIFIED:
            return web.Response(status=HTTPStatus.NOT_MODIFIED, headers=headers)
        return web.Response(body=image.body, content_type="image/jpeg", headers=headers)
