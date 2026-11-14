"""The photo on screen as the frame shows it, read through the token.

The signed image URLs of the API are not handed to Home Assistant: they expire after two hours,
and the frame is not reachable from outside the LAN. ``image_last_updated`` changes when the photo
or its display URL without the signature changes (the URL carries the image version and the key of
the shown part; the signature `t` changes every hour), so the frontend reloads the image exactly
then.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CurrentPhotoImage(hass, entry.runtime_data)])


def unsigned(url: str) -> str:
    """The display URL without its signature, which changes every hour for the same image."""
    parsed = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "t"]
    return urlunsplit(parsed._replace(query=urlencode(query)))


def screen_size(info: dict[str, Any], settings: dict[str, Any]) -> tuple[int, int]:
    """The frame's screen in its current orientation, as width and height.

    The info gives the screen in the device's natural orientation; the frame draws a landscape
    orientation on the long edge and a portrait one on the short edge, whatever the natural one is.
    """
    long, short = sorted((info["screen"]["width"], info["screen"]["height"]), reverse=True)
    return (long, short) if settings["orientation"] == "landscape" else (short, long)


class CurrentPhotoImage(OpenframeEntity, ImageEntity):
    """The part of the photo on screen that the frame shows."""

    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, coordinator: OpenframeCoordinator) -> None:
        OpenframeEntity.__init__(self, coordinator, "current_photo")
        ImageEntity.__init__(self, hass)
        self._shown: tuple[str, str] | None = None
        self._cache: tuple[str, bytes] | None = None
        self._follow_photo()

    @property
    def available(self) -> bool:
        return super().available and self.data.slideshow is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The screen format, so that a card can draw the photo in the frame's shape."""
        width, height = screen_size(self.data.info, self.data.settings)
        return {"screen_width": width, "screen_height": height}

    @callback
    def _handle_coordinator_update(self) -> None:
        self._follow_photo()
        super()._handle_coordinator_update()

    def _follow_photo(self) -> None:
        slideshow = self.data.slideshow
        photo = slideshow["photo"] if slideshow else None
        shown = None if photo is None else (photo["id"], unsigned(photo["urls"]["display"]))
        if shown != self._shown:
            self._shown = shown
            self._attr_image_last_updated = None if shown is None else dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        if self._shown is None:
            return None
        photo_id, display_url = self._shown
        if self._cache is not None and self._cache[0] == display_url:
            return self._cache[1]
        image = await self.command(self.coordinator.client.get_photo_image(photo_id))
        self._cache = (display_url, image)
        return image
