"""The openframe integration: openframe picture frames on the local network."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenframeClient, OpenframeError
from .const import CONF_CLIENT_ID, DOMAIN
from .coordinator import OpenframeConfigEntry, OpenframeCoordinator, outdated_issue_id
from .entity import follow_app_version, source_names

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

# Seconds to wait for the frame when the entry is removed; the removal goes ahead without it
REVOKE_TIMEOUT = 5


def _client(hass: HomeAssistant, entry: OpenframeConfigEntry) -> OpenframeClient:
    return OpenframeClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
    )


async def async_setup_entry(hass: HomeAssistant, entry: OpenframeConfigEntry) -> bool:
    """Set up a frame from a config entry."""
    coordinator = OpenframeCoordinator(hass, entry, _client(hass, entry))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    names = source_names(coordinator.data)

    @callback
    def on_update() -> None:
        follow_app_version(hass, coordinator)
        current = source_names(coordinator.data)
        if any(current.get(source_id, name) != name for source_id, name in names.items()):
            # A source entity takes its name when it is created; a reload names it anew
            hass.config_entries.async_schedule_reload(entry.entry_id)
        names.update(current)

    # Also keeps the coordinator polling with every entity disabled (it polls only while it has
    # listeners), so that a revoked pairing still leads to re-authentication.
    entry.async_on_unload(coordinator.async_add_listener(on_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenframeConfigEntry) -> bool:
    """Unload a frame."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: OpenframeConfigEntry) -> None:
    """Revoke Home Assistant's pairing on the frame; a frame that does not answer is skipped."""
    ir.async_delete_issue(hass, DOMAIN, outdated_issue_id(entry))
    try:
        await _client(hass, entry).delete_client(entry.data[CONF_CLIENT_ID], timeout=REVOKE_TIMEOUT)
    except OpenframeError as err:
        _LOGGER.info("Could not revoke the pairing on %s: %s", entry.title, err)
