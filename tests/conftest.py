"""Fixtures shared by all tests: the fake frame and Home Assistant's custom integration loader."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from tests.fake_frame import FakeFrame


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load ``custom_components/openframe`` from this repository."""


@pytest.fixture
async def frame(socket_enabled: None) -> AsyncGenerator[FakeFrame]:
    """A running fake frame; the test fails if a request or response broke the contract."""
    fake = FakeFrame()
    await fake.start()
    try:
        yield fake
    finally:
        await fake.stop()
    assert not fake.contract_errors, "\n".join(fake.contract_errors)
