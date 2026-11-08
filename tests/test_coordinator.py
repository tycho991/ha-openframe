"""Polling the frame in three tiers, safe mode and availability (`frame-connection`)."""

from __future__ import annotations

import logging

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe.coordinator import UPDATE_INTERVAL, OpenframeCoordinator
from tests.conftest import scheduled_refresh, tick
from tests.fake_frame import FakeFrame

FAST = [("GET", "/state"), ("GET", "/display"), ("GET", "/slideshow")]
MEDIUM = [("GET", "/sources"), ("GET", "/update")]
FULL = [
    ("GET", "/settings"),
    ("GET", "/albums"),
    ("GET", "/info"),
    ("GET", "/photos"),
    ("GET", "/photos"),
]


def coordinator(entry: MockConfigEntry) -> OpenframeCoordinator:
    return entry.runtime_data


async def test_first_read_reads_every_tier(frame: FakeFrame, entry: MockConfigEntry) -> None:
    assert frame.requests == FAST + MEDIUM + FULL
    data = coordinator(entry).data
    assert data.info["id"] == entry.unique_id
    assert scheduled_refresh(coordinator(entry))
    assert coordinator(entry).update_interval == UPDATE_INTERVAL
    assert UPDATE_INTERVAL.total_seconds() == 15


async def test_request_counts_per_tier(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-connection › Polling the frame: three small requests per tick, sources and update
    every minute."""
    frame.reset_requests()
    for _ in range(3):
        await tick(hass, freezer)
    assert frame.requests == FAST * 3
    frame.reset_requests()
    await tick(hass, freezer)
    assert frame.requests == FAST + MEDIUM


async def test_nothing_changed(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-connection › Polling the frame › Nothing changed."""
    frame.reset_requests()
    for _ in range(20):  # five minutes
        await tick(hass, freezer)
    for request in FULL:
        assert frame.count(*request) == 0, request


async def test_full_read_every_ten_minutes(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.reset_requests()
    for _ in range(40):
        await tick(hass, freezer)
    assert frame.count("GET", "/settings") == 1


async def test_photo_change_on_the_frame(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-connection › Polling the frame › Photo change on the frame."""
    frame.add_photo("a/1.jpg")
    frame.add_photo("a/2.jpg")
    await tick(hass, freezer)
    assert coordinator(entry).data.slideshow["photo"]["path"] == "a/1.jpg"
    frame.current = 1
    await tick(hass, freezer)
    assert coordinator(entry).data.slideshow["photo"]["path"] == "a/2.jpg"


async def test_setting_changed_in_the_web_ui(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-connection › Polling the frame › Setting changed in the web UI."""
    frame.settings["intervalSeconds"] = 60
    frame.settings_version += 1
    frame.reset_requests()
    await tick(hass, freezer)
    assert frame.requests == FAST + FULL
    assert coordinator(entry).data.settings["intervalSeconds"] == 60


async def test_sources_every_tick_while_syncing(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.add_source("nc1", "Shared photos")
    frame.source("nc1")["status"]["syncing"] = True
    await tick(hass, freezer, 60)  # the minute tier sees the sync
    frame.reset_requests()
    await tick(hass, freezer)
    await tick(hass, freezer)
    assert frame.count("GET", "/sources") == 2
    frame.finish_sync("nc1")
    await tick(hass, freezer)
    frame.reset_requests()
    await tick(hass, freezer)
    assert frame.count("GET", "/sources") == 0


@pytest.mark.parametrize("phase", ["checking", "downloading", "installing"])
async def test_update_every_tick_while_busy(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    phase: str,
) -> None:
    frame.update["phase"] = phase
    await tick(hass, freezer, 60)
    frame.reset_requests()
    await tick(hass, freezer)
    assert frame.count("GET", "/update") == 1


async def test_safe_mode_is_not_a_failure(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.safe_mode = True
    await tick(hass, freezer)
    assert coordinator(entry).last_update_success
    assert coordinator(entry).data.slideshow is None
    assert coordinator(entry).data.state["safeMode"] is True


async def test_frame_switched_off_and_back(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """frame-connection › Availability › Frame switched off, Frame back."""
    caplog.set_level(logging.INFO, logger="custom_components.openframe")
    frame.unreachable = True
    await tick(hass, freezer)
    assert not coordinator(entry).last_update_success
    for _ in range(3):
        await tick(hass, freezer)
    lost = [r for r in caplog.records if "Error fetching" in r.getMessage()]
    assert len(lost) == 1

    frame.unreachable = False
    frame.current = None
    await tick(hass, freezer)
    assert coordinator(entry).last_update_success
    assert coordinator(entry).data.slideshow["photo"] is None
    await tick(hass, freezer)
    back = [r for r in caplog.records if "recovered" in r.getMessage()]
    assert len(back) == 1
