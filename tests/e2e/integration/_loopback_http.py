"""Proxy-isolated transport for controlled loopback integration tests only."""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx
from fastmcp.client.transports.http import StreamableHttpTransport


def _client_factory(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
    **client_options: Any,
) -> httpx.AsyncClient:
    options: dict[str, Any] = dict(client_options)
    options.update({"follow_redirects": True, "trust_env": False})
    options["timeout"] = timeout or httpx.Timeout(30.0, read=300.0)
    if headers is not None:
        options["headers"] = headers
    if auth is not None:
        options["auth"] = auth
    return httpx.AsyncClient(**options)


def loopback_streamable_transport(url: str) -> StreamableHttpTransport:
    parsed = urlparse(url)
    host = parsed.hostname
    if host is None:
        raise ValueError("Loopback test transport requires an absolute URL")
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host.lower() == "localhost"
    if not is_loopback:
        raise ValueError("Proxy isolation is restricted to controlled loopback test transports")
    return StreamableHttpTransport(url, httpx_client_factory=_client_factory)
