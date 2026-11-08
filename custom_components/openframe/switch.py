"""Switches: display, slideshow, settings and one per album."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FrameData, OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity, add_dynamic_entities, album_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            DisplaySwitch(coordinator),
            SlideshowSwitch(coordinator),
            *(SettingSwitch(coordinator, d) for d in SETTING_SWITCHES),
        ]
    )
    add_dynamic_entities(
        entry,
        async_add_entities,
        lambda data: (album["name"] for album in data.albums),
        lambda name: [AlbumSwitch(coordinator, name)],
    )


class DisplaySwitch(OpenframeEntity, SwitchEntity):
    """The display, with why it is in its state and when it changes next by itself."""

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "display")

    @property
    def available(self) -> bool:
        # Without device administrator rights the frame cannot switch its display
        return super().available and self.data.display["available"]

    @property
    def is_on(self) -> bool:
        return self.data.display["on"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"cause": self.data.display["cause"], "next_change": self.data.display["nextChange"]}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._switch(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._switch(False)

    async def _switch(self, on: bool) -> None:
        self.coordinator.set_display(await self.command(self.coordinator.client.set_display(on)))


class SlideshowSwitch(OpenframeEntity, SwitchEntity):
    """On while the slideshow plays, off while it is paused."""

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "slideshow")

    @property
    def available(self) -> bool:
        return super().available and self.data.slideshow is not None

    @property
    def is_on(self) -> bool | None:
        slideshow = self.data.slideshow
        return None if slideshow is None else not slideshow["paused"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._control("resume")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._control("pause")

    async def _control(self, action: str) -> None:
        client = self.coordinator.client
        self.coordinator.set_slideshow(await self.command(client.control_slideshow(action)))


@dataclass(frozen=True, kw_only=True)
class SettingSwitchDescription(SwitchEntityDescription):
    value: Callable[[dict[str, Any]], bool]
    patch: Callable[[bool], dict[str, Any]]
    available: Callable[[FrameData], bool] = lambda data: True


SETTING_SWITCHES = (
    SettingSwitchDescription(
        key="clock",
        entity_category=EntityCategory.CONFIG,
        value=lambda settings: settings["clock"]["enabled"],
        patch=lambda on: {"clock": {"enabled": on}},
    ),
    SettingSwitchDescription(
        key="display_schedule",
        entity_category=EntityCategory.CONFIG,
        value=lambda settings: settings["displaySchedule"]["enabled"],
        patch=lambda on: {"displaySchedule": {"enabled": on}},
        # The schedule can be switched on only while the frame can switch its display
        available=lambda data: data.display["available"],
    ),
    SettingSwitchDescription(
        key="auto_update_check",
        entity_category=EntityCategory.CONFIG,
        value=lambda settings: settings["autoUpdateCheck"],
        patch=lambda on: {"autoUpdateCheck": on},
    ),
)


class SettingSwitch(OpenframeEntity, SwitchEntity):
    """A setting that is on or off; a change sends only this setting."""

    entity_description: SettingSwitchDescription

    def __init__(
        self, coordinator: OpenframeCoordinator, description: SettingSwitchDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.available(self.data)

    @property
    def is_on(self) -> bool:
        return self.entity_description.value(self.data.settings)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, on: bool) -> None:
        patch = self.entity_description.patch(on)
        self.coordinator.set_settings(
            await self.command(self.coordinator.client.patch_settings(patch))
        )


class AlbumSwitch(OpenframeEntity, SwitchEntity):
    """On while the album is shown, off while it is hidden."""

    def __init__(self, coordinator: OpenframeCoordinator, name: str) -> None:
        super().__init__(coordinator, f"album_{name}", translation_key="album")
        self.album = name
        self._attr_translation_placeholders = {"album": name}
        # Sub-albums would crowd the device page; the user enables the ones they need
        self._attr_entity_registry_enabled_default = "/" not in name

    @property
    def available(self) -> bool:
        return super().available and album_of(self.data, self.album) is not None

    @property
    def is_on(self) -> bool | None:
        album = album_of(self.data, self.album)
        return None if album is None else not album["hidden"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        album = album_of(self.data, self.album)
        return None if album is None else {"photos": album["count"]}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(hidden=False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(hidden=True)

    async def _set(self, hidden: bool) -> None:
        client = self.coordinator.client
        self.coordinator.set_albums(await self.command(client.patch_album(self.album, hidden)))
