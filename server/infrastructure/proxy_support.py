"""Actionable diagnostics for optional outbound proxy configuration."""

from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse

PROXY_ENVIRONMENT_KEYS = (
    "ALL_PROXY",
    "all_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
)


@dataclass(frozen=True)
class ProxyCompatibility:
    configured: bool
    outbound_supported: bool
    level: str
    message: str


def inspect_proxy_compatibility(environment: dict[str, str] | None = None) -> ProxyCompatibility:
    values = environment if environment is not None else os.environ
    configured = next((values.get(key, "").strip() for key in PROXY_ENVIRONMENT_KEYS if values.get(key)), "")
    if not configured:
        return ProxyCompatibility(False, True, "debug", "No outbound proxy is configured")

    parsed = urlparse(configured)
    if parsed.scheme not in {"http", "https", "socks4", "socks5", "socks5h"} or not parsed.hostname:
        return ProxyCompatibility(
            True,
            False,
            "warning",
            "Malformed outbound proxy configuration; use a URL such as http://proxy.example:8080. "
            "The local backend remains available, but outbound provider requests may fail.",
        )

    if parsed.scheme.startswith("socks") and importlib.util.find_spec("socksio") is None:
        return ProxyCompatibility(
            True,
            False,
            "warning",
            "A SOCKS proxy is configured, but optional SOCKS support is not installed. "
            "Install the provider environment with `httpx[socks]`, choose an HTTP proxy, or unset ALL_PROXY. "
            "The local backend remains available.",
        )

    return ProxyCompatibility(True, True, "info", f"Outbound {parsed.scheme.upper()} proxy configuration is supported")


def log_proxy_compatibility(logger: logging.Logger) -> ProxyCompatibility:
    result = inspect_proxy_compatibility()
    getattr(logger, result.level)(result.message)
    return result
