"""Settings as configuration entities (`frame-entities` › Settings as configuration entities)."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import entity_id, tick
from tests.fake_frame import FakeFrame
from tests.helpers import call


def patches(frame: FakeFrame) -> list:
    return [body for method, path, body in frame.bodies if (method, path) == ("PATCH", "/settings")]


async def test_interval_from_an_automation(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """frame-entities › Settings as configuration entities › Interval from an automation."""
    before = dict(frame.settings)
    interval = entity_id(hass, "number", "interval")
    await call(hass, "number", "set_value", interval, value=60)
    assert patches(frame) == [{"intervalSeconds": 60}]
    assert frame.settings == before | {"intervalSeconds": 60}
    assert hass.states.get(interval).state == "60"


async def test_value_out_of_range(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """frame-entities › Settings as configuration entities › Value out of range."""
    interval = entity_id(hass, "number", "interval")
    state = hass.states.get(interval)
    assert (state.attributes["min"], state.attributes["max"]) == (5, 86400)
    with pytest.raises(ServiceValidationError):
        await call(hass, "number", "set_value", interval, value=2)
    assert patches(frame) == []


async def test_fill_mode(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """frame-entities › Settings as configuration entities › Fill mode."""
    fill_mode = entity_id(hass, "select", "fill_mode")
    assert hass.states.get(fill_mode).attributes["options"] == ["auto", "fill", "fit"]
    await call(hass, "select", "select_option", fill_mode, option="fit")
    assert patches(frame) == [{"fillMode": "fit"}]
    assert hass.states.get(fill_mode).state == "fit"


@pytest.mark.parametrize(
    ("platform", "key", "service", "data", "body"),
    [
        (
            "number",
            "transition_duration",
            "set_value",
            {"value": 1200},
            {"transitionDurationMs": 1200},
        ),
        (
            "select",
            "order",
            "select_option",
            {"option": "chronological"},
            {"order": "chronological"},
        ),
        ("select", "transition", "select_option", {"option": "slide"}, {"transition": "slide"}),
        (
            "select",
            "orientation",
            "select_option",
            {"option": "portrait"},
            {"orientation": "portrait"},
        ),
        (
            "select",
            "brightness_mode",
            "select_option",
            {"option": "manual"},
            {"brightness": {"mode": "manual"}},
        ),
        ("number", "dim_level", "set_value", {"value": 25}, {"displaySchedule": {"dimLevel": 25}}),
        ("switch", "clock", "turn_on", {}, {"clock": {"enabled": True}}),
        ("switch", "display_schedule", "turn_on", {}, {"displaySchedule": {"enabled": True}}),
        ("switch", "auto_update_check", "turn_off", {}, {"autoUpdateCheck": False}),
    ],
)
async def test_each_setting_sends_only_its_field(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    platform: str,
    key: str,
    service: str,
    data: dict,
    body: dict,
) -> None:
    before = {k: v for k, v in frame.settings.items() if k not in body}
    await call(hass, platform, service, entity_id(hass, platform, key), **data)
    assert patches(frame) == [body]
    assert {k: v for k, v in frame.settings.items() if k not in body} == before
    entity = er.async_get(hass).async_get(entity_id(hass, platform, key))
    assert entity.entity_category == "config"


async def test_settings_are_read_again_after_a_change(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    await call(hass, "switch", "turn_on", entity_id(hass, "switch", "clock"))
    frame.reset_requests()
    await tick(hass, freezer)
    assert frame.count("GET", "/settings") == 1


async def test_display_schedule_unavailable_without_device_administrator(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.display["available"] = False
    await tick(hass, freezer)
    state = hass.states.get(entity_id(hass, "switch", "display_schedule"))
    assert state.state == STATE_UNAVAILABLE


# -- Brightness settings ----------------------------------------------------------------------


async def test_automatic_from_an_automation(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Brightness settings as configuration entities › Automatic from an
    automation."""
    mode = entity_id(hass, "select", "brightness_mode")
    await call(hass, "select", "select_option", mode, option="auto")
    assert patches(frame) == [{"brightness": {"mode": "auto"}}]
    assert frame.display["brightness"]["auto"] is True
    await tick(hass, freezer)
    assert hass.states.get(mode).state == "auto"
    assert hass.states.get(entity_id(hass, "light", "display")).attributes["auto"] is True


async def test_no_light_sensor(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Brightness settings as configuration entities › No light sensor."""
    mode = entity_id(hass, "select", "brightness_mode")
    assert hass.states.get(mode).attributes["options"] == ["system", "manual", "auto"]
    frame.display["brightness"]["autoSupported"] = False
    await tick(hass, freezer)
    assert hass.states.get(mode).attributes["options"] == ["system", "manual"]


async def test_stored_automatic_stays_offered(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.settings["brightness"]["mode"] = "auto"
    frame.settings_version += 1
    frame.display["brightness"]["autoSupported"] = False
    await tick(hass, freezer)
    state = hass.states.get(entity_id(hass, "select", "brightness_mode"))
    assert state.state == "auto"
    assert "auto" in state.attributes["options"]


async def test_fixed_level_without_permission(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Brightness settings as configuration entities › Fixed level without
    permission."""
    mode = entity_id(hass, "select", "brightness_mode")
    frame.display["brightness"]["available"] = False
    await tick(hass, freezer)
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "select", "select_option", mode, option="manual")
    assert caught.value.translation_key == "refused"
    assert "may not modify system settings" in str(caught.value)
    assert frame.settings["brightness"]["mode"] == "system"
    assert hass.states.get(mode).state == "system"


async def test_dim_level(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """frame-entities › Brightness settings as configuration entities › Dim level."""
    schedule = dict(frame.settings["displaySchedule"])
    dim_level = entity_id(hass, "number", "dim_level")
    state = hass.states.get(dim_level)
    assert (state.state, state.attributes["min"], state.attributes["max"]) == ("20", 1, 100)
    await call(hass, "number", "set_value", dim_level, value=25)
    assert patches(frame) == [{"displaySchedule": {"dimLevel": 25}}]
    assert frame.settings["displaySchedule"] == schedule | {"dimLevel": 25}
    assert hass.states.get(dim_level).state == "25"
