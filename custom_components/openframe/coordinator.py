"""One coordinator per frame that polls cheaply and reads the heavy parts only when they change.

Every 15 seconds it reads the state, the display and the slideshow. Sources and the update state
follow every minute, or every tick while a sync or an update runs. Albums and photo totals are
read when the library version in the state changed, the settings when the settings version changed,
the info when the app version changed; all of them after a command that changes them, and in any
case every 10 minutes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import OpenframeAuthError, OpenframeClient, OpenframeError, OpenframeResponseError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=15)
MEDIUM_INTERVAL = timedelta(seconds=60)
FULL_INTERVAL = timedelta(minutes=10)
# A tick may come a little early; within this margin a tier counts as due
SLACK = timedelta(seconds=2)
BUSY_UPDATE_PHASES = frozenset({"checking", "downloading", "installing"})

type OpenframeConfigEntry = ConfigEntry[OpenframeCoordinator]


@dataclass(frozen=True)
class FrameData:
    """What the entities read, as the contract defines it."""

    state: dict[str, Any]
    display: dict[str, Any]
    # None while the frame is in safe mode: no slideshow runs then
    slideshow: dict[str, Any] | None
    sources: list[dict[str, Any]]
    update: dict[str, Any]
    info: dict[str, Any]
    settings: dict[str, Any]
    albums: list[dict[str, Any]]
    photos_total: int
    photos_visible: int

    @property
    def busy(self) -> bool:
        """A sync or an update runs, so sources and update are read every tick."""
        return self.update["phase"] in BUSY_UPDATE_PHASES or any(
            s["status"]["syncing"] or s["status"]["waiting"] for s in self.sources
        )


class OpenframeCoordinator(DataUpdateCoordinator[FrameData]):
    """Polls one frame."""

    config_entry: OpenframeConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OpenframeConfigEntry, client: OpenframeClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.frame_id: str = entry.unique_id or ""
        self._versions: tuple[int, int, str] | None = None
        self._medium_at: datetime | None = None
        self._full_at: datetime | None = None
        self._force_medium = False
        self._force_full = False

    def request_full(self) -> None:
        """Read settings, albums, info and totals on the next tick."""
        self._force_full = True

    def request_medium(self) -> None:
        """Read sources and the update state on the next tick."""
        self._force_medium = True

    async def _async_update_data(self) -> FrameData:
        try:
            return await self._read()
        except OpenframeAuthError as err:
            raise ConfigEntryAuthFailed("The frame rejected the token") from err
        except OpenframeError as err:
            raise UpdateFailed(str(err)) from err

    async def _read(self) -> FrameData:
        client = self.client
        now = dt_util.utcnow()
        previous = self.data
        state = await client.get_state()
        display = await client.get_display()
        try:
            slideshow: dict[str, Any] | None = await client.get_slideshow()
        except OpenframeResponseError as err:
            if (err.status, err.code) != (503, "safe_mode"):
                raise
            slideshow = None

        medium_due = (
            previous is None
            or self._force_medium
            or previous.busy
            or self._medium_at is None
            or now - self._medium_at >= MEDIUM_INTERVAL - SLACK
        )
        if medium_due:
            sources = await client.get_sources()
            update = await client.get_update()
            # Cleared only after the reads succeeded: a failed tick keeps the request
            self._force_medium = False
            self._medium_at = now
        else:
            assert previous is not None
            sources, update = previous.sources, previous.update

        versions = (state["libraryVersion"], state["settingsVersion"], state["appVersion"])
        changed = (
            [True, True, True]
            if self._versions is None
            else [new != old for new, old in zip(versions, self._versions, strict=True)]
        )
        everything = (
            previous is None
            or self._force_full
            or self._full_at is None
            or now - self._full_at >= FULL_INTERVAL - SLACK
        )
        library_due, settings_due, app_due = (everything or c for c in changed)
        if not (library_due or settings_due or app_due):
            assert previous is not None
            return replace(
                previous,
                state=state,
                display=display,
                slideshow=slideshow,
                sources=sources,
                update=update,
            )
        # Each version names what it covers: the library its albums and photos, the settings
        # their values, the app version the info
        if library_due:
            albums = await client.get_albums()
            photos_total = await client.count_photos()
            photos_visible = await client.count_photos(visible=True)
        else:
            assert previous is not None
            albums = previous.albums
            photos_total, photos_visible = previous.photos_total, previous.photos_visible
        if settings_due:
            settings = await client.get_settings()
        else:
            assert previous is not None
            settings = previous.settings
        if app_due:
            info = await client.get_info()
        else:
            assert previous is not None
            info = previous.info
        self._versions = versions
        if everything:
            self._force_full = False
            self._full_at = now
        return FrameData(
            state=state,
            display=display,
            slideshow=slideshow,
            sources=sources,
            update=update,
            info=info,
            settings=settings,
            albums=albums,
            photos_total=photos_total,
            photos_visible=photos_visible,
        )

    def set_slideshow(self, slideshow: dict[str, Any]) -> None:
        """Show the state a slideshow command returned, without waiting for the next tick."""
        self.async_set_updated_data(replace(self.data, slideshow=slideshow))

    def set_display(self, display: dict[str, Any]) -> None:
        self.async_set_updated_data(replace(self.data, display=display))

    def set_settings(self, settings: dict[str, Any]) -> None:
        self.request_full()
        self.async_set_updated_data(replace(self.data, settings=settings))

    def set_albums(self, albums: list[dict[str, Any]]) -> None:
        self.request_full()
        self.async_set_updated_data(replace(self.data, albums=albums))

    def set_update(self, update: dict[str, Any]) -> None:
        self.request_medium()
        self.async_set_updated_data(replace(self.data, update=update))
