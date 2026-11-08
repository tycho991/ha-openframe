"""Problem sensors: safe mode, transition fallback and a failed sync per source."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity, SourceEntity, add_dynamic_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([SafeModeSensor(coordinator), TransitionFallbackSensor(coordinator)])
    add_dynamic_entities(
        entry,
        async_add_entities,
        lambda data: (source["id"] for source in data.sources),
        lambda source_id: [SyncProblemSensor(coordinator, source_id)],
    )


class SafeModeSensor(OpenframeEntity, BinarySensorEntity):
    """On while the frame runs in safe mode after repeated crashes."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "safe_mode")

    @property
    def is_on(self) -> bool:
        return self.data.state["safeMode"]


class TransitionFallbackSensor(OpenframeEntity, BinarySensorEntity):
    """On while the frame changes photos instantly because its display could not keep up."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "transition_fallback")

    @property
    def is_on(self) -> bool:
        return self.data.state["transitionFallback"]


class SyncProblemSensor(SourceEntity, BinarySensorEntity):
    """On while the last sync of a source failed, with the error."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: OpenframeCoordinator, source_id: str) -> None:
        super().__init__(coordinator, "sync_problem", source_id)

    @property
    def is_on(self) -> bool | None:
        source = self.source
        return None if source is None else source["status"]["ok"] is False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        source = self.source
        return None if source is None else {"error": source["status"]["error"]}
