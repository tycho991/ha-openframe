"""Base class of the frame's entities, the device and the commands' errors."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OpenframeAuthError, OpenframeConnectionError, OpenframeResponseError
from .const import DOMAIN
from .coordinator import FrameData, OpenframeConfigEntry, OpenframeCoordinator

# Refusals with a message of their own; any other refusal names the frame's message
KNOWN_REFUSALS = frozenset(
    {
        "display_off",
        "display_unavailable",
        "safe_mode",
        "update_not_ready",
        "install_not_allowed",
        "install_in_progress",
        "install_cooldown",
        "source_no_folder",
        "not_in_safe_mode",
    }
)


def device_info(coordinator: OpenframeCoordinator) -> DeviceInfo:
    data = coordinator.data
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.frame_id)},
        name=data.info["name"],
        manufacturer="openframe",
        model="openframe",
        sw_version=data.state["appVersion"],
        hw_version=f"Android {data.info['androidVersion']}",
        configuration_url=coordinator.client.frame_url,
    )


@callback
def follow_app_version(hass: HomeAssistant, coordinator: OpenframeCoordinator) -> None:
    """Show the app version the frame reports on its device, also after it updated itself."""
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        (DOMAIN, coordinator.frame_id), coordinator.config_entry.entry_id
    )
    version = coordinator.data.state["appVersion"] if coordinator.data else None
    if device is not None and version is not None and device.sw_version != version:
        registry.async_update_device(device.id, sw_version=version)


class OpenframeEntity(CoordinatorEntity[OpenframeCoordinator]):
    """An entity of one frame."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenframeCoordinator,
        key: str,
        translation_key: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = translation_key or key
        self._attr_unique_id = f"{coordinator.frame_id}_{key}"
        self._attr_device_info = device_info(coordinator)

    @property
    def data(self) -> FrameData:
        return self.coordinator.data

    async def command[T](self, call: Awaitable[T]) -> T:
        """Run a command; a refusal or no answer becomes a translated error."""
        try:
            return await call
        except OpenframeAuthError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unauthorized"
            ) from err
        except OpenframeConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_answer"
            ) from err
        except OpenframeResponseError as err:
            if err.code in KNOWN_REFUSALS:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key=err.code
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refused",
                translation_placeholders={"message": err.message},
            ) from err


def add_dynamic_entities(
    entry: OpenframeConfigEntry,
    add_entities: Callable[[Iterable[Entity]], None],
    keys: Callable[[FrameData], Iterable[str]],
    create: Callable[[str], Iterable[Entity]],
) -> None:
    """Add entities for albums or sources as they appear, without a reload.

    Entities of an album or source that disappears stay and report themselves unavailable, so
    automations that reference them do not break silently.
    """
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def check() -> None:
        if coordinator.data is None:
            return
        new = [key for key in keys(coordinator.data) if key not in known]
        if new:
            known.update(new)
            add_entities([entity for key in new for entity in create(key)])

    check()
    entry.async_on_unload(coordinator.async_add_listener(check))


def album_of(data: FrameData, name: str) -> dict[str, Any] | None:
    return next((a for a in data.albums if a["name"] == name), None)


def source_of(data: FrameData, source_id: str) -> dict[str, Any] | None:
    return next((s for s in data.sources if s["id"] == source_id), None)


def source_names(data: FrameData) -> dict[str, str]:
    return {s["id"]: s["settings"]["name"] for s in data.sources}


class SourceEntity(OpenframeEntity):
    """An entity of one remote source, named after it; unavailable while the source is gone.

    The name is taken when the entity is created; the entry reloads when a source is renamed.
    """

    def __init__(self, coordinator: OpenframeCoordinator, key: str, source_id: str) -> None:
        super().__init__(coordinator, f"{key}_{source_id}", translation_key=key)
        self.source_id = source_id
        self._attr_translation_placeholders = {
            "source": source_names(coordinator.data).get(source_id, source_id)
        }

    @property
    def source(self) -> dict[str, Any] | None:
        return source_of(self.data, self.source_id)

    @property
    def available(self) -> bool:
        return super().available and self.source is not None
