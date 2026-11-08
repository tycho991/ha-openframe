"""Health of the frame and errors of commands (`frame-entities`)."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe import entity as entity_module
from tests.conftest import entity_id, tick
from tests.fake_frame import FakeFrame
from tests.helpers import call


def state(hass: HomeAssistant, platform: str, key: str) -> str:
    return hass.states.get(entity_id(hass, platform, key)).state


async def test_safe_mode(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Health of the frame › Safe mode."""
    assert state(hass, "button", "leave_safe_mode") == STATE_UNAVAILABLE
    frame.safe_mode = True
    await tick(hass, freezer)
    assert state(hass, "binary_sensor", "safe_mode") == STATE_ON
    for platform, key in (
        ("switch", "slideshow"),
        ("button", "next_photo"),
        ("button", "previous_photo"),
        ("image", "current_photo"),
        ("sensor", "current_photo"),
    ):
        assert state(hass, platform, key) == STATE_UNAVAILABLE, key
    assert state(hass, "button", "leave_safe_mode") != STATE_UNAVAILABLE


async def test_leave_safe_mode(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Health of the frame › Leave safe mode."""
    frame.safe_mode = True
    await tick(hass, freezer)
    await call(hass, "button", "press", entity_id(hass, "button", "leave_safe_mode"))
    assert frame.safe_mode is False
    await tick(hass, freezer)
    assert state(hass, "binary_sensor", "safe_mode") == STATE_OFF
    assert state(hass, "switch", "slideshow") == STATE_ON


async def test_transition_fallback(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    fallback = entity_id(hass, "binary_sensor", "transition_fallback")
    assert er.async_get(hass).async_get(fallback).entity_category == "diagnostic"
    frame.transition_fallback = True
    await tick(hass, freezer)
    assert hass.states.get(fallback).state == STATE_ON


async def test_frame_unreachable(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """frame-entities › Errors of commands › Frame unreachable."""
    display = entity_id(hass, "switch", "display")
    frame.unreachable = True
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "switch", "turn_off", display)
    assert caught.value.translation_key == "no_answer"
    assert str(caught.value) == "The frame does not answer"
    assert hass.states.get(display).state == STATE_ON


async def test_refused_command(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Errors of commands: a refusal fails with a translated message."""
    frame.update.update(
        phase="ready", latest={"version": "0.6.0", "notes": "", "publishedAt": None}
    )
    await tick(hass, freezer, 60)
    # The download is dropped on the frame before the next poll
    frame.update["phase"] = "idle"
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "update", "install", entity_id(hass, "update", "app"))
    assert caught.value.translation_key == "update_not_ready"
    assert frame.update["phase"] == "idle"


async def test_unknown_refusal_names_the_frame_message(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entity_module, "KNOWN_REFUSALS", frozenset())
    frame.display["available"] = False
    with pytest.raises(HomeAssistantError) as caught:
        # The frame refuses the schedule without device administrator rights (400 with a field)
        await call(hass, "switch", "turn_on", entity_id(hass, "switch", "display_schedule"))
    assert caught.value.translation_key == "refused"
    assert caught.value.translation_placeholders == {"message": "Invalid request."}


async def test_revoked_token_on_a_command_starts_reauthentication(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.revoke_all()
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "switch", "turn_off", entity_id(hass, "switch", "display"))
    assert caught.value.translation_key == "unauthorized"
    await hass.async_block_till_done()
    [flow] = hass.config_entries.flow.async_progress_by_handler("openframe")
    assert flow["context"]["source"] == "reauth"
