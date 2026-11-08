"""Select settings: order, transition, fill mode and orientation, with the frame's choices."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity


@dataclass(frozen=True, kw_only=True)
class SettingSelectDescription(SelectEntityDescription):
    field: str


# The choices are the enums `Order`, `Transition`, `FillMode` and `Orientation` of the contract
SELECTS = (
    SettingSelectDescription(
        key="order",
        field="order",
        entity_category=EntityCategory.CONFIG,
        options=["shuffle", "chronological"],
    ),
    SettingSelectDescription(
        key="transition",
        field="transition",
        entity_category=EntityCategory.CONFIG,
        options=["fade", "slide", "none"],
    ),
    SettingSelectDescription(
        key="fill_mode",
        field="fillMode",
        entity_category=EntityCategory.CONFIG,
        options=["auto", "fill", "fit"],
    ),
    SettingSelectDescription(
        key="orientation",
        field="orientation",
        entity_category=EntityCategory.CONFIG,
        options=["landscape", "portrait"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SettingSelect(entry.runtime_data, d) for d in SELECTS)


class SettingSelect(OpenframeEntity, SelectEntity):
    """A setting with a fixed set of choices; a change sends only this setting."""

    entity_description: SettingSelectDescription

    def __init__(
        self, coordinator: OpenframeCoordinator, description: SettingSelectDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str:
        return self.data.settings[self.entity_description.field]

    async def async_select_option(self, option: str) -> None:
        patch = {self.entity_description.field: option}
        self.coordinator.set_settings(
            await self.command(self.coordinator.client.patch_settings(patch))
        )
