"""Config flow: adding, pairing, re-pairing, moving and removing a frame (`frame-connection`)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe.const import CONF_CLIENT_ID, DOMAIN
from tests.conftest import mock_entry, tick
from tests.fake_frame import FRAME_ID, FakeFrame


@pytest.fixture
def no_setup():
    """Config flow tests that create an entry do not need the coordinator."""
    with patch("custom_components.openframe.async_setup_entry", return_value=True) as setup:
        yield setup


async def start(hass: HomeAssistant, frame: FakeFrame) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: frame.host, CONF_PORT: frame.port}
    )


def other_code(frame: FakeFrame) -> str:
    return "123456" if frame.code != "123456" else "654321"


# -- Adding a frame by its address -----------------------------------------------------------


async def test_frame_found(hass: HomeAssistant, frame: FakeFrame) -> None:
    """frame-connection › Adding a frame by its address › Frame found."""
    result = await start(hass, frame)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["description_placeholders"] == {"name": "Test frame"}
    assert frame.code is not None


async def test_nothing_answers(hass: HomeAssistant, frame: FakeFrame) -> None:
    """frame-connection › Adding a frame by its address › Nothing answers."""
    frame.unreachable = True
    result = await start(hass, frame)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    suggested = {
        str(key): key.description["suggested_value"] for key in result["data_schema"].schema
    }
    assert suggested == {CONF_HOST: frame.host, CONF_PORT: frame.port}


async def test_same_frame_again(hass: HomeAssistant, frame: FakeFrame) -> None:
    """frame-connection › Adding a frame by its address › Same frame again."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=FRAME_ID,
        data={CONF_HOST: "192.168.100.216", CONF_PORT: 8080, CONF_TOKEN: "t", CONF_CLIENT_ID: "c"},
    ).add_to_hass(hass)
    result = await start(hass, frame)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# -- Pairing with the code on the frame ------------------------------------------------------


async def test_correct_code(hass: HomeAssistant, frame: FakeFrame, no_setup) -> None:
    """frame-connection › Pairing with the code on the frame › Correct code."""
    result = await start(hass, frame)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test frame"
    assert result["result"].unique_id == FRAME_ID
    [(client_id, client)] = frame.clients.items()
    assert client["name"] == "Home Assistant"
    assert result["data"] == {
        CONF_HOST: frame.host,
        CONF_PORT: frame.port,
        CONF_TOKEN: client["token"],
        CONF_CLIENT_ID: client_id,
    }


async def test_wrong_code(hass: HomeAssistant, frame: FakeFrame, no_setup) -> None:
    """frame-connection › Pairing with the code on the frame › Wrong code."""
    result = await start(hass, frame)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": other_code(frame)}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"code": "invalid_code"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_code_that_is_not_six_digits(hass: HomeAssistant, frame: FakeFrame) -> None:
    result = await start(hass, frame)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "12a4"})
    assert result["errors"] == {"code": "invalid_code"}
    assert frame.count("POST", "/pairing") == 0


async def test_expired_code(hass: HomeAssistant, frame: FakeFrame, no_setup) -> None:
    """frame-connection › Pairing with the code on the frame › Expired code."""
    result = await start(hass, frame)
    old_code = frame.code
    frame.code_expired = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": old_code})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "expired_code"}
    assert frame.count("POST", "/pairing/code") == 2
    assert not frame.code_expired
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_locked_after_wrong_codes(hass: HomeAssistant, frame: FakeFrame) -> None:
    """frame-connection › Pairing with the code on the frame › Locked after wrong codes."""
    result = await start(hass, frame)
    frame.failed_codes = frame.lock_after
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "locked"}


# -- Minimum frame version -------------------------------------------------------------------


async def test_frame_before_the_slideshow_api(
    hass: HomeAssistant, frame: FakeFrame, no_setup
) -> None:
    """frame-connection › Minimum frame version › Frame before the slideshow API."""
    frame.outdated = True
    result = await start(hass, frame)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "outdated_frame"
    assert result["description_placeholders"] == {"version": "0.5.0"}
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert frame.clients == {}, "the new pairing is revoked again"


async def test_unexpected_answer_is_not_called_outdated(
    hass: HomeAssistant, frame: FakeFrame, no_setup
) -> None:
    frame.reject_slideshow = True
    result = await start(hass, frame)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unexpected_answer"
    assert frame.clients == {}


async def test_frame_in_safe_mode_can_be_added(
    hass: HomeAssistant, frame: FakeFrame, no_setup
) -> None:
    frame.safe_mode = True
    result = await start(hass, frame)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.CREATE_ENTRY


# -- Re-authentication after a revoked pairing -----------------------------------------------


async def test_pairing_revoked_in_the_web_ui(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """frame-connection › Re-authentication after a revoked pairing › Pairing revoked in the
    web UI."""
    old_token = entry.data[CONF_TOKEN]
    frame.revoke_all()
    await tick(hass, freezer)
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == "reauth"
    assert flow["step_id"] == "reauth_confirm"
    frame.reset_requests()
    await tick(hass, freezer)
    assert frame.requests == [], "polling stops while the token is rejected"

    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["step_id"] == "pair"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": frame.code})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.data[CONF_TOKEN] != old_token
    assert entry.data[CONF_CLIENT_ID] in frame.clients
    assert entry.state is ConfigEntryState.LOADED


async def test_reauthentication_with_another_frame(
    hass: HomeAssistant,
    frame: FakeFrame,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """frame-connection › Re-authentication after a revoked pairing › Re-authentication with
    another frame."""
    old_token = entry.data[CONF_TOKEN]
    frame.revoke_all()
    await tick(hass, freezer)
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    frame.info["id"] = "0" * 32
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_frame"
    assert entry.data[CONF_TOKEN] == old_token


# -- Changed address -------------------------------------------------------------------------


async def test_new_ip_address(hass: HomeAssistant, frame: FakeFrame) -> None:
    """frame-connection › Changed address › New IP address."""
    config_entry = mock_entry(frame, **{CONF_HOST: "192.168.100.215", CONF_PORT: 8080})
    config_entry.add_to_hass(hass)
    token = config_entry.data[CONF_TOKEN]
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: frame.host, CONF_PORT: frame.port}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert config_entry.data[CONF_HOST] == frame.host
    assert config_entry.data[CONF_PORT] == frame.port
    assert config_entry.data[CONF_TOKEN] == token
    assert config_entry.state is ConfigEntryState.LOADED


async def test_another_frame_at_the_new_address(hass: HomeAssistant, frame: FakeFrame) -> None:
    """frame-connection › Changed address › Another frame at the new address."""
    config_entry = mock_entry(frame, **{CONF_HOST: "192.168.100.215", CONF_PORT: 8080})
    config_entry.add_to_hass(hass)
    frame.info["id"] = "0" * 32
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: frame.host, CONF_PORT: frame.port}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_frame"}
    assert config_entry.data[CONF_HOST] == "192.168.100.215"


# -- Removing a frame ------------------------------------------------------------------------


async def test_removal(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """frame-connection › Removing a frame › Removal."""
    client_id = entry.data[CONF_CLIENT_ID]
    assert client_id in frame.clients
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert client_id not in frame.clients


async def test_removal_of_an_unreachable_frame(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """frame-connection › Removing a frame › Removal of an unreachable frame."""
    frame.unreachable = True
    result = await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert result == {"require_restart": False}
    assert hass.config_entries.async_entries(DOMAIN) == []
