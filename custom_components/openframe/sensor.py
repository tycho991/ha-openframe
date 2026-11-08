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
from .entity import OpenframeEntity, add_dynamic_entities, source_of


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
        return photo["comment"] or photo["path"].rpartition("/")[2]

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


class LastSyncSensor(OpenframeEntity, SensorEntity):
    """Time of the last sync of a source, with what it changed."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: OpenframeCoordinator, source_id: str) -> None:
        super().__init__(coordinator, f"last_sync_{source_id}", translation_key="last_sync")
        self.source_id = source_id
        source = source_of(coordinator.data, source_id)
        self._attr_translation_placeholders = {
            "source": source["settings"]["name"] if source else source_id
        }

    @property
    def available(self) -> bool:
        return super().available and source_of(self.data, self.source_id) is not None

    @property
    def native_value(self) -> datetime | None:
        source = source_of(self.data, self.source_id)
        at = source["status"]["lastSyncAt"] if source else None
        return dt_util.parse_datetime(at) if at else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        source = source_of(self.data, self.source_id)
        if source is None:
            return None
        status = source["status"]
        return {key: status[key] for key in ("added", "updated", "removed")}
