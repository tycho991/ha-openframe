"""Actions on a frame's photos and albums: hide, comment, crop, delete and upload photos, hide
albums.

The actions target frames as devices and are registered once, for administrators, automations
and scripts. A photo action without a photo ID acts on the photo each targeted frame shows at the
moment the action runs.
"""

from __future__ import annotations

import asyncio
import mimetypes
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import probatio as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import (
    async_extract_config_entry_ids,
    async_register_admin_service,
)

from .api import OpenframeAuthError, OpenframeResponseError, UploadFile
from .const import DOMAIN
from .coordinator import OpenframeCoordinator
from .entity import run_command

SET_PHOTO_HIDDEN = "set_photo_hidden"
SET_PHOTO_COMMENT = "set_photo_comment"
SET_PHOTO_CROP = "set_photo_crop"
DELETE_PHOTO = "delete_photo"
UPLOAD_PHOTO = "upload_photo"
SET_ALBUM_HIDDEN = "set_album_hidden"

ATTR_PHOTO_ID = "photo_id"
ATTR_HIDDEN = "hidden"
ATTR_COMMENT = "comment"
ATTR_X = "x"
ATTR_Y = "y"
ATTR_ZOOM = "zoom"
ATTR_RESET = "reset"
ATTR_FILE_PATH = "file_path"
ATTR_ALBUM = "album"

# openframe's photo ID: the source and the SHA-1 of the photo's path
PHOTO_ID = vol.Match(r"^[a-z][a-z0-9]*-[0-9a-f]{40}$")
FRACTION = vol.All(vol.Coerce(float), vol.Range(min=0, max=1))

PHOTO_FIELDS = {**cv.TARGET_SERVICE_FIELDS, vol.Optional(ATTR_PHOTO_ID): PHOTO_ID}

SET_PHOTO_HIDDEN_SCHEMA = vol.Schema({**PHOTO_FIELDS, vol.Required(ATTR_HIDDEN): cv.boolean})
SET_PHOTO_COMMENT_SCHEMA = vol.Schema(
    {**PHOTO_FIELDS, vol.Required(ATTR_COMMENT): vol.Any(None, cv.string)}
)
SET_PHOTO_CROP_SCHEMA = vol.Schema(
    {
        **PHOTO_FIELDS,
        vol.Optional(ATTR_X): FRACTION,
        vol.Optional(ATTR_Y): FRACTION,
        vol.Optional(ATTR_ZOOM): vol.All(
            vol.Coerce(float), vol.Range(min=0, min_included=False, max=4)
        ),
        vol.Optional(ATTR_RESET, default=False): cv.boolean,
    }
)
DELETE_PHOTO_SCHEMA = vol.Schema(PHOTO_FIELDS)
UPLOAD_PHOTO_SCHEMA = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
        vol.Required(ATTR_FILE_PATH): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
        vol.Optional(ATTR_ALBUM): cv.string,
    }
)
SET_ALBUM_HIDDEN_SCHEMA = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
        vol.Required(ATTR_ALBUM): cv.string,
        vol.Required(ATTR_HIDDEN): cv.boolean,
    }
)

