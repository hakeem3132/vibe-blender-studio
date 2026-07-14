from __future__ import annotations

import asyncio

import httpx
import pytest
from tests.e2e.integration._loopback_http import _client_factory, loopback_streamable_transport


def test_loopback_transport_rejects_nonlocal_destination():
    with pytest.raises(ValueError, match="restricted"):
        loopback_streamable_transport("https://example.com/mcp")


def test_loopback_http_client_ignores_environment_proxy(monkeypatch):
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9")

    async def inspect() -> None:
        async with _client_factory(timeout=httpx.Timeout(1.0)) as client:
            assert client._trust_env is False

    asyncio.run(inspect())
