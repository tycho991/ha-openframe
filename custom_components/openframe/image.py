"""The photo on screen as the frame shows it, read through the token.

The signed image URLs of the API are not handed to Home Assistant: they expire after two hours,
and the frame is not reachable from outside the LAN. ``image_last_updated`` changes when the photo
or its display URL changes (the URL carries the image version and the key of the shown part), so
the frontend reloads the image exactly then.
"""

from __future__ import annotations

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

    @callback
    def _handle_coordinator_update(self) -> None:
        self._follow_photo()
        super()._handle_coordinator_update()

    def _follow_photo(self) -> None:
        slideshow = self.data.slideshow
        photo = slideshow["photo"] if slideshow else None
        shown = None if photo is None else (photo["id"], photo["urls"]["display"])
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
