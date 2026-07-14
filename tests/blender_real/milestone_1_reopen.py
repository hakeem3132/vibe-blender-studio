"""Stage 2 persistence, inspection and diagnostics validation."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import bpy


def arguments() -> tuple[Path, Path]:
    separator = sys.argv.index("--")
    return tuple(Path(item) for item in sys.argv[separator + 1 : separator + 3])  # type: ignore[return-value]


result_path, diagnostics_path = arguments()
results: dict[str, Any] = json.loads(result_path.read_text(encoding="utf-8"))


def check(name: str, expected: Any, actual: Any, passed: bool | None = None) -> None:
    outcome = expected == actual if passed is None else passed
    results["checks"].append({"name": name, "passed": bool(outcome), "expected": expected, "actual": actual})
    if not outcome:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")


try:
    enable_result = bpy.ops.preferences.addon_enable(module="blender_ai_mcp")
    check("reopen_addon_enabled", ["FINISHED"], sorted(enable_result))
    import blender_ai_mcp
    from blender_ai_mcp.vibe_studio.identities import lookup_unique
    from blender_ai_mcp.vibe_studio.runtime import VibeRuntime

    runtime = VibeRuntime(bpy)
    stable_id = results["stable_uuid"]
    cube = lookup_unique(bpy.context.scene.objects, stable_id)
    check("uuid_persists_after_reopen", stable_id, cube.get("vibe_uuid"))
    summary = runtime.inspect()
    check("reopened_scene_inspectable", True, summary["object_count"] >= 4)
    generated = runtime.diagnostics(blender_ai_mcp.rpc_server)
    shutil.copyfile(generated, diagnostics_path)
    diagnostics = diagnostics_path.read_text(encoding="utf-8")
    check("diagnostics_exported", True, diagnostics_path.is_file())
    check("diagnostics_token_redacted", False, "auth_token" in diagnostics or "api_key" in diagnostics)
    check("diagnostics_filepath_redacted", True, '"filepath": "<redacted>"' in diagnostics)
    results["artifacts"]["diagnostics"] = str(diagnostics_path)
    results["passed"] = all(item["passed"] for item in results["checks"])
finally:
    result_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")

print("VIBE_MILESTONE_1_STAGE_2_PASS")
