"""The photo and album actions: target, photo on screen, permissions and responses."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from homeassistant.core import Context, HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.openframe.const import DOMAIN
from tests.conftest import mock_entry
from tests.fake_frame import FRAME_ID, FakeFrame

OTHER_ID = f"{FRAME_ID}-2"


def device_id(hass: HomeAssistant, frame_id: str = FRAME_ID) -> str:
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, frame_id)
    assert entry is not None
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, frame_id), entry.entry_id)
    assert device is not None
    return device.id


async def act(
    hass: HomeAssistant,
    service: str,
    devices: list[str],
    *,
    response: bool = False,
    context: Context | None = None,
    **data: Any,
) -> ServiceResponse:
    """Call an action with frames as target, as an automation would."""
    return await hass.services.async_call(
        DOMAIN,
        service,
        {"device_id": devices, **data},
        blocking=True,
        return_response=response,
        context=context,
    )


@pytest.fixture
async def other(
    hass: HomeAssistant, entry: MockConfigEntry, socket_enabled: None
) -> AsyncGenerator[FakeFrame]:
    """A second frame, set up after the first one."""
    frame = FakeFrame()
    frame.info["id"] = OTHER_ID
    frame.info["name"] = "Other frame"
    await frame.start()
    try:
        base = mock_entry(frame)
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="Other frame",
            unique_id=OTHER_ID,
            data=base.data,
            minor_version=2,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield frame
    finally:
        await frame.stop()
    assert not frame.contract_errors, "\n".join(frame.contract_errors)


# -- Target of a photo action ----------------------------------------------------------------


async def test_photo_id_with_two_frames(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame
) -> None:
    """photo-actions › Target of a photo action › Two frames with a photo ID."""
    photo = frame.add_photo("a/1.jpg")
    other.add_photo("a/1.jpg")
    frame.reset_requests()
    other.reset_requests()
    devices = [device_id(hass), device_id(hass, OTHER_ID)]
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "set_photo_hidden", devices, photo_id=photo.id, hidden=True)
    assert caught.value.translation_key == "photo_id_one_frame"
    assert not any(p.hidden for p in frame.photos + other.photos)
    assert frame.requests == other.requests == []


async def test_unknown_photo(hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry) -> None:
    """photo-actions › Target of a photo action › Unknown photo."""
    frame.add_photo("a/1.jpg")
    with pytest.raises(HomeAssistantError) as caught:
        await act(
            hass, "set_photo_hidden", [device_id(hass)], photo_id="local-" + "0" * 40, hidden=True
        )
    assert caught.value.translation_key == "photo_not_found"


async def test_target_without_a_frame(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "set_photo_hidden", [], hidden=True)
    assert caught.value.translation_key == "no_frame"


async def test_photo_id_is_checked_before_the_frame_is_asked(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.reset_requests()
    with pytest.raises(Exception, match="photo_id"):
        await act(hass, "set_photo_hidden", [device_id(hass)], photo_id="../etc", hidden=True)
    assert frame.requests == []


# -- Photo on screen by default --------------------------------------------------------------


async def test_hide_the_photo_on_the_wall(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Photo on screen by default › Hide the photo on the wall: the action hits
    the photo on screen when it runs, not the one of the last poll."""
    frame.add_photo("a/1.jpg")
    frame.add_photo("a/2.jpg")
    frame.add_photo("a/3.jpg")
    frame.current = 1
    on_wall = frame.on_screen()
    assert on_wall is not None
    frame.reset_requests()
    await act(hass, "set_photo_hidden", [device_id(hass)], hidden=True)
    assert on_wall.hidden is True
    assert on_wall not in frame.visible_photos()
    assert frame.requests == [("GET", "/slideshow"), ("PATCH", f"/photos/{on_wall.id}")]


