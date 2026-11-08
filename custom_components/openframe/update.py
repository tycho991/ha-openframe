"""The app update: installed and latest openframe version, installed through the frame.

Installing opens Android's installation dialog on the frame, which someone confirms there. It is
offered for an update the frame has downloaded and verified, and not while Android does not let
openframe install apps.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity

IN_PROGRESS_PHASES = frozenset({"downloading", "installing"})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AppUpdate(entry.runtime_data)])


class AppUpdate(OpenframeEntity, UpdateEntity):
    """The openframe app on the frame."""

    _attr_title = "openframe"

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, "app")

    @property
    def _update(self) -> dict[str, Any]:
        return self.data.update

    @property
    def supported_features(self) -> UpdateEntityFeature:
        update = self._update
        features = UpdateEntityFeature.PROGRESS
        if update["latest"] is not None:
            features |= UpdateEntityFeature.RELEASE_NOTES
        # Only a downloaded and verified update can be installed; anything else is refused
        if update["installAllowed"] and update["phase"] == "ready":
            features |= UpdateEntityFeature.INSTALL
        return features

    @property
    def installed_version(self) -> str:
        return self._update["installedVersion"]

    @property
    def latest_version(self) -> str:
        latest = self._update["latest"]
        return latest["version"] if latest else self.installed_version

    @property
    def in_progress(self) -> bool:
        return self._update["phase"] in IN_PROGRESS_PHASES

    async def async_release_notes(self) -> str | None:
        latest = self._update["latest"]
        # Plain text from the frame, never rendered as HTML; fenced so markdown stays literal
        if latest is None:
            return None
        notes = latest["notes"].replace("```", "`\u200b``")
        return f"```text\n{notes}\n```"

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        self.coordinator.set_update(await self.command(self.coordinator.client.install_update()))
