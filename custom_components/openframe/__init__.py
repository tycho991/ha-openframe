"""The openframe integration: openframe picture frames on the local network."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import OpenframeClient, OpenframeError
from .const import CONF_CLIENT_ID, DOMAIN
from .coordinator import OpenframeConfigEntry, OpenframeCoordinator, outdated_issue_id
from .entity import follow_app_version, source_names

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

# Seconds to wait for the frame when the entry is removed; the removal goes ahead without it
REVOKE_TIMEOUT = 5

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Where the dashboard card is served from, and its module
STATIC_URL = "/openframe_static"
CARD_MODULE = "openframe-card.js"


def _client(hass: HomeAssistant, entry: OpenframeConfigEntry) -> OpenframeClient:
    return OpenframeClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and load it into the frontend, once per Home Assistant start."""
    integration = await async_get_integration(hass, DOMAIN)
    # Without cache headers the browser asks again on each page load: the card imports its model
    # without the version parameter, and a cached model must not outlive an update
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)]
    )
    # The version busts the browser's cache of the card after an update
    add_extra_js_url(hass, f"{STATIC_URL}/{CARD_MODULE}?v={integration.version}")
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: OpenframeConfigEntry) -> bool:
    """Bring an entry of an earlier version of the integration up to date."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        # Up to 0.1.0 the display was a switch with the unique ID the light has now; Home
        # Assistant cannot move an entity to another domain, so the switch goes. This runs
        # before the setup, also for a frame that does not answer or is still outdated.
        registry = er.async_get(hass)
        if switch := registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, f"{entry.unique_id}_display"
        ):
            registry.async_remove(switch)
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True


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
