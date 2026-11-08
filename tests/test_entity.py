"""The device of a frame and the availability of its entities."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.openframe.const import DOMAIN
from tests.conftest import entity_id, tick
from tests.fake_frame import FRAME_ID, FakeFrame


async def test_device_page(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """frame-entities › One device per frame › Device page."""
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, FRAME_ID), entry.entry_id)
    assert device is not None
    assert device.name == "Test frame"
    assert device.manufacturer == "openframe"
    assert device.sw_version == "0.5.0"
    assert device.hw_version == "Android 6.0.1"
    assert device.configuration_url == f"http://{frame.host}:{frame.port}/"
    entities = er.async_entries_for_device(er.async_get(hass), device.id)
    assert {e.unique_id for e in entities} >= {f"{FRAME_ID}_display", f"{FRAME_ID}_app"}


async def test_frame_updated_itself(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › One device per frame › Frame updated itself."""
    frame.info["appVersion"] = "0.6.0"
    frame.update["installedVersion"] = "0.6.0"
    await tick(hass, freezer)
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, FRAME_ID), entry.entry_id)
    assert device is not None
    assert device.sw_version == "0.6.0"


async def test_entities_unavailable_while_the_frame_is_off(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-connection › Availability › Frame switched off, Frame back (entities)."""
    display = entity_id(hass, "switch", "display")
    assert hass.states.get(display).state == STATE_ON
    frame.unreachable = True
    await tick(hass, freezer)
    assert hass.states.get(display).state == STATE_UNAVAILABLE
    frame.unreachable = False
    await tick(hass, freezer)
    assert hass.states.get(display).state == STATE_ON
