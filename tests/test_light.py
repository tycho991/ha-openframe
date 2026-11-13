"""Brightness of the display light and the former display switch (`frame-entities`)."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe.const import DOMAIN
from custom_components.openframe.light import to_brightness, to_percent
from tests.conftest import entity_id, mock_entry, tick
from tests.fake_frame import FRAME_ID, FakeFrame
from tests.helpers import call


def test_every_level_round_trips() -> None:
    for percent in range(1, 101):
        assert to_percent(to_brightness(percent)) == percent
    assert to_brightness(0) == 1, "a level of 0 % does not read as off"
    assert to_percent(1) == 1


async def test_dim_from_an_automation(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Brightness of the display light › Dim from an automation."""
    display = entity_id(hass, "light", "display")
    await call(hass, "light", "turn_on", display, brightness_pct=50)
    assert frame.display["brightness"]["level"] == 50
    assert frame.settings["brightness"] == {"mode": "manual", "level": 50}
    state = hass.states.get(display)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == to_brightness(50)
    # The display was on: only the brightness is sent, `on` would be a manual switch
    assert frame.bodies[-1] == ("PUT", "/display", {"brightness": 50})
    # The brightness became the frame's fixed level, which the next tick reads
    frame.reset_requests()
    await tick(hass, freezer)
    assert frame.count("GET", "/settings") == 1
    assert hass.states.get(entity_id(hass, "select", "brightness_mode")).state == "manual"


async def test_dimmed_by_the_schedule(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Brightness of the display light › Dimmed by the schedule."""
    frame.display["brightness"].update(level=20, dimmed=True)
    await tick(hass, freezer)
    state = hass.states.get(entity_id(hass, "light", "display"))
    assert state.attributes[ATTR_BRIGHTNESS] == to_brightness(20)
    assert state.attributes["dimmed"] is True
    assert state.attributes["auto"] is False


async def test_brightness_during_a_dim_period_keeps_the_settings(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.display["brightness"].update(level=20, dimmed=True)
    await tick(hass, freezer)
    await call(hass, "light", "turn_on", entity_id(hass, "light", "display"), brightness_pct=50)
    assert frame.display["brightness"]["level"] == 50
    assert frame.settings["brightness"] == {"mode": "system", "level": 80}


async def test_without_permission(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Brightness of the display light › Without permission."""
    display = entity_id(hass, "light", "display")
    frame.display["brightness"]["available"] = False
    await tick(hass, freezer)
    state = hass.states.get(display)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert state.attributes.get(ATTR_BRIGHTNESS) is None
    await call(hass, "light", "turn_off", display)
    assert hass.states.get(display).state == STATE_OFF
    await call(hass, "light", "turn_on", display, brightness_pct=30)
    assert hass.states.get(display).state == STATE_ON
    assert frame.bodies[-1] == ("PUT", "/display", {"on": True})
    assert frame.display["brightness"]["level"] == 80


async def test_permission_withdrawn_since_the_last_read(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """frame-entities › Errors of commands: the frame refuses a brightness it may not set."""
    frame.display["brightness"]["available"] = False
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "light", "turn_on", entity_id(hass, "light", "display"), brightness=100)
    assert caught.value.translation_key == "brightness_unavailable"
    assert frame.display["brightness"]["level"] == 80


async def test_dimmed_without_device_administrator(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.display.update(available=False)
    await tick(hass, freezer)
    await call(hass, "light", "turn_on", entity_id(hass, "light", "display"), brightness_pct=40)
    assert frame.bodies[-1] == ("PUT", "/display", {"brightness": 40})
    assert frame.display["brightness"]["level"] == 40


async def test_brightness_keeps_a_woken_display_woken(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Brightness of the display light › Woken display dimmed: no `on` is sent,
    which openframe would take as a manual switch that ends the wake."""
    frame.display.update(cause="wake")
    await tick(hass, freezer)
    await call(hass, "light", "turn_on", entity_id(hass, "light", "display"), brightness_pct=30)
    assert frame.bodies[-1] == ("PUT", "/display", {"brightness": 30})
    assert frame.display["cause"] == "wake"


async def test_turn_on_of_a_display_that_is_on_sends_nothing(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.reset_requests()
    await call(hass, "light", "turn_on", entity_id(hass, "light", "display"))
    assert frame.count("PUT", "/display") == 0


async def test_display_off_without_device_administrator(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """A brightness cannot turn on a display the frame cannot switch: the request fails as a
    whole instead of succeeding with the display still off."""
    frame.display.update(on=False, available=False, cause="none")
    await tick(hass, freezer)
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "light", "turn_on", entity_id(hass, "light", "display"), brightness_pct=50)
    assert caught.value.translation_key == "display_unavailable"
    assert frame.display["brightness"]["level"] == 80


async def test_update_from_a_version_with_the_switch(
    hass: HomeAssistant, frame: FakeFrame, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Former display switch › Update from a version with the switch."""
    config_entry = mock_entry(frame)
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{FRAME_ID}_display",
        suggested_object_id="test_frame_display",
        config_entry=config_entry,
    )
    assert old.entity_id == "switch.test_frame_display"
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get("switch.test_frame_display") is None
    assert hass.states.get("switch.test_frame_display") is None
    assert hass.states.get("light.test_frame_display").state == STATE_ON
    await call(hass, "light", "turn_off", "light.test_frame_display")
    assert frame.display["on"] is False


async def test_former_switch_goes_also_while_the_frame_is_outdated(
    hass: HomeAssistant, frame: FakeFrame
) -> None:
    frame.before_brightness = True
    config_entry = mock_entry(frame)
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{FRAME_ID}_display",
        suggested_object_id="test_frame_display",
        config_entry=config_entry,
    )
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert registry.async_get("switch.test_frame_display") is None
    assert config_entry.minor_version == 2


async def test_setup_without_a_former_switch(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    assert er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{FRAME_ID}_display") is None
    assert hass.states.get("light.test_frame_display").state == STATE_ON
