"""Config flow: add a frame by its address and the pairing code it shows.

``user`` reads the frame's info without a token, ``pair`` asks the frame to show a code and
exchanges the code the user types for a token, and a frame without the slideshow API is refused
after its new pairing is revoked again. ``reauth`` pairs again with a code, ``reconfigure`` takes a
new address for the same frame and keeps the token.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import probatio
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OpenframeClient,
    OpenframeConnectionError,
    OpenframeError,
    OpenframeResponseError,
)
from .const import (
    API_VERSION,
    CONF_CLIENT_ID,
    DEFAULT_PORT,
    DEVICE_NAME,
    DOMAIN,
    MIN_OPENFRAME_VERSION,
)

_LOGGER = logging.getLogger(__name__)

CODE = "code"

ADDRESS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=65535)
        ),
    }
)
CODE_SCHEMA = probatio.Schema({probatio.Required(CODE): str})


class NotOpenframe(Exception):
    """Something answered, but not an openframe frame with API version 1."""


class OpenframeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add, re-pair and move openframe frames."""

    VERSION = 1

    def __init__(self) -> None:
        self._host = ""
        self._port = DEFAULT_PORT
        self._info: dict[str, Any] = {}

    def _client(self, token: str | None = None) -> OpenframeClient:
        return OpenframeClient(async_get_clientsession(self.hass), self._host, self._port, token)

    async def _read_info(self, host: str, port: int) -> dict[str, Any]:
        """The frame's info; raises ``OpenframeConnectionError`` or ``NotOpenframe``."""
        client = OpenframeClient(async_get_clientsession(self.hass), host, port)
        try:
            info = await client.get_info()
        except OpenframeResponseError as err:
            raise NotOpenframe from err
        if not isinstance(info, dict) or info.get("apiVersion") != API_VERSION or "id" not in info:
            raise NotOpenframe
        return info

    # -- Adding a frame --------------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            try:
                info = await self._read_info(host, port)
            except OpenframeConnectionError:
                errors["base"] = "cannot_connect"
            except NotOpenframe:
                errors["base"] = "not_openframe"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured()
                self._host, self._port, self._info = host, port, info
                return await self.async_step_pair()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(ADDRESS_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_pair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask the frame to show a code, then exchange the typed code for a token."""
        errors: dict[str, str] = {}
        if user_input is None:
            if (failure := await self._show_code()) is not None:
                errors["base"] = failure
        else:
            code = re.sub(r"\s", "", user_input[CODE])
            if not re.fullmatch(r"[0-9]{6}", code):
                errors[CODE] = "invalid_code"
            else:
                try:
                    paired = await self._client().pair(code, DEVICE_NAME)
                except OpenframeConnectionError:
                    errors["base"] = "cannot_connect"
                except OpenframeResponseError as err:
                    if err.status == 429:
                        errors["base"] = "locked"
                    elif err.code == "expired_code":
                        errors["base"] = "expired_code"
                        # The frame shows a new code; a failure to ask for it shows as a later error
                        await self._show_code()
                    else:
                        errors[CODE] = "invalid_code"
                else:
                    return await self._finish_pairing(paired["token"], paired["client"]["id"])
        return self.async_show_form(
            step_id="pair",
            data_schema=CODE_SCHEMA,
            errors=errors,
            description_placeholders={"name": self._info.get("name", "")},
        )

    async def _show_code(self) -> str | None:
        try:
            await self._client().show_pairing_code()
        except OpenframeConnectionError:
            return "cannot_connect"
        except OpenframeResponseError:
            return "not_openframe"
        return None

    async def _finish_pairing(self, token: str, client_id: str) -> ConfigFlowResult:
        client = self._client(token)
        try:
            await client.get_slideshow()
        except OpenframeResponseError as err:
            # 503 safe_mode: the endpoint exists, only the slideshow rests
            if (err.status, err.code) != (503, "safe_mode"):
                await self._revoke(client, client_id)
                if err.status == 404:
                    # An app before the slideshow API
                    return self._outdated()
                return self.async_abort(
                    reason="unexpected_answer", description_placeholders={"message": err.message}
                )
        except OpenframeConnectionError:
            await self._revoke(client, client_id)
            return self.async_abort(reason="cannot_connect")
        try:
            display = await client.get_display()
        except OpenframeResponseError as err:
            await self._revoke(client, client_id)
            return self.async_abort(
                reason="unexpected_answer", description_placeholders={"message": err.message}
            )
        except OpenframeConnectionError:
            await self._revoke(client, client_id)
            return self.async_abort(reason="cannot_connect")
        if "brightness" not in display:
            # An app before openframe 0.6.0
            await self._revoke(client, client_id)
            return self._outdated()
        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_TOKEN: token,
            CONF_CLIENT_ID: client_id,
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=data)
        return self.async_create_entry(title=self._info["name"], data=data)

    def _outdated(self) -> ConfigFlowResult:
        return self.async_abort(
            reason="outdated_frame", description_placeholders={"version": MIN_OPENFRAME_VERSION}
        )

    @staticmethod
    async def _revoke(client: OpenframeClient, client_id: str) -> None:
        """Leave no orphan pairing on the frame."""
        try:
            await client.delete_client(client_id)
        except OpenframeError:
            _LOGGER.debug("Could not revoke the new pairing %s", client_id)

    # -- Pairing again ---------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._host = entry_data[CONF_HOST]
        self._port = entry_data[CONF_PORT]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await self._read_info(self._host, self._port)
            except OpenframeConnectionError:
                errors["base"] = "cannot_connect"
            except NotOpenframe:
                errors["base"] = "not_openframe"
            else:
                if info["id"] != entry.unique_id:
                    return self.async_abort(reason="wrong_frame")
                self._info = info
                return await self.async_step_pair()
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    # -- A new address ---------------------------------------------------------------------

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry: ConfigEntry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            try:
                info = await self._read_info(host, port)
            except OpenframeConnectionError:
                errors["base"] = "cannot_connect"
            except NotOpenframe:
                errors["base"] = "not_openframe"
            else:
                if info["id"] != entry.unique_id:
                    errors["base"] = "wrong_frame"
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_HOST: host, CONF_PORT: port}
                    )
        suggested = user_input or {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data[CONF_PORT],
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(ADDRESS_SCHEMA, suggested),
            errors=errors,
        )
