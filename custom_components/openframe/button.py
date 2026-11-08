"""Buttons: next and previous photo, update check, leaving safe mode, and one sync per source."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities(
        [
            StepButton(coordinator, "next"),
            StepButton(coordinator, "previous"),
            CheckUpdateButton(coordinator),
            LeaveSafeModeButton(coordinator),
        ]
    )
    add_dynamic_entities(
        entry,
        async_add_entities,
        lambda data: (source["id"] for source in data.sources),
        lambda source_id: [SyncButton(coordinator, source_id)],
    )


class StepButton(OpenframeEntity, ButtonEntity):
    """Next or previous photo; the frame refuses while its display is off."""

    def __init__(self, coordinator: OpenframeCoordinator, action: str) -> None:
        super().__init__(coordinator, f"{action}_photo")
        self.action = action

    @property
    def available(self) -> bool:
        return super().available and self.data.slideshow is not None

    async def async_press(self) -> None:
        client = self.coordinator.client
        self.coordinator.set_slideshow(await self.command(client.control_slideshow(self.action)))


class CheckUpdateButton(OpenframeEntity, ButtonEntity):
    """Ask the frame to check for an update now, also while automatic checks are off."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "check_update")

    async def async_press(self) -> None:
        self.coordinator.set_update(await self.command(self.coordinator.client.check_update()))


class LeaveSafeModeButton(OpenframeEntity, ButtonEntity):
    """Start the frame normally again; available only in safe mode."""

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "leave_safe_mode")

    @property
    def available(self) -> bool:
        return super().available and self.data.state["safeMode"]

    async def async_press(self) -> None:
        await self.command(self.coordinator.client.exit_safe_mode())
        # The frame restarts; the next polls show it back in normal mode
        self.coordinator.request_full()
        await self.coordinator.async_request_refresh()


class SyncButton(SourceEntity, ButtonEntity):
    """Start a sync of one remote source."""

    def __init__(self, coordinator: OpenframeCoordinator, source_id: str) -> None:
        super().__init__(coordinator, "sync", source_id)

    async def async_press(self) -> None:
        await self.command(self.coordinator.client.sync_source(self.source_id))
        self.coordinator.request_medium()
        await self.coordinator.async_request_refresh()
