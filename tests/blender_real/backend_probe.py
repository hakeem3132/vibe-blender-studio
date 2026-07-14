"""Backend-side authenticated health probe used by real Blender acceptance."""

from __future__ import annotations

import json

from server.adapters.rpc.client import RpcClient

response = RpcClient("127.0.0.1", 8765, rpc_timeout_seconds=10.0).send_request("ping")
print(json.dumps(response.model_dump(mode="json"), sort_keys=True))
raise SystemExit(0 if response.status == "ok" else 1)
