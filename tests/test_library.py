"""Photo counts and album switches (`frame-entities`)."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import entity_id, tick
from tests.fake_frame import FakeFrame
from tests.helpers import call


def state(hass: HomeAssistant, platform: str, key: str) -> str:
    return hass.states.get(entity_id(hass, platform, key)).state


async def test_photo_hidden_in_the_web_ui(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Photo counts › Photo hidden in the web UI."""
    for number in range(120):
        frame.add_photo(f"a/{number:03}.jpg")
    frame.add_photo("b/hidden.jpg", hidden=True)
    await tick(hass, freezer)
    assert state(hass, "sensor", "photos") == "121"
    assert state(hass, "sensor", "photos_visible") == "120"
    assert state(hass, "sensor", "photos_hidden") == "1"
    assert state(hass, "sensor", "albums") == "2"

    frame.photos[5].hidden = True
    frame.library_version += 1
    await tick(hass, freezer)
    assert state(hass, "sensor", "photos_visible") == "119"
    assert state(hass, "sensor", "photos_hidden") == "2"


async def test_hide_an_album(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › One switch per album › Hide an album."""
    frame.add_photo("holiday/1.jpg")
    frame.add_photo("holiday/2024/2.jpg")
    frame.add_photo("home/3.jpg")
    await tick(hass, freezer)
    holiday = entity_id(hass, "switch", "album_holiday")
    assert hass.states.get(holiday).state == STATE_ON
    assert hass.states.get(holiday).attributes["photos"] == 2
    await call(hass, "switch", "turn_off", holiday)
    assert ("PATCH", "/albums", {"name": "holiday", "hidden": True}) in frame.bodies
    assert hass.states.get(holiday).state == STATE_OFF
    assert [p.path for p in frame.visible_photos()] == ["home/3.jpg"]
    await call(hass, "switch", "turn_on", holiday)
    assert len(frame.visible_photos()) == 3


async def test_new_album(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › One switch per album › New album."""
    frame.add_photo("holiday/1.jpg")
    await tick(hass, freezer)
    assert entity_id(hass, "switch", "album_holiday")
    frame.add_photo("2026/1.jpg")
    await tick(hass, freezer)
    assert hass.states.get(entity_id(hass, "switch", "album_2026")).state == STATE_ON


async def test_sub_album(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › One switch per album › Sub-album."""
    frame.add_photo("holiday/2024/1.jpg")
    await tick(hass, freezer)
    registry = er.async_get(hass)
    sub = registry.async_get(entity_id(hass, "switch", "album_holiday/2024"))
    assert sub.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    top = registry.async_get(entity_id(hass, "switch", "album_holiday"))
    assert top.disabled_by is None


async def test_removed_album_becomes_unavailable(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.add_photo("holiday/1.jpg")
    frame.add_photo("home/1.jpg")
    await tick(hass, freezer)
    frame.photos = [p for p in frame.photos if p.album != "holiday"]
    frame.library_version += 1
    await tick(hass, freezer)
    assert state(hass, "switch", "album_holiday") == STATE_UNAVAILABLE
    assert state(hass, "switch", "album_home") == STATE_ON