async def test_photo_on_screen_of_each_frame(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame
) -> None:
    mine = frame.add_photo("a/1.jpg")
    theirs = other.add_photo("b/1.jpg")
    response = await act(
        hass,
        "set_photo_hidden",
        [device_id(hass), device_id(hass, OTHER_ID)],
        response=True,
        hidden=True,
    )
    assert mine.hidden and theirs.hidden
    assert response is not None
    assert {(p["device_id"], p["id"]) for p in response["photos"]} == {
        (device_id(hass), mine.id),
        (device_id(hass, OTHER_ID), theirs.id),
    }


async def test_frame_without_photos(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Photo on screen by default › Frame without photos."""
    with pytest.raises(ServiceValidationError) as caught:
        await act(hass, "set_photo_hidden", [device_id(hass)], hidden=True)
    assert caught.value.translation_key == "no_photo_on_screen"
    assert caught.value.translation_placeholders == {"frame": entry.title}
    # Home Assistant drops the full stop of a translated message
    assert str(caught.value) == f"{entry.title} shows no photo"


async def test_one_frame_without_a_photo_does_not_stop_the_other(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, other: FakeFrame
) -> None:
    theirs = other.add_photo("b/1.jpg")
    with pytest.raises(ServiceValidationError) as caught:
        await act(
            hass, "set_photo_hidden", [device_id(hass), device_id(hass, OTHER_ID)], hidden=True
        )
    assert caught.value.translation_key == "no_photo_on_screen"
    assert theirs.hidden is True


async def test_photo_on_screen_in_safe_mode(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("a/1.jpg")
    frame.safe_mode = True
    with pytest.raises(HomeAssistantError) as caught:
        await act(hass, "set_photo_hidden", [device_id(hass)], hidden=True)
    assert caught.value.translation_key == "safe_mode"


# -- Photo actions for administrators --------------------------------------------------------


async def test_non_admin_user_is_refused(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, hass_read_only_user: MockUser
) -> None:
    """photo-actions › Photo actions for administrators › Non-admin user."""
    photo = frame.add_photo("a/1.jpg")
    frame.reset_requests()
    context = Context(user_id=hass_read_only_user.id)
    for service, data in (
        ("delete_photo", {"photo_id": photo.id}),
        ("set_photo_hidden", {"hidden": True}),
        ("set_photo_comment", {"comment": "x"}),
        ("set_photo_crop", {"reset": True}),
        ("upload_photo", {"file_path": ["/media/a.jpg"]}),
        ("set_album_hidden", {"album": "a", "hidden": True}),
    ):
        with pytest.raises(Unauthorized):
            await act(hass, service, [device_id(hass)], context=context, **data)
    assert frame.photos == [photo]
    assert frame.requests == []


async def test_automation_and_admin_may_act(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry, hass_admin_user: MockUser
) -> None:
    """photo-actions › Photo actions for administrators › Automation."""
    photo = frame.add_photo("a/1.jpg")
    await act(hass, "set_photo_hidden", [device_id(hass)], photo_id=photo.id, hidden=True)
    assert photo.hidden is True
    admin = Context(user_id=hass_admin_user.id)
    await act(
        hass, "set_photo_hidden", [device_id(hass)], context=admin, photo_id=photo.id, hidden=False
    )
    assert photo.hidden is False


# -- Responses of photo actions --------------------------------------------------------------


async def test_response_in_a_script(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    """photo-actions › Responses of photo actions › Response in a script."""
    photo = frame.add_photo("holiday/IMG_0042.jpg")
    response = await act(
        hass, "set_photo_comment", [device_id(hass)], response=True, comment="Summer 2025"
    )
    assert response == {
        "photos": [
            {
                "device_id": device_id(hass),
                "id": photo.id,
                "album": "holiday",
                "path": "holiday/IMG_0042.jpg",
                "hidden": False,
                "visible": True,
                "comment": "Summer 2025",
                "crop": None,
            }
        ]
    }


async def test_no_response_unless_asked(
    hass: HomeAssistant, frame: FakeFrame, entry: MockConfigEntry
) -> None:
    frame.add_photo("a/1.jpg")
    assert await act(hass, "set_photo_comment", [device_id(hass)], comment="x") is None
    assert frame.photos[0].comment == "x"
