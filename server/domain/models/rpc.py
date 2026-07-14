import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

PROTOCOL_VERSION = "1.0"


class RpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    protocol_version: str = PROTOCOL_VERSION
    auth_token: str = Field(min_length=16, repr=False)
    cmd: str
    args: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[float] = None
    deadline_unix_ms: Optional[int] = None


class RpcResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    protocol_version: str = PROTOCOL_VERSION
    status: str  # "ok" or "error"
    result: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_boundary: Optional[str] = None
