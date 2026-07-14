"""Verify persistent Milestone 2 IDs, actions and diagnostics after reopening."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import bpy
from blender_ai_mcp.infrastructure.rpc_server import rpc_server
from blender_ai_mcp.vibe_studio.identities import inspect_uuid, lookup_unique
from blender_ai_mcp.vibe_studio.runtime import VibeRuntime

separator = sys.argv.index("--")
results_path, diagnostics_path = [Path(item) for item in sys.argv[separator + 1 : separator + 3]]
results: dict[str, Any] = json.loads(results_path.read_text(encoding="utf-8"))


def check(name: str, expected: Any, actual: Any) -> None:
    passed = expected == actual
    results["checks"].append({"name": name, "passed": passed, "expected": expected, "actual": actual})
    if not passed:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")


runtime = VibeRuntime(bpy)
ids = results["persistent_ids"]
product = lookup_unique(bpy.context.scene.objects, ids["product"])
camera = lookup_unique(bpy.context.scene.objects, ids["camera"])
check("reopen_product_uuid", ids["product"], inspect_uuid(product))
check("reopen_camera_uuid", ids["camera"], inspect_uuid(camera))
check("reopen_material_uuid", ids["material"], inspect_uuid(product.active_material))
check("reopen_product_action_uuid", ids["product_action"], inspect_uuid(product.animation_data.action))
check("reopen_camera_action_uuid", ids["camera_action"], inspect_uuid(camera.animation_data.action))
check(
    "reopen_light_ids",
    sorted(ids["lights"]),
    sorted(inspect_uuid(obj) for obj in bpy.context.scene.objects if obj.type == "LIGHT"),
)
summary = runtime.inspect()
check("reopen_scene_inspectable", True, len(summary["materials"]) >= 2 and len(summary["animations"]) >= 2)
generated = runtime.diagnostics(rpc_server)
payload = json.loads(generated.read_text(encoding="utf-8"))
payload["scene"]["filepath"] = "<redacted>"
diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
diagnostics_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
serialized = diagnostics_path.read_text(encoding="utf-8")
check("diagnostics_redacted", False, "VIBE_RPC_TOKEN" in serialized or "session_token" in serialized)
results["passed"] = all(item["passed"] for item in results["checks"])
results_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
print("VIBE_MILESTONE_2_REOPEN_PASS")
