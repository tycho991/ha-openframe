"""A thin client for the versioned JSON API of an openframe frame (`/api/v1`).

The answers stay JSON dicts as openframe's contract defines them; the contract tests keep the
integration's reading of them honest. The token never appears in an exception text, a log line or
the client's ``repr``.
"""

from __future__ import annotations

from typing import Any

import aiohttp

# Seconds; sync, update check and install may take longer on a weak frame
TIMEOUT = 10
LONG_TIMEOUT = 60


class OpenframeError(Exception):
    """Base class of the client's errors."""


class OpenframeConnectionError(OpenframeError):
    """The frame did not answer, or its answer was not JSON."""


class OpenframeResponseError(OpenframeError):
    """The frame refused the request with an error envelope."""

    def __init__(
        self, status: int, code: str, message: str, fields: dict[str, str] | None = None
    ) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}


class OpenframeAuthError(OpenframeResponseError):
    """The frame rejected the token (401)."""


class OpenframeClient:
    """One frame at ``host:port``, with or without the token of a pairing."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, port: int, token: str | None = None
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self._token = token

    def __repr__(self) -> str:
        return f"OpenframeClient(host={self.host!r}, port={self.port})"

    @property
    def frame_url(self) -> str:
        """Address of the frame's web UI."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}/"

    @property
    def base_url(self) -> str:
        return f"{self.frame_url}api/v1"

    # -- Without a token -------------------------------------------------------------------

    async def get_info(self) -> dict[str, Any]:
        return await self._request("GET", "/info", auth=False)

    async def show_pairing_code(self) -> None:
        await self._request("POST", "/pairing/code", auth=False)

    async def pair(self, code: str, device_name: str) -> dict[str, Any]:
        return await self._request(
            "POST", "/pairing", json={"code": code, "deviceName": device_name}, auth=False
        )

    # -- With the token --------------------------------------------------------------------

    async def delete_client(self, client_id: str, timeout: float = TIMEOUT) -> None:
        await self._request("DELETE", f"/clients/{client_id}", timeout=timeout)

    async def get_state(self) -> dict[str, Any]:
        return await self._request("GET", "/state")

    async def get_display(self) -> dict[str, Any]:
        return await self._request("GET", "/display")

    async def set_display(self, on: bool) -> dict[str, Any]:
        return await self._request("PUT", "/display", json={"on": on})

    async def get_slideshow(self) -> dict[str, Any]:
        return await self._request("GET", "/slideshow")

    async def control_slideshow(self, action: str) -> dict[str, Any]:
        return await self._request("POST", "/slideshow", json={"action": action})

    async def get_settings(self) -> dict[str, Any]:
        return await self._request("GET", "/settings")

    async def patch_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", "/settings", json=patch)

    async def get_albums(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "/albums"))["albums"]

    async def patch_album(self, name: str, hidden: bool) -> list[dict[str, Any]]:
        answer = await self._request("PATCH", "/albums", json={"name": name, "hidden": hidden})
        return answer["albums"]

    async def count_photos(self, visible: bool | None = None) -> int:
        """Total of all photos, or of the visible or hidden ones, from a one-item page."""
        params = {"limit": "1"}
        if visible is not None:
            params["visible"] = "true" if visible else "false"
        return (await self._request("GET", "/photos", params=params))["total"]

    async def get_photo_image(self, photo_id: str, size: str = "display") -> bytes:
        return await self._request(
            "GET", f"/photos/{photo_id}/image", params={"size": size}, binary=True
        )

    async def get_sources(self) -> list[dict[str, Any]]:
        return (await self._request("GET", "/sources"))["sources"]

    async def sync_source(self, source_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/sources/{source_id}/sync", timeout=LONG_TIMEOUT)

    async def get_update(self) -> dict[str, Any]:
        return await self._request("GET", "/update")

    async def check_update(self) -> dict[str, Any]:
        return await self._request("POST", "/update/check", timeout=LONG_TIMEOUT)

    async def install_update(self) -> dict[str, Any]:
        return await self._request("POST", "/update/install", timeout=LONG_TIMEOUT)

    async def exit_safe_mode(self) -> None:
        await self._request("POST", "/safe-mode/exit")

    # -- Transport -------------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        auth: bool = True,
        binary: bool = False,
        timeout: float | None = None,
    ) -> Any:
        headers = {"Accept": "image/jpeg" if binary else "application/json"}
        if auth and self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"
        # aiohttp's errors carry the request headers, and with them the token: they are
        # neither chained nor kept as context, only their kind ends up in the message.
        failure: str
        try:
            async with self._session.request(
                method,
                self.base_url + path,
                json=json,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT if timeout is None else timeout),
            ) as response:
                if response.status >= 400:
                    raise await self._error(response, auth)
                if response.status == 204:
                    return None
                if binary:
                    return await response.read()
                try:
                    return await response.json()
                except aiohttp.ContentTypeError, ValueError:
                    failure = "the answer is not JSON"
        except TimeoutError:
            failure = "no answer in time"
        except aiohttp.ClientError as err:
            failure = type(err).__name__
        raise OpenframeConnectionError(f"{method} {path}: {failure}")

    @staticmethod
    async def _error(response: aiohttp.ClientResponse, auth: bool) -> OpenframeError:
        try:
            envelope = (await response.json())["error"]
            code, message = envelope["code"], envelope["message"]
            fields = envelope.get("fields")
        except aiohttp.ContentTypeError, ValueError, KeyError, TypeError:
            code, message, fields = "unknown", response.reason or "", None
        if response.status == 401 and auth:
            return OpenframeAuthError(response.status, code, message, fields)
        return OpenframeResponseError(response.status, code, message, fields)
