"""Display light, slideshow controls and fresh state after a command (`frame-entities`)."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import entity_id, tick
from tests.fake_frame import FakeFrame
from tests.helpers import call


@pytest.fixture
async def photos(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer) -> None:
    for name in ("1", "2", "3"):
        frame.add_photo(f"a/{name}.jpg", comment=f"Photo {name}")
    await tick(hass, freezer)


async def test_display_off_from_an_automation(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """frame-entities › Display light › Display off from an automation."""
    display = entity_id(hass, "light", "display")
    await call(hass, "light", "turn_off", display)
    assert frame.display["on"] is False
    state = hass.states.get(display)
    assert state.state == STATE_OFF
    assert state.attributes["cause"] == "manual"
    assert state.attributes["next_change"] is None


async def test_no_device_administrator(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Display light › No device administrator."""
    display = entity_id(hass, "light", "display")
    frame.display.update(available=False, cause="none")
    await tick(hass, freezer)
    assert hass.states.get(display).state == STATE_ON
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "light", "turn_off", display)
    assert caught.value.translation_key == "display_unavailable"
    assert frame.display["on"] is True
    assert hass.states.get(display).state == STATE_ON


async def test_nothing_to_control(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Display light › Nothing to control."""
    frame.display.update(available=False, cause="none")
    frame.display["brightness"]["available"] = False
    await tick(hass, freezer)
    assert hass.states.get(entity_id(hass, "light", "display")).state == STATE_UNAVAILABLE


async def test_pause_from_home_assistant(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, photos: None
) -> None:
    """frame-entities › Slideshow controls › Pause from Home Assistant."""
    slideshow = entity_id(hass, "switch", "slideshow")
    assert hass.states.get(slideshow).state == STATE_ON
    await call(hass, "switch", "turn_off", slideshow)
    assert frame.paused is True
    assert hass.states.get(slideshow).state == STATE_OFF
    await call(hass, "switch", "turn_on", slideshow)
    assert frame.paused is False
    assert hass.states.get(slideshow).state == STATE_ON


async def test_previous_photo(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, photos: None
) -> None:
    """frame-entities › Slideshow controls › Previous photo."""
    await call(hass, "button", "press", entity_id(hass, "button", "previous_photo"))
    assert frame.on_screen().path == "a/3.jpg"
    assert hass.states.get(entity_id(hass, "sensor", "current_photo")).state == "Photo 3"


async def test_next_photo_at_night(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, photos: None
) -> None:
    """frame-entities › Slideshow controls › Next photo at night."""
    await call(hass, "light", "turn_off", entity_id(hass, "light", "display"))
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "button", "press", entity_id(hass, "button", "next_photo"))
    assert caught.value.translation_key == "display_off"
    assert str(caught.value) == "The display is off"
    assert frame.on_screen().path == "a/1.jpg"
    assert hass.states.get(entity_id(hass, "sensor", "current_photo")).state == "Photo 1"


async def test_fresh_state_after_next_photo(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, photos: None
) -> None:
    """frame-connection › Fresh state after a command › Next photo."""
    frame.reset_requests()
    await call(hass, "button", "press", entity_id(hass, "button", "next_photo"))
    assert frame.requests == [("POST", "/slideshow")], "no poll needed for the new state"
    assert hass.states.get(entity_id(hass, "sensor", "current_photo")).state == "Photo 2"
