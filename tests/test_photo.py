"""The photo on screen as image and sensor (`frame-entities` › Photo on screen)."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.image import DATA_COMPONENT as IMAGES
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import entity_id, tick
from tests.fake_frame import FakeFrame, image_bytes


async def image_of(hass: HomeAssistant) -> bytes | None:
    entity = hass.data[IMAGES].get_entity(entity_id(hass, "image", "current_photo"))
    assert entity is not None
    return await entity.async_image()


async def test_new_photo(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Photo on screen › New photo."""
    photo = frame.add_photo("holiday/IMG_0001.jpg", comment="Summer 2025", place="Munich, Germany")
    await tick(hass, freezer)
    assert await image_of(hass) == image_bytes(photo, "display")
    state = hass.states.get(entity_id(hass, "sensor", "current_photo"))
    assert state.state == "Summer 2025"
    assert state.attributes["place"] == "Munich, Germany"
    assert state.attributes["photo_id"] == photo.id
    assert state.attributes["taken_at"] == photo.taken_at


async def test_long_comment_is_cut_to_a_valid_state(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    frame.add_photo("a/1.jpg", comment="x" * 500)
    await tick(hass, freezer)
    state = hass.states.get(entity_id(hass, "sensor", "current_photo")).state
    assert len(state) == 255
    assert state.endswith("…")


async def test_photo_without_comment(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """frame-entities › Photo on screen › Photo without comment."""
    frame.add_photo("holiday/IMG_0042.jpg")
    await tick(hass, freezer)
    state = hass.states.get(entity_id(hass, "sensor", "current_photo"))
    assert state.state == "IMG_0042.jpg"
    assert state.attributes["album"] == "holiday"
    assert state.attributes["place"] is None


async def test_empty_library(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """frame-entities › Photo on screen › Empty library."""
    assert hass.states.get(entity_id(hass, "image", "current_photo")).state == STATE_UNKNOWN
    assert hass.states.get(entity_id(hass, "sensor", "current_photo")).state == STATE_UNKNOWN
    assert await image_of(hass) is None


async def test_image_follows_photo_and_section(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """`image_last_updated` changes with a new photo and a new section of the same photo, and
    not on an unchanged poll; the image is read from the frame once per section."""
    image = entity_id(hass, "image", "current_photo")
    photo = frame.add_photo("a/1.jpg")
    frame.add_photo("a/2.jpg")
    await tick(hass, freezer)
    first = hass.states.get(image).state
    assert first != STATE_UNKNOWN
    await image_of(hass)
    await image_of(hass)
    assert frame.count("GET", f"/photos/{photo.id}/image") == 1

    await tick(hass, freezer)
    assert hass.states.get(image).state == first, "unchanged poll"

    frame.signature_hour += 1  # a new signature every full hour, same image
    frame.library_version += 1
    await tick(hass, freezer)
    assert hass.states.get(image).state == first, "new signature only"
    await image_of(hass)
    assert frame.count("GET", f"/photos/{photo.id}/image") == 1

    photo.part = "b2"  # a new section of the same photo
    frame.library_version += 1
    await tick(hass, freezer)
    second = hass.states.get(image).state
    assert second != first
    assert await image_of(hass) == image_bytes(photo, "display")
    assert frame.count("GET", f"/photos/{photo.id}/image") == 2

    frame.current = 1
    await tick(hass, freezer)
    assert hass.states.get(image).state != second
