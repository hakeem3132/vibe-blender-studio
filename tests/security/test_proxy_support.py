from __future__ import annotations

import logging

from server.infrastructure import proxy_support


def test_no_proxy_and_http_proxy_are_supported():
    assert proxy_support.inspect_proxy_compatibility({}).outbound_supported
    http = proxy_support.inspect_proxy_compatibility({"HTTPS_PROXY": "http://proxy.example:8080"})
    assert http.configured
    assert http.outbound_supported
    assert "HTTP" in http.message


def test_malformed_proxy_is_actionable_without_backend_exception():
    result = proxy_support.inspect_proxy_compatibility({"ALL_PROXY": "not-a-proxy-url"})
    assert not result.outbound_supported
    assert "Malformed" in result.message


def test_missing_optional_socks_dependency_is_actionable(monkeypatch):
    monkeypatch.setattr(proxy_support.importlib.util, "find_spec", lambda _name: None)
    result = proxy_support.inspect_proxy_compatibility({"ALL_PROXY": "socks5://proxy.example:1080"})
    assert not result.outbound_supported
    assert "optional SOCKS support is not installed" in result.message


def test_socks_proxy_is_supported_when_optional_dependency_is_installed(monkeypatch):
    monkeypatch.setattr(proxy_support.importlib.util, "find_spec", lambda _name: object())
    result = proxy_support.inspect_proxy_compatibility({"ALL_PROXY": "socks5://proxy.example:1080"})
    assert result.outbound_supported
    assert "SOCKS5" in result.message


def test_proxy_diagnostics_log_and_return_without_stopping_backend(monkeypatch, caplog):
    monkeypatch.setenv("ALL_PROXY", "broken")
    caplog.set_level(logging.WARNING)
    result = proxy_support.log_proxy_compatibility(logging.getLogger("vibe.proxy.test"))
    assert not result.outbound_supported
    assert "Malformed" in caplog.text
