"""An openframe frame in memory, served over HTTP for the tests.

The fake frame implements the endpoints of openframe's API that the integration uses, with enough
behaviour for the scenarios of the specs. Every request and every response is validated against
``tests/contract/openapi.yaml``; a mismatch is recorded in ``FakeFrame.contract_errors`` with the
operation and the offending field, and the ``frame`` fixture fails the test on it.

Switches change how the frame behaves: ``safe_mode``, ``display["available"]`` (device
administrator), ``outdated`` (an app before the slideshow API, answering 404 for ``/slideshow``),
``revoke_all()`` (every token rejected), ``unreachable`` (connections are dropped) and
``not_json`` (an answer that is not JSON) and ``delay`` (a slow answer).
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import itertools
import json
import secrets
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestServer
from openapi_core import Config, OpenAPI
from openapi_core.contrib.aiohttp import AIOHTTPOpenAPIWebRequest, AIOHTTPOpenAPIWebResponse

CONTRACT = Path(__file__).parent / "contract" / "openapi.yaml"
PREFIX = "/api/v1"

FRAME_ID = "f0e1d2c3b4a5968778695a4b3c2d1e0f"
NOW = "2026-11-08T10:00:00Z"

# Errors whose envelope the contract defines per response
ERROR_MESSAGES = {
    "unauthorized": "No valid token.",
    "invalid_code": "The code is wrong.",
    "expired_code": "The code has expired.",
    "pairing_locked": "Too many failed attempts.",
    "not_found": "Not found.",
    "display_unavailable": "openframe is not a device administrator.",
    "display_off": "The display is off.",
    "safe_mode": "The frame is in safe mode.",
    "not_in_safe_mode": "The frame is not in safe mode.",
    "validation_failed": "Invalid request.",
    "update_not_ready": "No update is ready.",
    "install_not_allowed": "Android does not allow openframe to install apps.",
}

_openapi: OpenAPI | None = None


def contract() -> OpenAPI:
    """The pinned contract, parsed once per test session."""
    global _openapi
    if _openapi is None:
        # A JPEG is `type: string, format: binary`; hand the validator the bytes as a string
        config = Config(
            extra_media_type_deserializers={"image/jpeg": lambda b: b.decode("latin-1")}
        )
        _openapi = OpenAPI.from_file_path(str(CONTRACT), config=config)
    return _openapi


def describe(error: BaseException) -> str:
    """A readable text of a validation error, naming the fields jsonschema complained about."""
    parts = [str(error)]
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for schema_error in getattr(current, "schema_errors", ()) or ():
            where = "/".join(str(p) for p in schema_error.absolute_path) or "<root>"
            parts.append(f"{where}: {schema_error.message}")
        current = current.__cause__ or current.__context__
    return "; ".join(parts)


def photo_id(source: str, path: str) -> str:
    return f"{source}-{hashlib.sha1(path.encode()).hexdigest()}"


@dataclass
class FakePhoto:
    path: str
    source: str = "local"
    comment: str | None = None
    hidden: bool = False
    taken_at: str = "2025-07-14T16:20:00Z"
    place: str | None = None
    version: int = 1
    # Key of the shown part; changes when the section or the settings that shape it change
    part: str = "a1"

    @property
    def id(self) -> str:
        return photo_id(self.source, self.path)

    @property
    def album(self) -> str | None:
        head, _, _ = self.path.rpartition("/")
        return head or None


@dataclass
class FakeFrame:
    """State and behaviour of one frame. Tests change the fields directly."""

    info: dict[str, Any] = field(
        default_factory=lambda: {
            "id": FRAME_ID,
            "name": "Test frame",
            "appVersion": "0.5.0",
            "androidVersion": "6.0.1",
            "screen": {"width": 1024, "height": 600},
            "apiVersion": 1,
        }
    )
    settings: dict[str, Any] = field(
        default_factory=lambda: {
            "name": "Test frame",
            "intervalSeconds": 30,
            "order": "shuffle",
            "transition": "fade",
            "transitionDurationMs": 800,
            "fillMode": "auto",
            "orientation": "landscape",
            "clock": {
                "enabled": False,
                "position": "bottom-right",
                "sizePercent": 100,
                "format": "24h",
            },
            "caption": {"albumTitle": True, "place": True, "position": "bottom-left"},
            "language": "en",
            "cacheBudgetMb": 500,
            "displaySchedule": {
                "enabled": False,
                "weekdays": {"on": "07:00", "off": "22:00"},
                "weekend": {"on": "08:00", "off": "23:00"},
                "wakeMinutes": 5,
            },
            "autoUpdateCheck": True,
        }
    )
    display: dict[str, Any] = field(
        default_factory=lambda: {"available": True, "on": True, "cause": "none", "nextChange": None}
    )
    photos: list[FakePhoto] = field(default_factory=list)
    # Albums with a setting of their own: hidden (True) or shown (False)
    album_settings: dict[str, bool] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    update: dict[str, Any] = field(
        default_factory=lambda: {
            "installedVersion": "0.5.0",
            "phase": "idle",
            "latest": None,
            "lastCheck": None,
            "error": None,
            "installAllowed": True,
        }
    )
    library_version: int = 1
    settings_version: int = 1
    transition_fallback: bool = False
    safe_mode: bool = False
    outdated: bool = False
    unreachable: bool = False
    not_json: bool = False
    # Seconds the frame waits before it answers
    delay: float = 0.0
    paused: bool = False
    # Index into the visible photos of the photo on screen, None while none is shown
    current: int | None = 0

    # Pairing
    code: str | None = None
    code_expired: bool = False
    failed_codes: int = 0
    lock_after: int = 5
    clients: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Observations for the tests
    requests: list[tuple[str, str]] = field(default_factory=list)
    bodies: list[tuple[str, str, Any]] = field(default_factory=list)
    contract_errors: list[str] = field(default_factory=list)
    # Extra fields merged into the answer of an operation, to test the contract check
    extra_fields: dict[str, dict[str, Any]] = field(default_factory=dict)

    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    server: TestServer | None = None

    # -- Derived state ---------------------------------------------------------------------

    @property
    def host(self) -> str:
        assert self.server is not None
        return "127.0.0.1"

    @property
    def port(self) -> int:
        assert self.server is not None and self.server.port is not None
        return self.server.port

    def album_hidden(self, album: str | None) -> bool:
        while album:
            if album in self.album_settings:
                return self.album_settings[album]
            album = album.rpartition("/")[0] or None
        return False

    def visible(self, photo: FakePhoto) -> bool:
        return not photo.hidden and not self.album_hidden(photo.album)

    def visible_photos(self) -> list[FakePhoto]:
        return [p for p in self.photos if self.visible(p)]

    def on_screen(self) -> FakePhoto | None:
        shown = self.visible_photos()
        if self.current is None or not shown:
            return None
        return shown[self.current % len(shown)]

    def album_names(self) -> list[str]:
        names: set[str] = set()
        for photo in self.photos:
            album = photo.album
            while album:
                names.add(album)
                album = album.rpartition("/")[0] or None
        return sorted(names)

    @property
    def resting(self) -> bool:
        return not self.display["on"]

    def count(self, method: str, path: str) -> int:
        return Counter(self.requests)[(method, path)]

    def reset_requests(self) -> None:
        self.requests.clear()
        self.bodies.clear()

    # -- Test helpers ----------------------------------------------------------------------

    def add_photo(self, path: str, **kwargs: Any) -> FakePhoto:
        photo = FakePhoto(path, **kwargs)
        self.photos.append(photo)
        self.library_version += 1
        return photo

    def add_source(self, source_id: str, name: str) -> dict[str, Any]:
        source = {
            "id": source_id,
            "kind": "nextcloud-share",
            "serverUrl": "https://cloud.example.com",
            "user": None,
            "settings": {
                "name": name,
                "enabled": True,
                "folder": "/",
                "includeSubfolders": True,
                "removeVanished": True,
                "intervalMinutes": 60,
                "originalsBudgetMb": 1000,
            },
            "status": {
                "syncing": False,
                "waiting": False,
                "lastSyncAt": None,
                "ok": None,
                "error": None,
                "added": 0,
                "updated": 0,
                "removed": 0,
            },
        }
        self.sources.append(source)
        return source

    def finish_sync(
        self,
        source_id: str,
        *,
        at: str = NOW,
        ok: bool = True,
        error: str | None = None,
        added: int = 0,
        updated: int = 0,
        removed: int = 0,
    ) -> None:
        status = self.source(source_id)["status"]
        status.update(
            syncing=False,
            lastSyncAt=at,
            ok=ok,
            error=error,
            added=added,
            updated=updated,
            removed=removed,
        )
        self.library_version += 1

    def source(self, source_id: str) -> dict[str, Any]:
        return next(s for s in self.sources if s["id"] == source_id)

    def revoke_all(self) -> None:
        self.clients.clear()

    def pair_directly(self, name: str = "Home Assistant") -> tuple[str, str]:
        """A pairing without the code step, for tests that start with a configured frame."""
        return self._new_client(name)

    def _new_client(self, name: str) -> tuple[str, str]:
        client_id = f"c{next(self._ids)}"
        token = secrets.token_urlsafe(24)
        self.clients[client_id] = {"token": token, "name": name, "pairedAt": NOW}
        return client_id, token

    # -- JSON views ------------------------------------------------------------------------

    def photo_json(self, photo: FakePhoto) -> dict[str, Any]:
        base = f"{PREFIX}/photos/{photo.id}/image"
        signature = "sig" + photo.id[-6:]
        return {
            "id": photo.id,
            "source": photo.source,
            "path": photo.path,
            "album": photo.album,
            "hidden": photo.hidden,
            "visible": self.visible(photo),
            "quarantined": False,
            "width": 4000,
            "height": 3000,
            "takenAt": photo.taken_at,
            "fileSize": 2_500_000,
            "version": photo.version,
            "crop": None,
            "presentation": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0, "zoom": 1.0},
            "urls": {
                "thumb": f"{base}?size=thumb&v={photo.version}&t={signature}",
                "display": f"{base}?size=display&v={photo.version}&p={photo.part}&t={signature}",
                "full": f"{base}?size=full&v={photo.version}&t={signature}",
            },
            "comment": photo.comment,
            "location": None
            if photo.place is None
            else {"lat": 48.1, "lon": 11.6, "place": photo.place},
        }

    def state_json(self) -> dict[str, Any]:
        return {
            "libraryVersion": self.library_version,
            "settingsVersion": self.settings_version,
            "transitionFallback": self.transition_fallback,
            "safeMode": self.safe_mode,
            "appVersion": self.info["appVersion"],
        }

    def slideshow_json(self) -> dict[str, Any]:
        photo = self.on_screen()
        return {
            "photo": None if photo is None else self.photo_json(photo),
            "paused": self.paused,
            "resting": self.resting,
        }

    def albums_json(self) -> dict[str, Any]:
        albums = []
        for name in self.album_names():
            members = [
                p for p in self.photos if p.album == name or (p.album or "").startswith(name + "/")
            ]
            parent = name.rpartition("/")[0] or None
            hidden = self.album_hidden(name)
            albums.append(
                {
                    "name": name,
                    "count": len(members),
                    "hidden": hidden,
                    "overridesParent": parent is not None and hidden != self.album_hidden(parent),
                    "cover": None if not members else self.photo_json(members[-1])["urls"],
                }
            )
        return {"albums": albums}

    # -- HTTP --------------------------------------------------------------------------------

    async def start(self) -> None:
        app = web.Application(middlewares=[self._middleware])
        app.router.add_route("*", PREFIX + "/{tail:.*}", self._dispatch)
        self.server = TestServer(app, host="127.0.0.1")
        await self.server.start_server()

    async def stop(self) -> None:
        if self.server is not None:
            await self.server.close()

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @web.middleware
    async def _middleware(self, request: web.Request, handler: Any) -> web.StreamResponse:
        path = request.path.removeprefix(PREFIX)
        self.requests.append((request.method, path))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.unreachable:
            assert request.transport is not None
            request.transport.close()
            raise ConnectionResetError
        if self.not_json:
            return web.Response(text="<html>not a frame</html>", content_type="text/html")
        body = await request.read()
        if body:
            try:
                self.bodies.append((request.method, path, json.loads(body)))
            except ValueError:
                self.bodies.append((request.method, path, body))
        if self.outdated and path == "/slideshow":
            # An app before the slideshow API: the path does not exist in its contract
            return error(404, "not_found")
        openapi_request = AIOHTTPOpenAPIWebRequest(request, body=body or None)
        try:
            contract().validate_request(openapi_request)
        except Exception as exc:
            self.contract_errors.append(f"request {request.method} {path}: {describe(exc)}")
            return error(400, "validation_failed")
        response = await handler(request)
        operation = OPERATIONS.get((request.method, request.match_info["tail"].split("/")[0]))
        extra = self.extra_fields.get(operation or "")
        if extra and isinstance(response, web.Response) and response.body:
            data = json.loads(response.body)
            data.update(extra)
            response = web.json_response(data, status=response.status)
        try:
            contract().validate_response(openapi_request, AIOHTTPOpenAPIWebResponse(response))
        except Exception as exc:
            self.contract_errors.append(
                f"response {operation or ''} {request.method} {path} {response.status}: "
                f"{describe(exc)}"
            )
        return response

    async def _dispatch(self, request: web.Request) -> web.StreamResponse:
        path = request.path.removeprefix(PREFIX)
        method = request.method
        parts = path.strip("/").split("/")
        public = {("GET", "/info"), ("POST", "/pairing"), ("POST", "/pairing/code")}
        if (method, path) not in public and not self._authorized(request):
            return error(401, "unauthorized")
        raw = await request.read()
        body = json.loads(raw) if raw else None
        match (method, parts):
            case ("GET", ["info"]):
                return web.json_response(self.info)
            case ("POST", ["pairing", "code"]):
                if self.failed_codes < self.lock_after:
                    self.code = f"{secrets.randbelow(10**6):06d}"
                    self.code_expired = False
                return web.Response(status=204)
            case ("POST", ["pairing"]):
                return self._pair(body)
            case ("DELETE", ["clients", client_id]):
                if self.clients.pop(client_id, None) is None:
                    return error(404, "not_found")
                return web.Response(status=204)
            case ("GET", ["state"]):
                return web.json_response(self.state_json())
            case ("GET", ["display"]):
                return web.json_response(self.display)
            case ("PUT", ["display"]):
                if not self.display["available"]:
                    return error(409, "display_unavailable")
                self.display.update(on=body["on"], cause="manual")
                return web.json_response(self.display)
            case ("GET", ["slideshow"]):
                if self.safe_mode:
                    return error(503, "safe_mode")
                return web.json_response(self.slideshow_json())
            case ("POST", ["slideshow"]):
                return self._control(body["action"])
            case ("GET", ["settings"]):
                return web.json_response(self.settings)
            case ("PATCH", ["settings"]):
                return self._patch_settings(body)
            case ("GET", ["albums"]):
                return web.json_response(self.albums_json())
            case ("PATCH", ["albums"]):
                if body["name"] not in self.album_names():
                    return error(404, "not_found")
                name = body["name"]
                # The whole branch follows; a setting equal to the parent's is not kept
                self.album_settings = {
                    a: h for a, h in self.album_settings.items() if not a.startswith(name + "/")
                }
                self.album_settings.pop(name, None)
                parent = name.rpartition("/")[0] or None
                if body["hidden"] != self.album_hidden(parent):
                    self.album_settings[name] = body["hidden"]
                self.library_version += 1
                return web.json_response(self.albums_json())
            case ("GET", ["photos"]):
                return self._photos(request)
            case ("GET", ["photos", pid, "image"]):
                photo = next((p for p in self.photos if p.id == pid), None)
                if photo is None:
                    return error(404, "not_found")
                if self.safe_mode:
                    return error(503, "safe_mode")
                size = request.query["size"]
                return web.Response(body=image_bytes(photo, size), content_type="image/jpeg")
            case ("GET", ["sources"]):
                return web.json_response({"sources": self.sources})
            case ("POST", ["sources", source_id, "sync"]):
                if not any(s["id"] == source_id for s in self.sources):
                    return error(404, "not_found")
                if self.safe_mode:
                    return error(503, "safe_mode")
                status = self.source(source_id)["status"]
                started = not status["syncing"]
                status["syncing"] = True
                return web.json_response({"started": started}, status=202)
            case ("GET", ["update"]):
                return web.json_response(self.update)
            case ("POST", ["update", "check"]):
                if self.update["phase"] in ("idle", "ready"):
                    self.update["phase"] = "checking"
                return web.json_response(self.update, status=202)
            case ("POST", ["update", "install"]):
                if self.update["phase"] != "ready":
                    return error(409, "update_not_ready")
                if not self.update["installAllowed"]:
                    return error(409, "install_not_allowed")
                self.update["phase"] = "installing"
                self.display.update(on=True, cause="wake")
                return web.json_response(self.update, status=202)
            case ("POST", ["safe-mode", "exit"]):
                if not self.safe_mode:
                    return error(409, "not_in_safe_mode")
                self.safe_mode = False
                return web.json_response({}, status=202)
        return error(404, "not_found")

    def _authorized(self, request: web.Request) -> bool:
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ")
        return header.startswith("Bearer ") and any(
            c["token"] == token for c in self.clients.values()
        )

    def _pair(self, body: dict[str, Any]) -> web.Response:
        if self.failed_codes >= self.lock_after:
            response = error(429, "pairing_locked")
            response.headers["Retry-After"] = "60"
            return response
        if self.code is None or body.get("code") != self.code:
            self.failed_codes += 1
            return error(401, "invalid_code")
        if self.code_expired:
            return error(401, "expired_code")
        self.code = None
        name = body.get("deviceName") or "Unknown device"
        client_id, token = self._new_client(name)
        client = {
            "id": client_id,
            "name": name,
            "pairedAt": NOW,
            "lastSeenAt": NOW,
            "current": True,
        }
        return web.json_response({"token": token, "client": client}, status=201)

    def _control(self, action: str) -> web.Response:
        if self.safe_mode:
            return error(503, "safe_mode")
        if action in ("next", "previous"):
            if self.resting:
                return error(409, "display_off")
            shown = self.visible_photos()
            if shown:
                step = 1 if action == "next" else -1
                self.current = ((self.current or 0) + step) % len(shown)
        else:
            self.paused = action == "pause"
        return web.json_response(self.slideshow_json())

    def _patch_settings(self, body: dict[str, Any]) -> web.Response:
        merged = copy.deepcopy(self.settings)
        fields: dict[str, str] = {}
        for key, value in body.items():
            if key not in merged:
                fields[key] = "Unknown field."
            elif isinstance(value, dict):
                merged[key].update(value)
            else:
                merged[key] = value
        if not 5 <= merged["intervalSeconds"] <= 86400:
            fields["intervalSeconds"] = "Must be between 5 and 86400."
        if not 0 <= merged["transitionDurationMs"] <= 5000:
            fields["transitionDurationMs"] = "Must be between 0 and 5000."
        if merged["displaySchedule"]["enabled"] and not self.display["available"]:
            fields["displaySchedule.enabled"] = "openframe is not a device administrator."
        if fields:
            return error(400, "validation_failed", fields)
        self.settings = merged
        self.settings_version += 1
        return web.json_response(self.settings)

    def _photos(self, request: web.Request) -> web.Response:
        selected = self.photos
        if "visible" in request.query:
            wanted = request.query["visible"] == "true"
            selected = [p for p in selected if self.visible(p) == wanted]
        limit = int(request.query.get("limit", "100"))
        items = [self.photo_json(p) for p in selected[:limit]]
        return web.json_response(
            {
                "items": items,
                "total": len(selected),
                "nextCursor": "next" if len(selected) > limit else None,
            }
        )


# Operation IDs by method and first path segment, for the contract error messages
OPERATIONS = {
    ("GET", "info"): "getInfo",
    ("POST", "pairing"): "pair",
    ("DELETE", "clients"): "deleteClient",
    ("GET", "state"): "getState",
    ("GET", "display"): "getDisplay",
    ("PUT", "display"): "setDisplay",
    ("GET", "slideshow"): "getSlideshow",
    ("POST", "slideshow"): "controlSlideshow",
    ("GET", "settings"): "getSettings",
    ("PATCH", "settings"): "patchSettings",
    ("GET", "albums"): "listAlbums",
    ("PATCH", "albums"): "patchAlbum",
    ("GET", "photos"): "listPhotos",
    ("GET", "sources"): "listSources",
    ("GET", "update"): "getUpdate",
}


def error(status: int, code: str, fields: dict[str, str] | None = None) -> web.Response:
    body: dict[str, Any] = {"code": code, "message": ERROR_MESSAGES.get(code, code)}
    if fields:
        body["fields"] = fields
    return web.json_response({"error": body}, status=status)


def image_bytes(photo: FakePhoto, size: str) -> bytes:
    """A stand-in for the JPEG: distinct per photo, version, shown part and size."""
    return b"\xff\xd8\xff" + f"{photo.id}:{photo.version}:{photo.part}:{size}".encode()
