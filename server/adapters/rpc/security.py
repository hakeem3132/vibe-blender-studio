"""Backend side of the local ephemeral RPC session exchange."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

MAX_REQUEST_BYTES = int(os.environ.get("VIBE_RPC_MAX_REQUEST_BYTES", str(1024 * 1024)))
MAX_RESPONSE_BYTES = int(os.environ.get("VIBE_RPC_MAX_RESPONSE_BYTES", str(1024 * 1024)))
SESSION_TTL_SECONDS = int(os.environ.get("VIBE_RPC_SESSION_TTL_SECONDS", "28800"))


class RpcSecurityError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SessionCredential:
    token: str
    expires_at: float


def _path() -> Path:
    configured = os.environ.get("VIBE_RPC_SESSION_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path(tempfile.gettempdir()) / "vibe-blender-studio" / f"session-{os.getuid()}.json"


def load_session() -> SessionCredential:
    token = os.environ.get("VIBE_RPC_SESSION_TOKEN")
    if token:
        return SessionCredential(token, time.time() + SESSION_TTL_SECONDS)
    try:
        payload = json.loads(_path().read_text(encoding="utf-8"))
        credential = SessionCredential(str(payload["token"]), float(payload["expires_at"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RpcSecurityError("session_unavailable", "No valid local RPC session is available") from exc
    if time.time() >= credential.expires_at:
        raise RpcSecurityError("session_expired", "The local RPC session has expired")
    return credential


def create_session() -> SessionCredential:
    """Create a temporary client session for startup ordering and tests.

    Blender rotates this credential when its listener starts, so the next
    request reloads the add-on-owned session.
    """

    credential = SessionCredential(secrets.token_urlsafe(32), time.time() + SESSION_TTL_SECONDS)
    path = _path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"token": credential.token, "expires_at": credential.expires_at}),
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)
    return credential
