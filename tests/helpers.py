"""Small helpers for entity tests."""

from __future__ import annotations

from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def call(hass: HomeAssistant, domain: str, service: str, target: str, **data: Any) -> None:
    """Call an entity service and wait for it, as an automation would."""
    await hass.services.async_call(domain, service, {ATTR_ENTITY_ID: target, **data}, blocking=True)
