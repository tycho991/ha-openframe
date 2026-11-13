"""The display as a light: on and off, and its brightness while openframe may set it."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import OpenframeConfigEntry, OpenframeCoordinator
from .entity import OpenframeEntity

KEY = "display"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    # Versions before the light had the display as a switch with the same unique ID; Home
    # Assistant cannot move an entity to another domain, so the switch goes
    registry = er.async_get(hass)
    unique_id = f"{coordinator.frame_id}_{KEY}"
    if switch := registry.async_get_entity_id(Platform.SWITCH, DOMAIN, unique_id):
        registry.async_remove(switch)
    async_add_entities([DisplayLight(coordinator)])


def to_percent(brightness: int) -> int:
    """Home Assistant's brightness (1 to 255) as openframe's level (1 to 100)."""
    return max(1, round(brightness * 100 / 255))


def to_brightness(percent: int) -> int:
    """openframe's level (0 to 100) as Home Assistant's brightness; 0 % does not read as off."""
    return max(1, round(percent * 255 / 100))


class DisplayLight(OpenframeEntity, LightEntity):
    """The display, with why it is in its state, when it changes next by itself, and how
    bright it is."""

    def __init__(self, coordinator: OpenframeCoordinator) -> None:
        super().__init__(coordinator, KEY)

    @property
    def _brightness(self) -> dict[str, Any]:
        return self.data.display["brightness"]

    @property
    def _dimmable(self) -> bool:
        # Without the permission to modify system settings the frame cannot set the brightness
        return self._brightness["available"]

    @property
    def available(self) -> bool:
        display = self.data.display
        return super().available and (display["available"] or self._dimmable)

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        return {ColorMode.BRIGHTNESS} if self._dimmable else {ColorMode.ONOFF}

    @property
    def color_mode(self) -> ColorMode:
        return ColorMode.BRIGHTNESS if self._dimmable else ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        return self.data.display["on"]

    @property
    def brightness(self) -> int | None:
        if not self.is_on or not self._dimmable:
            return None
        return to_brightness(self._brightness["level"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        display = self.data.display
        return {
            "cause": display["cause"],
            "next_change": display["nextChange"],
            "dimmed": self._brightness["dimmed"],
            "auto": self._brightness["auto"],
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        percent = None if brightness is None else to_percent(brightness)
        # A frame without device administration can still be dimmed; a plain turn on asks for
        # the display as before, and the frame refuses it with `display_unavailable`
        on = True if percent is None or self.data.display["available"] else None
        await self._send(on, percent)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(False, None)

    async def _send(self, on: bool | None, percent: int | None) -> None:
        coordinator = self.coordinator
        coordinator.set_display(await self.command(coordinator.client.set_display(on, percent)))
        if percent is not None:
            # Outside a dim period the level becomes the stored brightness with mode `manual`
            coordinator.request_full()
