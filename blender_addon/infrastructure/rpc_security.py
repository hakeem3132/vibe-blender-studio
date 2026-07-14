"""Security primitives for the local Blender RPC transport."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = int(os.environ.get("VIBE_RPC_MAX_REQUEST_BYTES", str(1024 * 1024)))
MAX_RESPONSE_BYTES = int(os.environ.get("VIBE_RPC_MAX_RESPONSE_BYTES", str(1024 * 1024)))
MAX_JSON_DEPTH = int(os.environ.get("VIBE_RPC_MAX_JSON_DEPTH", "24"))
MAX_BATCH_SIZE = int(os.environ.get("VIBE_RPC_MAX_BATCH_SIZE", "1"))
MAX_TOOL_CALLS = int(os.environ.get("VIBE_RPC_MAX_TOOL_CALLS", "16"))
SESSION_TTL_SECONDS = int(os.environ.get("VIBE_RPC_SESSION_TTL_SECONDS", "28800"))


class RpcSecurityError(ValueError):
    """A request failed a transport security policy."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SessionCredential:
    token: str
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


def resolve_bind_address() -> tuple[str, int, bool]:
    host = os.environ.get("VIBE_RPC_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    port = int(os.environ.get("VIBE_RPC_PORT", str(DEFAULT_PORT)))
    if not 1 <= port <= 65535:
        raise RpcSecurityError("invalid_port", "VIBE_RPC_PORT must be between 1 and 65535")
    remote = host not in {"127.0.0.1", "::1", "localhost"}
    if remote and os.environ.get("VIBE_RPC_ALLOW_REMOTE") != "1":
        raise RpcSecurityError(
            "remote_binding_denied",
            "Remote RPC binding requires the explicit VIBE_RPC_ALLOW_REMOTE=1 opt-in",
        )
    return host, port, remote


def session_file_path() -> Path:
    configured = os.environ.get("VIBE_RPC_SESSION_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path(tempfile.gettempdir()) / "vibe-blender-studio" / f"session-{os.getuid()}.json"


def create_session() -> SessionCredential:
    credential = SessionCredential(
        token=secrets.token_urlsafe(32),
        expires_at=time.time() + SESSION_TTL_SECONDS,
    )
    path = session_file_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {
        "token": credential.token,
        "expires_at": credential.expires_at,
        "protocol_version": PROTOCOL_VERSION,
        "pid": os.getpid(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)
    return credential


def load_session() -> SessionCredential:
    token = os.environ.get("VIBE_RPC_SESSION_TOKEN")
    if token:
        return SessionCredential(token=token, expires_at=time.time() + SESSION_TTL_SECONDS)
    try:
        payload = json.loads(session_file_path().read_text(encoding="utf-8"))
        credential = SessionCredential(token=str(payload["token"]), expires_at=float(payload["expires_at"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RpcSecurityError("session_unavailable", "No valid local RPC session is available") from exc
    if credential.expired:
        raise RpcSecurityError("session_expired", "The local RPC session has expired")
    return credential


def json_depth(value: Any, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        return depth
    if isinstance(value, dict):
        return max((json_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, list):
        return max((json_depth(item, depth + 1) for item in value), default=depth)
    return depth


def validate_request_envelope(message: Any, credential: SessionCredential) -> dict[str, Any]:
    if not isinstance(message, dict):
        raise RpcSecurityError("invalid_schema", "RPC request must be a JSON object")
    if json_depth(message) > MAX_JSON_DEPTH:
        raise RpcSecurityError("json_too_deep", "RPC request exceeds the JSON nesting limit")
    if message.get("protocol_version") != PROTOCOL_VERSION:
        raise RpcSecurityError("protocol_mismatch", f"Protocol version {PROTOCOL_VERSION} is required")
    supplied = message.get("auth_token")
    if not isinstance(supplied, str) or not supplied:
        raise RpcSecurityError("authentication_required", "Session authentication is required")
    if credential.expired:
        raise RpcSecurityError("session_expired", "The local RPC session has expired")
    if not secrets.compare_digest(supplied, credential.token):
        raise RpcSecurityError("authentication_failed", "Session authentication failed")
    request_id = message.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise RpcSecurityError("invalid_request_id", "A request ID is required")
    args = message.get("args", {})
    if not isinstance(args, dict):
        raise RpcSecurityError("invalid_schema", "RPC args must be a JSON object")
    operations = args.get("operations", [])
    if isinstance(operations, list) and len(operations) > MAX_TOOL_CALLS:
        raise RpcSecurityError("too_many_tool_calls", "RPC request exceeds the tool-call limit")
    return message


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key.lower() in {"auth_token", "token", "api_key", "authorization"} else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
