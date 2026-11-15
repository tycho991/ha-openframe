"""App update entity and the update check (`frame-entities`)."""

from __future__ import annotations

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_LATEST_VERSION,
    ATTR_TITLE,
    UpdateEntityFeature,
)
from homeassistant.components.update.const import DATA_COMPONENT as UPDATES
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import entity_id, tick
from tests.fake_frame import NOW, FakeFrame
from tests.helpers import call

RELEASE = {"version": "0.7.0", "notes": "Faster start.\n<b>not html</b>", "publishedAt": NOW}
CONFIRM_EN = "Installing opens a dialog on the frame's screen: confirm it there within 10 minutes."
CONFIRM_DE = (
    "Die Installation öffnet einen Dialog auf dem Bildschirm des Rahmens: "
    "Bestätige ihn dort innerhalb von 10 Minuten."
)


async def test_update_ready(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › App update entity › Update ready."""
    frame.update.update(phase="ready", latest=RELEASE)
    await tick(hass, freezer, 60)
    app = entity_id(hass, "update", "app")
    state = hass.states.get(app)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LATEST_VERSION] == "0.7.0"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & UpdateEntityFeature.INSTALL
    entity = hass.data[UPDATES].get_entity(app)
    notes = await entity.async_release_notes()
    assert notes == f"{CONFIRM_EN}\n\n```text\nFaster start.\n<b>not html</b>\n```"


async def test_install_from_home_assistant(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › App update entity › Install from Home Assistant."""
    frame.display.update(on=False, cause="schedule")
    frame.update.update(phase="ready", latest=RELEASE)
    await tick(hass, freezer, 60)
    app = entity_id(hass, "update", "app")
    await call(hass, "update", "install", app)
    assert frame.update["phase"] == "installing"
    assert frame.display["on"] is True
    assert hass.states.get(app).attributes[ATTR_IN_PROGRESS] is True


async def test_installing_not_allowed(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › App update entity › Installing not allowed."""
    frame.update.update(phase="ready", latest=RELEASE, installAllowed=False)
    await tick(hass, freezer, 60)
    state = hass.states.get(entity_id(hass, "update", "app"))
    assert state.attributes[ATTR_LATEST_VERSION] == "0.7.0"
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & UpdateEntityFeature.INSTALL


async def test_unofficial_build_offers_no_install(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.update.update(phase="unsupported")
    await tick(hass, freezer, 60)
    state = hass.states.get(entity_id(hass, "update", "app"))
    assert state.state == STATE_OFF
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & UpdateEntityFeature.INSTALL


async def test_no_install_before_the_download(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.update.update(
        phase="idle",
        latest=RELEASE,
        error={"code": "update_checksum", "message": "The checksum does not match."},
    )
    await tick(hass, freezer, 60)
    state = hass.states.get(entity_id(hass, "update", "app"))
    assert state.state == STATE_ON
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & UpdateEntityFeature.INSTALL


async def test_in_progress_while_downloading(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.update.update(phase="downloading", latest=RELEASE)
    await tick(hass, freezer, 60)
    assert hass.states.get(entity_id(hass, "update", "app")).attributes[ATTR_IN_PROGRESS] is True


async def test_check_now(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Checking for an update › Check now."""
    frame.settings["autoUpdateCheck"] = False
    await call(hass, "button", "press", entity_id(hass, "button", "check_update"))
    assert frame.count("POST", "/update/check") == 1
    # The frame finds the release while it checks
    frame.update.update(
        phase="idle",
        latest=RELEASE,
        lastCheck={"at": NOW, "result": "update_found"},
    )
    await tick(hass, freezer)  # every tick while checking
    state = hass.states.get(entity_id(hass, "update", "app"))
    assert state.attributes[ATTR_LATEST_VERSION] == "0.7.0"
    assert state.state == STATE_ON


async def test_confirmation_on_the_frame(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › App update entity › Confirmation on the frame."""
    await hass.config.async_update(language="de")
    frame.update.update(phase="ready", latest=RELEASE)
    await tick(hass, freezer, 60)
    entity = hass.data[UPDATES].get_entity(entity_id(hass, "update", "app"))
    notes = await entity.async_release_notes()
    assert notes.startswith(f"{CONFIRM_DE}\n\n```text\nFaster start.")


async def test_two_updates_named_openframe(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › App update entity › Two updates named openframe."""
    frame.update.update(phase="ready", latest=RELEASE)
    await tick(hass, freezer, 60)
    state = hass.states.get(entity_id(hass, "update", "app"))
    assert state.attributes[ATTR_TITLE] == "openframe app"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.7.0"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        # frame-entities › Refused installation › Dialog not confirmed
        (
            {"code": "install_unanswered", "message": "Nobody answered."},
            "install_cooldown_unanswered",
        ),
        # › Dialog cancelled
        ({"code": "install_cancelled", "message": "Cancelled."}, "install_cooldown_cancelled"),
        # › Cause not reported
        (None, "install_cooldown"),
    ],
)
async def test_refused_installation(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    error: dict[str, str] | None,
    key: str,
) -> None:
    """frame-entities › Refused installation."""
    frame.update.update(phase="ready", latest=RELEASE, error=error)
    frame.install_cooldown = True
    await tick(hass, freezer, 60)
    app = entity_id(hass, "update", "app")
    with pytest.raises(HomeAssistantError) as caught:
        await call(hass, "update", "install", app)
    assert caught.value.translation_key == key
    # No dialog on the frame
    assert frame.update["phase"] == "ready"
    assert hass.states.get(app).attributes[ATTR_IN_PROGRESS] is False
