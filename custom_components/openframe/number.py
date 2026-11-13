"""Number settings: interval, transition duration and dim level, with the frame's ranges."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity


@dataclass(frozen=True, kw_only=True)
class SettingNumberDescription(NumberEntityDescription):
    value: Callable[[dict[str, Any]], int]
    patch: Callable[[int], dict[str, Any]]


NUMBERS = (
    SettingNumberDescription(
        key="interval",
        entity_category=EntityCategory.CONFIG,
        native_min_value=5,
        native_max_value=86400,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
        value=lambda settings: settings["intervalSeconds"],
        patch=lambda value: {"intervalSeconds": value},
    ),
    SettingNumberDescription(
        key="transition_duration",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=5000,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        mode=NumberMode.BOX,
        value=lambda settings: settings["transitionDurationMs"],
        patch=lambda value: {"transitionDurationMs": value},
    ),
    SettingNumberDescription(
        key="dim_level",
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        value=lambda settings: settings["displaySchedule"]["dimLevel"],
        patch=lambda value: {"displaySchedule": {"dimLevel": value}},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SettingNumber(entry.runtime_data, d) for d in NUMBERS)


class SettingNumber(OpenframeEntity, NumberEntity):
    """A number setting; a change sends only this setting."""

    entity_description: SettingNumberDescription

    def __init__(
        self, coordinator: OpenframeCoordinator, description: SettingNumberDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int:
        return self.entity_description.value(self.data.settings)

    async def async_set_native_value(self, value: float) -> None:
        patch = self.entity_description.patch(round(value))
        self.coordinator.set_settings(
            await self.command(self.coordinator.client.patch_settings(patch))
        )