# The fields of a photo in an action's response
RECORD_FIELDS = ("id", "album", "path", "hidden", "visible", "comment", "crop")


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the photo and album actions for administrators, automations and scripts."""
    actions: list[tuple[str, Callable[..., Awaitable[ServiceResponse]], Any, SupportsResponse]] = [
        (SET_PHOTO_HIDDEN, _set_photo_hidden, SET_PHOTO_HIDDEN_SCHEMA, SupportsResponse.OPTIONAL),
        (
            SET_PHOTO_COMMENT,
            _set_photo_comment,
            SET_PHOTO_COMMENT_SCHEMA,
            SupportsResponse.OPTIONAL,
        ),
        (SET_PHOTO_CROP, _set_photo_crop, SET_PHOTO_CROP_SCHEMA, SupportsResponse.OPTIONAL),
        (DELETE_PHOTO, _delete_photo, DELETE_PHOTO_SCHEMA, SupportsResponse.NONE),
        (UPLOAD_PHOTO, _upload_photo, UPLOAD_PHOTO_SCHEMA, SupportsResponse.OPTIONAL),
        (SET_ALBUM_HIDDEN, _set_album_hidden, SET_ALBUM_HIDDEN_SCHEMA, SupportsResponse.NONE),
    ]
    for name, handler, schema, supports_response in actions:
        async_register_admin_service(
            hass, DOMAIN, name, handler, schema, supports_response=supports_response
        )


# -- Actions -------------------------------------------------------------------------------


async def _set_photo_hidden(call: ServiceCall) -> ServiceResponse:
    return await _patch_photos(call, {"hidden": call.data[ATTR_HIDDEN]})


async def _set_photo_comment(call: ServiceCall) -> ServiceResponse:
    # An empty comment removes it; the frame trims and shortens the rest
    return await _patch_photos(call, {"comment": call.data[ATTR_COMMENT] or None})


async def _set_photo_crop(call: ServiceCall) -> ServiceResponse:
    values = [call.data.get(key) for key in (ATTR_X, ATTR_Y, ATTR_ZOOM)]
    given = [v for v in values if v is not None]
    if call.data[ATTR_RESET] == bool(given) or len(given) not in (0, 3):
        # Either the whole section or the reset, so that no half section reaches the frame
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="crop_or_reset")
    crop = None if call.data[ATTR_RESET] else dict(zip(("x", "y", "zoom"), values, strict=True))
    return await _patch_photos(call, {"crop": crop})


async def _delete_photo(call: ServiceCall) -> None:
    async def delete(coordinator: OpenframeCoordinator) -> None:
        photo_id = await _photo_id(coordinator, call)
        await _request(coordinator, coordinator.client.delete_photo(photo_id))
        coordinator.request_full()

    await _each(await _frames(call, one_with_photo_id=True), delete)


async def _upload_photo(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    frames = await _frames(call)
    if len(frames) != 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="upload_one_frame")
    coordinator = frames[0]
    files = await hass.async_add_executor_job(_read_files, hass, call.data[ATTR_FILE_PATH])
    photos = await _request(
        coordinator, coordinator.client.upload_photos(files, call.data.get(ATTR_ALBUM))
    )
    coordinator.request_full()
    if not call.return_response:
        return None
    return {"photos": [{key: p[key] for key in ("id", "path", "album")} for p in photos]}


async def _set_album_hidden(call: ServiceCall) -> None:
    album, hidden = call.data[ATTR_ALBUM], call.data[ATTR_HIDDEN]

    async def hide(coordinator: OpenframeCoordinator) -> None:
        albums = await _request(
            coordinator, coordinator.client.patch_album(album, hidden), "album_not_found"
        )
        coordinator.set_albums(albums)

    await _each(await _frames(call), hide)


# -- Shared steps ----------------------------------------------------------------------------


async def _patch_photos(call: ServiceCall, patch: dict[str, Any]) -> ServiceResponse:
    """Change the named photo, or the photo on screen of each targeted frame."""
    hass = call.hass

    async def change(coordinator: OpenframeCoordinator) -> dict[str, Any]:
        photo_id = await _photo_id(coordinator, call)
        photo = await _request(coordinator, coordinator.client.patch_photo(photo_id, patch))
        coordinator.request_full()
        return {"device_id": _device_id(hass, coordinator)} | {
            key: photo[key] for key in RECORD_FIELDS
        }

    photos = await _each(await _frames(call, one_with_photo_id=True), change)
    return {"photos": photos} if call.return_response else None


async def _frames(call: ServiceCall, one_with_photo_id: bool = False) -> list[OpenframeCoordinator]:
    """The loaded frames the call targets, as devices, areas or entities."""
    entry_ids = await async_extract_config_entry_ids(call)
    frames = [
        entry.runtime_data
        for entry in call.hass.config_entries.async_loaded_entries(DOMAIN)
        if entry.entry_id in entry_ids
    ]
    if not frames:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_frame")
    if one_with_photo_id and ATTR_PHOTO_ID in call.data and len(frames) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="photo_id_one_frame"
        )
    return frames


async def _photo_id(coordinator: OpenframeCoordinator, call: ServiceCall) -> str:
    """The photo ID of the call, or of the photo the frame shows right now."""
    if ATTR_PHOTO_ID in call.data:
        return call.data[ATTR_PHOTO_ID]
    # The last poll may be 15 seconds old; the action hits the photo on the wall at this moment
    slideshow = await run_command(coordinator, coordinator.client.get_slideshow())
    if slideshow["photo"] is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_photo_on_screen",
            translation_placeholders={"frame": coordinator.config_entry.title},
        )
    return slideshow["photo"]["id"]


async def _each[T](
    frames: list[OpenframeCoordinator], act: Callable[[OpenframeCoordinator], Awaitable[T]]
) -> list[T]:
    """Act on every frame; a frame that fails does not stop the others, its error is raised."""
    results = await asyncio.gather(*(act(c) for c in frames), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return results  # type: ignore[return-value]


async def _request[T](
    coordinator: OpenframeCoordinator, call: Awaitable[T], not_found: str = "photo_not_found"
) -> T:
    """A request of a photo or album action, with the refusals of the photo API translated."""
    return await run_command(coordinator, _photo_refusals(call, not_found))


async def _photo_refusals[T](call: Awaitable[T], not_found: str) -> T:
    try:
        return await call
    except OpenframeAuthError:
        raise
    except OpenframeResponseError as err:
        if err.status == 404:
            key, placeholders = not_found, None
        elif err.code == "read_only_source":
            key, placeholders = "read_only_source", None
        elif err.status == 415:
            key, placeholders = "unsupported_format", {"message": err.message}
        elif err.status == 507:
            key, placeholders = "storage_full", None
        else:
            # The generic mapping of the entities' commands takes the rest
            raise
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders=placeholders,
        ) from err


def _read_files(hass: HomeAssistant, paths: list[str]) -> list[UploadFile]:
    """Check the paths of an upload, then read its files; runs in the executor, as both touch
    the disk."""
    # Every path is checked before a file is read or anything is sent
    for path in paths:
        if not hass.config.is_allowed_path(path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="path_not_allowed",
                translation_placeholders={"path": path},
            )
    files = []
    for path in paths:
        try:
            content = Path(path).read_bytes()
        except OSError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="file_not_readable",
                translation_placeholders={"path": path},
            ) from err
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        files.append(UploadFile(Path(path).name, content, content_type))
    return files


def _device_id(hass: HomeAssistant, coordinator: OpenframeCoordinator) -> str | None:
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, coordinator.frame_id), coordinator.config_entry.entry_id
    )
    return None if device is None else device.id
