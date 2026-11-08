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
            json={"on": True, "brightness": 80},
            headers={"Authorization": f"Bearer {token}"},
        ) as response,
    ):
        assert response.status == 400
    assert "brightness" in frame.contract_errors[0]
    frame.contract_errors.clear()
