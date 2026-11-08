"""Diagnostics of a frame: its info and state, without the token or private photo data."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_CLIENT_ID
from .coordinator import OpenframeConfigEntry

# The pairing, signed image URLs, and what names a person's photos, servers or accounts
TO_REDACT = {
    CONF_TOKEN,
    CONF_CLIENT_ID,
    "urls",
    "cover",
    "path",
    "album",
    "comment",
    "location",
    "serverUrl",
    "user",
    "error",
    "name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OpenframeConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = asdict(coordinator.data) if coordinator.data is not None else None
    if data is not None:
        # Album names are folder names of the user's photos; their number is enough
        data["albums"] = len(data["albums"])
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(data, TO_REDACT),
    }
