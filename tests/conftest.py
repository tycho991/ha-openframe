"""Fixtures shared by all tests: the fake frame, a configured frame and the clock."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe.const import CONF_CLIENT_ID, DOMAIN
from tests.fake_frame import FRAME_ID, FakeFrame


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load ``custom_components/openframe`` from this repository."""


@pytest.fixture(autouse=True)
async def frontend(hass: HomeAssistant) -> list[tuple[str, str]]:
    """The integration's dependencies: `http` for real, `frontend` only as far as the card needs it.

    The real frontend needs the package `home-assistant-frontend` and a dozen integrations; the
    card only adds a module URL. Returns the changes of the module URLs.
    """
    changes: list[tuple[str, str]] = []
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *change: changes.append(change), [])
    hass.config.components.add("frontend")
    assert await async_setup_component(hass, "http", {})
    return changes


@pytest.fixture
async def frame(socket_enabled: None) -> AsyncGenerator[FakeFrame]:
    """A running fake frame; the test fails if a request or response broke the contract."""
    fake = FakeFrame()
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()
    assert not fake.contract_errors, "\n".join(fake.contract_errors)


def mock_entry(frame: FakeFrame, **data: object) -> MockConfigEntry:
    """A config entry for the fake frame with a pairing made without the code step."""
    client_id, token = frame.pair_directly()
    return MockConfigEntry(
        domain=DOMAIN,
        title=frame.info["name"],
        unique_id=FRAME_ID,
        data={
            CONF_HOST: frame.host,
            CONF_PORT: frame.port,
            CONF_TOKEN: token,
            CONF_CLIENT_ID: client_id,
        }
        | data,
    )


@pytest.fixture
async def entry(
    hass: HomeAssistant, frame: FakeFrame, freezer: FrozenDateTimeFactory
) -> MockConfigEntry:
    """The fake frame, set up in Home Assistant; the clock is frozen before the setup."""
    config_entry = mock_entry(frame)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float = 15) -> None:
    """Let the clock run on by one polling interval and let every frame's coordinator poll.

    The coordinator's own timer is not fired with ``async_fire_time_changed``: that runs every
    timer handle due within the jump, aiohttp's request timeouts included, and the requests to the
    fake frame would time out. Tests check the timer itself through ``scheduled_refresh``.
    """
    freezer.tick(timedelta(seconds=seconds))
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        coordinator = getattr(config_entry, "runtime_data", None)
        if coordinator is not None and scheduled_refresh(coordinator):
            await coordinator.async_refresh()
    await hass.async_block_till_done()


def scheduled_refresh(coordinator: object) -> bool:
    """Whether the coordinator's timer will poll again."""
    return getattr(coordinator, "_unsub_refresh", None) is not None


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    """The entity ID of a frame entity by its key, as the unique ID names it."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{FRAME_ID}_{key}")
    assert found is not None, f"no {platform} entity {key}"
    return found
