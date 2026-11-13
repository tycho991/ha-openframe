"""The fake frame itself: its contract check must catch what the real frame would never send."""

from __future__ import annotations

import aiohttp

from tests.fake_frame import FakeFrame


async def test_answers_match_the_contract(frame: FakeFrame) -> None:
    frame.add_photo("holiday/IMG_0042.jpg", comment="Summer 2025", place="Munich, Germany")
    frame.add_source("nc1", "Shared photos")
    _, token = frame.pair_directly()
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession(frame.url, headers=headers) as session:
        for path in (
            "/info",
            "/state",
            "/display",
            "/slideshow",
            "/settings",
            "/albums",
            "/photos?limit=1",
            "/photos?visible=true&limit=1",
            "/sources",
            "/update",
        ):
            async with session.get(f"/api/v1{path}") as response:
                assert response.status == 200, path
    assert frame.contract_errors == []


async def test_response_outside_the_contract_names_the_field(frame: FakeFrame) -> None:
    """integration-distribution › Contract with the openframe API › Response outside the
    contract."""
    _, token = frame.pair_directly()
    frame.extra_fields["getState"] = {"brightness": 80}
    async with (
        aiohttp.ClientSession(frame.url) as session,
        session.get("/api/v1/state", headers={"Authorization": f"Bearer {token}"}),
    ):
        pass
    assert len(frame.contract_errors) == 1
    assert "getState" in frame.contract_errors[0]
    assert "brightness" in frame.contract_errors[0]
    frame.contract_errors.clear()


async def test_request_outside_the_contract_is_recorded(frame: FakeFrame) -> None:
    _, token = frame.pair_directly()
    async with (
        aiohttp.ClientSession(frame.url) as session,
        session.put(
            "/api/v1/display",
            json={"on": True, "glow": 80},
            headers={"Authorization": f"Bearer {token}"},
        ) as response,
    ):
        assert response.status == 400
    assert "glow" in frame.contract_errors[0]
    frame.contract_errors.clear()


async def _call(
    frame: FakeFrame, method: str, path: str, body: object | None = None
) -> tuple[int, dict]:
    _, token = frame.pair_directly()
    async with (
        aiohttp.ClientSession(frame.url) as session,
        session.request(
            method, f"/api/v1{path}", json=body, headers={"Authorization": f"Bearer {token}"}
        ) as response,
    ):
        return response.status, await response.json()


async def test_brightness_outside_a_dim_period_becomes_the_setting(frame: FakeFrame) -> None:
    status, display = await _call(frame, "PUT", "/display", {"brightness": 60})
    assert status == 200
    assert display["brightness"]["level"] == 60
    assert frame.settings["brightness"] == {"mode": "manual", "level": 60}


async def test_brightness_in_a_dim_period_keeps_the_setting(frame: FakeFrame) -> None:
    frame.display["brightness"].update(dimmed=True, level=20)
    status, display = await _call(frame, "PUT", "/display", {"brightness": 50})
    assert status == 200
    assert display["brightness"]["level"] == 50
    assert frame.settings["brightness"] == {"mode": "system", "level": 80}


async def test_display_unavailable_comes_before_brightness_unavailable(frame: FakeFrame) -> None:
    frame.display["available"] = False
    frame.display["brightness"]["available"] = False
    status, answer = await _call(frame, "PUT", "/display", {"on": False, "brightness": 30})
    assert (status, answer["error"]["code"]) == (409, "display_unavailable")
    assert frame.display["on"] is True
    assert frame.display["brightness"]["level"] == 80


async def test_brightness_unavailable_changes_nothing(frame: FakeFrame) -> None:
    frame.display["brightness"]["available"] = False
    status, answer = await _call(frame, "PUT", "/display", {"on": False, "brightness": 30})
    assert (status, answer["error"]["code"]) == (409, "brightness_unavailable")
    assert frame.display["on"] is True
    assert frame.display["brightness"]["level"] == 80


async def test_empty_display_request_is_outside_the_contract(frame: FakeFrame) -> None:
    status, _ = await _call(frame, "PUT", "/display", {})
    assert status == 400
    assert frame.contract_errors
    frame.contract_errors.clear()


async def test_mode_without_permission_or_light_sensor(frame: FakeFrame) -> None:
    frame.display["brightness"].update(available=False)
    status, answer = await _call(frame, "PATCH", "/settings", {"brightness": {"mode": "manual"}})
    assert (status, list(answer["error"]["fields"])) == (400, ["brightness.mode"])
    status, _ = await _call(frame, "PATCH", "/settings", {"brightness": {"level": 40}})
    assert status == 200
    frame.display["brightness"].update(available=True, autoSupported=False)
    status, answer = await _call(frame, "PATCH", "/settings", {"brightness": {"mode": "auto"}})
    assert (status, list(answer["error"]["fields"])) == (400, ["brightness.mode"])
    assert frame.settings["brightness"] == {"mode": "system", "level": 40}


async def test_mode_auto_switches_on_automatic_brightness(frame: FakeFrame) -> None:
    status, _ = await _call(frame, "PATCH", "/settings", {"brightness": {"mode": "auto"}})
    assert status == 200
    assert frame.display["brightness"]["auto"] is True


async def test_dim_level_out_of_range(frame: FakeFrame) -> None:
    status, answer = await _call(frame, "PATCH", "/settings", {"displaySchedule": {"dimLevel": 0}})
    assert (status, list(answer["error"]["fields"])) == (400, ["displaySchedule.dimLevel"])


async def test_frame_before_the_brightness(frame: FakeFrame) -> None:
    frame.before_brightness = True
    status, display = await _call(frame, "GET", "/display")
    assert status == 200
    assert "brightness" not in display
    assert frame.contract_errors == []
