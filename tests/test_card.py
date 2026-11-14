"""Serving the dashboard card (`dashboard-card` › Card loads by itself)."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from tests.conftest import mock_entry
from tests.fake_frame import FRAME_ID, FakeFrame

MANIFEST = Path(__file__).parent.parent / "custom_components/openframe/manifest.json"


async def test_card_registered_once_with_the_version(
    hass: HomeAssistant,
    frontend: list[tuple[str, str]],
    hass_client: ClientSessionGenerator,
    socket_enabled: None,
) -> None:
    """dashboard-card › Card loads by itself › Fresh install and Integration updated: one module
    URL per Home Assistant start, with the manifest's version, also with two frames."""
    version = json.loads(MANIFEST.read_text())["version"]
    frames = [FakeFrame(), FakeFrame()]
    frames[1].info["id"] = f"{FRAME_ID}-2"
    for frame in frames:
        await frame.start()
    try:
        for frame in frames:
            entry = mock_entry(frame)
            entry = MockConfigEntry(
                domain=entry.domain,
                title=entry.title,
                unique_id=frame.info["id"],
                data=entry.data,
                minor_version=2,
            )
            entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        assert len(hass.config_entries.async_loaded_entries("openframe")) == 2
    finally:
        for frame in frames:
            await frame.stop()

    assert frontend == [("added", f"/openframe_static/openframe-card.js?v={version}")]

    client = await hass_client()
    for module in ("openframe-card.js", "model.js"):
        response = await client.get(f"/openframe_static/{module}")
        assert response.status == 200, module
        assert "javascript" in response.headers["Content-Type"]
