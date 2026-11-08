"""Sensors: the photo on screen, photo and album counts, and the last sync of each source."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import FrameData, OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity, SourceEntity, add_dynamic_entities

MAX_STATE = 255


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            CurrentPhotoSensor(coordinator),
            *(CountSensor(coordinator, description) for description in COUNTS),
        ]
    )
    add_dynamic_entities(
        entry,
        async_add_entities,
        lambda data: (source["id"] for source in data.sources),
        lambda source_id: [LastSyncSensor(coordinator, source_id)],
    )


class CurrentPhotoSensor(OpenframeEntity, SensorEntity):
    """The comment of the photo on screen, or its file name without one."""

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "current_photo")

    @property
    def available(self) -> bool:
        return super().available and self.data.slideshow is not None

    @property
    def _photo(self) -> dict[str, Any] | None:
        slideshow = self.data.slideshow
        return slideshow["photo"] if slideshow else None

    @property
    def native_value(self) -> str | None:
        photo = self._photo
        if photo is None:
            return None
        name = photo["comment"] or photo["path"].rpartition("/")[2]
        # A comment may have 500 characters; Home Assistant keeps a state of at most 255
        return name if len(name) <= MAX_STATE else name[: MAX_STATE - 1] + "…"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        photo = self._photo
        if photo is None:
            return None
        location = photo["location"]
        return {
            "album": photo["album"],
            "taken_at": photo["takenAt"],
            "place": location["place"] if location else None,
            "photo_id": photo["id"],
        }


@dataclass(frozen=True, kw_only=True)
class CountDescription(SensorEntityDescription):
    value: Callable[[FrameData], int]


COUNTS = (
    CountDescription(
        key="photos",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.photos_total,
    ),
    CountDescription(
        key="photos_visible",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.photos_visible,
    ),
    CountDescription(
        key="photos_hidden",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: data.photos_total - data.photos_visible,
    ),
    CountDescription(
        key="albums",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda data: len(data.albums),
    ),
)


class CountSensor(OpenframeEntity, SensorEntity):
    entity_description: CountDescription

    def __init__(self, coordinator: OpenframeCoordinator, description: CountDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int:
        return self.entity_description.value(self.data)


class LastSyncSensor(SourceEntity, SensorEntity):
    """Time of the last sync of a source, with what it changed."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: OpenframeCoordinator, source_id: str) -> None:
        super().__init__(coordinator, "last_sync", source_id)

    @property
    def native_value(self) -> datetime | None:
        source = self.source
        at = source["status"]["lastSyncAt"] if source else None
        return dt_util.parse_datetime(at) if at else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        source = self.source
        if source is None:
            return None
        status = source["status"]
        return {key: status[key] for key in ("added", "updated", "removed")}
