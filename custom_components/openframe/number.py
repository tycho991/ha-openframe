"""Number settings: interval and transition duration, with the frame's ranges."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity


@dataclass(frozen=True, kw_only=True)
class SettingNumberDescription(NumberEntityDescription):
    field: str


NUMBERS = (
    SettingNumberDescription(
        key="interval",
        field="intervalSeconds",
        entity_category=EntityCategory.CONFIG,
        native_min_value=5,
        native_max_value=86400,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
    ),
    SettingNumberDescription(
        key="transition_duration",
        field="transitionDurationMs",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=5000,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        mode=NumberMode.BOX,
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
        return self.data.settings[self.entity_description.field]

    async def async_set_native_value(self, value: float) -> None:
        patch = {self.entity_description.field: round(value)}
        self.coordinator.set_settings(
            await self.command(self.coordinator.client.patch_settings(patch))
        )
