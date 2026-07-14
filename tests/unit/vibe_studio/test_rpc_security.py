import json
import struct
import time

import pytest
from blender_addon.infrastructure.rpc_security import (
    MAX_REQUEST_BYTES,
    PROTOCOL_VERSION,
    RpcSecurityError,
    SessionCredential,
    redact,
    resolve_bind_address,
    validate_request_envelope,
)
from blender_addon.infrastructure.rpc_server import recv_msg
from server.domain.models.rpc import PROTOCOL_VERSION as BACKEND_PROTOCOL_VERSION


def envelope(token="secret-token-that-is-long-enough"):
    return {
        "request_id": "request-1",
        "protocol_version": PROTOCOL_VERSION,
        "auth_token": token,
        "cmd": "ping",
        "args": {},
    }


def test_default_binding_is_loopback(monkeypatch):
    monkeypatch.delenv("VIBE_RPC_HOST", raising=False)
    assert resolve_bind_address() == ("127.0.0.1", 8765, False)


def test_protocol_contract_is_identical_on_both_sides():
    assert BACKEND_PROTOCOL_VERSION == PROTOCOL_VERSION


def test_remote_binding_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("VIBE_RPC_HOST", "0.0.0.0")
    monkeypatch.delenv("VIBE_RPC_ALLOW_REMOTE", raising=False)
    with pytest.raises(RpcSecurityError, match="explicit"):
        resolve_bind_address()


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value.pop("auth_token"), "authentication_required"),
        (lambda value: value.update(auth_token="wrong-token-long-enough"), "authentication_failed"),
        (lambda value: value.update(protocol_version="99"), "protocol_mismatch"),
    ],
)
def test_invalid_envelopes_are_rejected(mutation, code):
    value = envelope()
    mutation(value)
    credential = SessionCredential("secret-token-that-is-long-enough", time.time() + 60)
    with pytest.raises(RpcSecurityError) as error:
        validate_request_envelope(value, credential)
    assert error.value.code == code


def test_expired_session_is_rejected():
    with pytest.raises(RpcSecurityError) as error:
        validate_request_envelope(envelope(), SessionCredential("secret-token-that-is-long-enough", time.time() - 1))
    assert error.value.code == "session_expired"


class HeaderSocket:
    def __init__(self, size):
        self.data = bytearray(struct.pack(">I", size))

    def recv(self, count):
        result = self.data[:count]
        del self.data[:count]
        return bytes(result)


def test_oversized_payload_rejected_before_body_read():
    with pytest.raises(RpcSecurityError) as error:
        recv_msg(HeaderSocket(MAX_REQUEST_BYTES + 1))
    assert error.value.code == "request_too_large"


def test_diagnostics_redaction_is_recursive():
    value = redact({"auth_token": "secret", "nested": {"api_key": "secret", "ok": 1}})
    assert json.dumps(value).count("secret") == 0
