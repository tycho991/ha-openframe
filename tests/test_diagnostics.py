"""The token stays private (`frame-connection` › Token kept private)."""

from __future__ import annotations

import json
import logging

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe.diagnostics import async_get_config_entry_diagnostics
from tests.conftest import mock_entry
from tests.fake_frame import FakeFrame


async def test_diagnostics(hass: HomeAssistant, frame: FakeFrame) -> None:
    """frame-connection › Token kept private › Diagnostics."""
    frame.add_photo("holiday/IMG_0042.jpg", comment="Summer 2025", place="Munich, Germany")
    frame.add_source("nc1", "Shared photos")
    config_entry = mock_entry(frame)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    token = config_entry.data[CONF_TOKEN]

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["entry"][CONF_TOKEN] == "**REDACTED**"
    assert diagnostics["data"]["info"]["appVersion"] == "0.5.0"
    assert diagnostics["data"]["state"]["libraryVersion"] == frame.library_version
    dump = json.dumps(diagnostics)
    for private in (
        token,
        "IMG_0042",
        "Summer 2025",
        "Munich",
        "holiday",
        "cloud.example.com",
        "sig",
    ):
        assert private not in dump, private


@pytest.mark.parametrize("failure", ["revoked", "unreachable"])
async def test_log_of_a_failed_setup_has_no_token(
    hass: HomeAssistant, frame: FakeFrame, caplog: pytest.LogCaptureFixture, failure: str
) -> None:
    caplog.set_level(logging.DEBUG)
    config_entry: MockConfigEntry = mock_entry(frame)
    token = config_entry.data[CONF_TOKEN]
    if failure == "revoked":
        frame.revoke_all()
    else:
        frame.unreachable = True
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state in (ConfigEntryState.SETUP_ERROR, ConfigEntryState.SETUP_RETRY)
    assert caplog.text
    assert token not in caplog.text
