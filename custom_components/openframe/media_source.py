"""The frames' photos in Home Assistant's media browser, by frame and album.

Identifiers: ``{entry_id}`` (a frame), ``{entry_id}/all`` (all its photos),
``{entry_id}/album/{path}`` (an album) and ``{entry_id}/photo/{id}/{version}`` (a photo; the
version keeps the image URL immutable). With a single frame the root is the frame's folder. Folders
are read from the frame when they are opened, never polled; images go through the image proxy.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable
from typing import Any

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, PHOTO_ID_PATTERN
from .entity import run_command
from .image_proxy import photo_url

# Photos per folder: the most the frame returns in one page
PAGE = 500


async def async_get_media_source(hass: HomeAssistant) -> OpenframeMediaSource:
    return OpenframeMediaSource(hass)


class OpenframeMediaSource(MediaSource):
    """openframe frames as folders of albums and photos."""

    name = "openframe"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """The uncropped photo in the frame's full size, through Home Assistant."""
        match = re.fullmatch(r"([^/]+)/photo/([^/]+)/(\d+)", item.identifier or "")
        if match is None or not re.fullmatch(PHOTO_ID_PATTERN, match[2]):
            raise Unresolvable(f"Not a photo: {item.identifier}")
        entry = self._entry(match[1], Unresolvable)
        photo = {"id": match[2], "version": int(match[3])}
        return PlayMedia(photo_url(self.hass, entry.entry_id, photo, "full"), "image/jpeg")

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        if not item.identifier:
            entries = self.hass.config_entries.async_loaded_entries(DOMAIN)
            if len(entries) == 1:
                return await self._frame(entries[0])
            return _folder(
                None, self.name or DOMAIN, [_folder(e.entry_id, e.title) for e in entries]
            )
        entry_id, _, rest = item.identifier.partition("/")
        entry = self._entry(entry_id, BrowseError)
        if not rest:
            return await self._frame(entry)
        if rest == "all":
            return await self._all_photos(entry)
        if rest.startswith("album/"):
            return await self._album(entry, rest.removeprefix("album/"))
        raise BrowseError(f"Unknown folder: {item.identifier}")

    def _entry(self, entry_id: str, error: type[HomeAssistantError]) -> ConfigEntry:
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry not in self.hass.config_entries.async_loaded_entries(DOMAIN):
            raise error(f"Unknown frame: {entry_id}")
        return entry

    async def _frame(self, entry: ConfigEntry) -> BrowseMediaSource:
        """A frame's folder: "All photos" and its top-level albums."""
        _check(entry)
        albums = await _read(entry, entry.runtime_data.client.get_albums())
        children = [_folder(f"{entry.entry_id}/all", "All photos")] + [
            _album_folder(entry, album) for album in albums if "/" not in album["name"]
        ]
        return _folder(entry.entry_id, entry.title, children)

    async def _all_photos(self, entry: ConfigEntry) -> BrowseMediaSource:
        _check(entry)
        page = await _read(
            entry, entry.runtime_data.client.list_photos(sort="date_desc", limit=PAGE)
        )
        return _photo_folder(entry, f"{entry.entry_id}/all", "All photos", [], page)

    async def _album(self, entry: ConfigEntry, path: str) -> BrowseMediaSource:
        """An album's folder: its sub-albums and the photos directly in it."""
        _check(entry)
        client = entry.runtime_data.client
        albums, page = await _read(
            entry,
            asyncio.gather(
                client.get_albums(),
                client.list_photos(album=path, subalbums=False, sort="date_desc", limit=PAGE),
            ),
        )
        album = next((a for a in albums if a["name"] == path), None)
        if album is None:
            raise BrowseError(translation_domain=DOMAIN, translation_key="album_not_found")
        subalbums = [
            _album_folder(entry, a) for a in albums if a["name"].rpartition("/")[0] == path
        ]
        return _photo_folder(
            entry, f"{entry.entry_id}/album/{path}", _album_title(album), subalbums, page
        )


def _check(entry: ConfigEntry) -> None:
    """Refuse to open a folder of a frame in safe mode, which the photo routes do not refuse."""
    data = entry.runtime_data.data
    if data is not None and data.state["safeMode"]:
        raise BrowseError(translation_domain=DOMAIN, translation_key="safe_mode")


async def _read[T](entry: ConfigEntry, call: Awaitable[T]) -> T:
    """Read a folder from the frame; no answer becomes a translated error."""
    try:
        return await run_command(entry.runtime_data, call)
    except HomeAssistantError as err:
        raise BrowseError(
            translation_domain=DOMAIN,
            translation_key=err.translation_key,
            translation_placeholders=err.translation_placeholders,
        ) from err


def _folder(
    identifier: str | None, title: str, children: list[BrowseMediaSource] | None = None
) -> BrowseMediaSource:
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier,
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaType.IMAGE,
        title=title,
        can_play=False,
        can_expand=True,
        children=children,
        children_media_class=MediaClass.IMAGE,
    )


def _album_title(album: dict[str, Any]) -> str:
    title = album["name"].rpartition("/")[2]
    return f"{title} (hidden)" if album["hidden"] else title


def _album_folder(entry: ConfigEntry, album: dict[str, Any]) -> BrowseMediaSource:
    return _folder(f"{entry.entry_id}/album/{album['name']}", _album_title(album))


def _photo_folder(
    entry: ConfigEntry,
    identifier: str,
    title: str,
    subalbums: list[BrowseMediaSource],
    page: dict[str, Any],
) -> BrowseMediaSource:
    """A folder of sub-albums and the newest photos; its title says when it shows not all."""
    photos = [_photo(entry, photo) for photo in page["items"]]
    if page["total"] > len(photos):
        title = f"{title} ({len(photos)} of {page['total']})"
    folder = _folder(identifier, title, subalbums + photos)
    folder.not_shown = page["total"] - len(photos)
    return folder


def _photo(entry: ConfigEntry, photo: dict[str, Any]) -> BrowseMediaSource:
    """A photo, titled by its comment or file name, without a thumbnail if the frame cannot
    render it."""
    title = photo["comment"] or photo["path"].rpartition("/")[2]
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"{entry.entry_id}/photo/{photo['id']}/{photo['version']}",
        media_class=MediaClass.IMAGE,
        media_content_type="image/jpeg",
        title=f"{title} (hidden)" if photo["hidden"] else title,
        can_play=True,
        can_expand=False,
        thumbnail=None
        if photo["quarantined"]
        else photo_url(entry.runtime_data.hass, entry.entry_id, photo, "thumb"),
    )
