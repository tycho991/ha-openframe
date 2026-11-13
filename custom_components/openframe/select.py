"""Select settings: order, transition, fill mode, orientation and brightness mode, with the
frame's choices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FrameData, OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity


@dataclass(frozen=True, kw_only=True)
class SettingSelectDescription(SelectEntityDescription):
    value: Callable[[dict[str, Any]], str]
    patch: Callable[[str], dict[str, Any]]
    # The choices offered now, when they depend on the frame; otherwise `options`
    choices: Callable[[FrameData], list[str]] | None = None


BRIGHTNESS_MODES = ["system", "manual", "auto"]


def brightness_modes(data: FrameData) -> list[str]:
    """Automatic only on a frame with a light sensor; a stored `auto` stays offered."""
    if data.display["brightness"]["autoSupported"] or data.settings["brightness"]["mode"] == "auto":
        return BRIGHTNESS_MODES
    return [mode for mode in BRIGHTNESS_MODES if mode != "auto"]


# The choices are the enums `Order`, `Transition`, `FillMode`, `Orientation` and the brightness
# mode of the contract
SELECTS = (
    SettingSelectDescription(
        key="order",
        entity_category=EntityCategory.CONFIG,
        options=["shuffle", "chronological"],
        value=lambda settings: settings["order"],
        patch=lambda option: {"order": option},
    ),
    SettingSelectDescription(
        key="transition",
        entity_category=EntityCategory.CONFIG,
        options=["fade", "slide", "none"],
        value=lambda settings: settings["transition"],
        patch=lambda option: {"transition": option},
    ),
    SettingSelectDescription(
        key="fill_mode",
        entity_category=EntityCategory.CONFIG,
        options=["auto", "fill", "fit"],
        value=lambda settings: settings["fillMode"],
        patch=lambda option: {"fillMode": option},
    ),
    SettingSelectDescription(
        key="orientation",
        entity_category=EntityCategory.CONFIG,
        options=["landscape", "portrait"],
        value=lambda settings: settings["orientation"],
        patch=lambda option: {"orientation": option},
    ),
    SettingSelectDescription(
        key="brightness_mode",
        entity_category=EntityCategory.CONFIG,
        options=BRIGHTNESS_MODES,
        value=lambda settings: settings["brightness"]["mode"],
        patch=lambda option: {"brightness": {"mode": option}},
        choices=brightness_modes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(SettingSelect(entry.runtime_data, d) for d in SELECTS)


class SettingSelect(OpenframeEntity, SelectEntity):
    """A setting with a set of choices; a change sends only this setting."""

    entity_description: SettingSelectDescription

    def __init__(
        self, coordinator: OpenframeCoordinator, description: SettingSelectDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def options(self) -> list[str]:
        choices = self.entity_description.choices
        return super().options if choices is None else choices(self.data)

    @property
    def current_option(self) -> str:
        return self.entity_description.value(self.data.settings)

    async def async_select_option(self, option: str) -> None:
        patch = self.entity_description.patch(option)
        self.coordinator.set_settings(
            await self.command(self.coordinator.client.patch_settings(patch))
        )
