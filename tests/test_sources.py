"""Remote sources (`frame-entities` › Remote sources)."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import entity_id, tick
from tests.fake_frame import FakeFrame
from tests.helpers import call


async def test_sync_from_home_assistant(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Remote sources › Sync from Home Assistant."""
    frame.add_source("nc1", "Shared photos")
    await tick(hass, freezer, 60)
    last_sync = entity_id(hass, "sensor", "last_sync_nc1")
    assert hass.states.get(last_sync).state == STATE_UNKNOWN
    assert hass.states.get(last_sync).name == "Test frame Last sync Shared photos"

    await call(hass, "button", "press", entity_id(hass, "button", "sync_nc1"))
    assert frame.source("nc1")["status"]["syncing"] is True
    frame.finish_sync("nc1", at="2026-11-08T10:05:00Z", added=3, updated=1)
    await tick(hass, freezer)  # every tick while the source syncs
    state = hass.states.get(last_sync)
    assert state.state == "2026-11-08T10:05:00+00:00"
    assert (
        state.attributes["added"],
        state.attributes["updated"],
        state.attributes["removed"],
    ) == (
        3,
        1,
        0,
    )
    assert hass.states.get(entity_id(hass, "binary_sensor", "sync_problem_nc1")).state == STATE_OFF


async def test_failed_sync(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Remote sources › Failed sync."""
    frame.add_source("nc1", "Shared photos")
    frame.finish_sync("nc1", ok=False, error="The server is not reachable.")
    await tick(hass, freezer, 60)
    problem = hass.states.get(entity_id(hass, "binary_sensor", "sync_problem_nc1"))
    assert problem.state == STATE_ON
    assert problem.attributes["error"] == "The server is not reachable."


async def test_source_renamed(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Remote sources › Source renamed."""
    frame.add_source("nc1", "Shared photos")
    await tick(hass, freezer, 60)
    keys = (
        ("sensor", "last_sync_nc1"),
        ("button", "sync_nc1"),
        ("binary_sensor", "sync_problem_nc1"),
    )
    ids = [entity_id(hass, platform, key) for platform, key in keys]
    frame.source("nc1")["settings"]["name"] = "Family photos"
    await tick(hass, freezer, 60)
    await hass.async_block_till_done()
    assert [entity_id(hass, platform, key) for platform, key in keys] == ids, "the IDs stay"
    assert [hass.states.get(i).name for i in ids] == [
        "Test frame Last sync Family photos",
        "Test frame Sync Family photos",
        "Test frame Sync problem Family photos",
    ]
