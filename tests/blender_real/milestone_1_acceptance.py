"""Stage 1 real Blender acceptance for the packaged add-on."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bpy


def arguments() -> tuple[Path, Path, Path]:
    separator = sys.argv.index("--")
    return tuple(Path(item) for item in sys.argv[separator + 1 : separator + 4])  # type: ignore[return-value]


class RecordingLayout:
    def __init__(self, actions: list[str], icons: list[str]):
        self.actions = actions
        self.icons = icons

    def box(self):
        return self

    def row(self, **_kwargs):
        return self

    def label(self, **kwargs):
        icon = kwargs.get("icon")
        if icon:
            self.icons.append(icon)

    def prop(self, owner, property_name, **_kwargs):
        getattr(owner, property_name)

    def operator(self, identifier, **kwargs):
        if identifier != "vibe.action":
            raise AssertionError(f"Unexpected UI operator: {identifier}")
        icon = kwargs.get("icon")
        if icon and icon != "NONE":
            self.icons.append(icon)
        result = SimpleNamespace(action="")
        self.actions.append(result)  # type: ignore[arg-type]
        return result


def serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


zip_path, blend_path, result_path = arguments()
results: dict[str, Any] = {
    "passed": False,
    "checks": [],
    "versions": {"blender": bpy.app.version_string, "python": sys.version.split()[0]},
    "artifacts": {"blend": str(blend_path), "results": str(result_path)},
}


def check(name: str, expected: Any, actual: Any, passed: bool | None = None) -> None:
    outcome = expected == actual if passed is None else passed
    results["checks"].append(
        {"name": name, "passed": bool(outcome), "expected": serializable(expected), "actual": serializable(actual)}
    )
    if not outcome:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")


try:
    check("factory_scene_started", 3, len(bpy.context.scene.objects))
    install_result = bpy.ops.preferences.addon_install(filepath=str(zip_path))
    check("packaged_addon_installed", {"FINISHED"}, install_result)
    enable_result = bpy.ops.preferences.addon_enable(module="blender_ai_mcp")
    check("packaged_addon_enabled", {"FINISHED"}, enable_result)

    import blender_ai_mcp
    from blender_ai_mcp.infrastructure.rpc_security import PROTOCOL_VERSION
    from blender_ai_mcp.version import DISPLAY_VERSION
    from blender_ai_mcp.vibe_studio import ui
    from blender_ai_mcp.vibe_studio.identities import inspect_uuid
    from blender_ai_mcp.vibe_studio.runtime import VibeRuntime

    results["versions"].update({"addon": DISPLAY_VERSION, "protocol": PROTOCOL_VERSION})
    check(
        "panel_registered",
        ui.VIBE_PT_Studio,
        bpy.types.Panel.bl_rna_get_subclass_py(ui.VIBE_PT_Studio.bl_idname),
    )
    check(
        "operator_registered",
        ui.VIBE_OT_Action,
        bpy.types.Operator.bl_rna_get_subclass_py("VIBE_OT_action"),
    )
    check(
        "property_group_registered",
        ui.VIBE_PG_State,
        bpy.types.PropertyGroup.bl_rna_get_subclass_py("VIBE_PG_State"),
    )
    check("scene_properties_registered", True, hasattr(bpy.types.Scene, "vibe_studio"))
    check("operator_callable", True, hasattr(bpy.ops.vibe, "action"))
    check("panel_category", "Vibe Studio", ui.VIBE_PT_Studio.bl_category)

    draw_actions: list[Any] = []
    draw_icons: list[str] = []
    fake_panel = SimpleNamespace(layout=RecordingLayout(draw_actions, draw_icons))
    ui.VIBE_PT_Studio.draw(fake_panel, bpy.context)
    mapped_actions = {item.action for item in draw_actions}
    check("draw_method_completed", True, True)
    check("enabled_controls_mapped", ui.ENABLED_ACTIONS, mapped_actions)
    icon_items = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
    valid_icons = {item.identifier for item in icon_items}
    check("ui_icons_valid", True, all(icon in valid_icons for icon in draw_icons))

    runtime = VibeRuntime(bpy)
    initial = runtime.inspect()
    check("initial_scene_inspected", 3, initial["object_count"])
    check("listener_started", True, blender_ai_mcp.rpc_server.is_listener_healthy())

    backend_python = os.environ["VIBE_BACKEND_PYTHON"]
    repository_root = Path(os.environ["VIBE_REPOSITORY_ROOT"])
    probe = subprocess.run(
        [backend_python, str(repository_root / "tests" / "blender_real" / "backend_probe.py")],
        cwd=repository_root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    check("backend_probe_exit", 0, probe.returncode)
    health = json.loads(probe.stdout.strip().splitlines()[-1])
    check("backend_authenticated", True, health["result"]["authenticated_session"])
    check("health_protocol", PROTOCOL_VERSION, health["result"]["protocol_version"])
    check("health_addon_version", DISPLAY_VERSION, health["result"]["addon_version"])
    check("health_backend_version", DISPLAY_VERSION, health["result"]["backend_version"])
    check("health_queue_operational", True, health["result"]["queue_operational"])
    check("health_scene_gateway_operational", True, health["result"]["scene_gateway_operational"])
    check(
        "health_degraded_features",
        ["storyboards", "audio", "characters", "godot"],
        health["result"]["degraded_features"],
    )
    results["versions"]["backend"] = health["result"]["backend_version"]

    before_creation = runtime.gateway.snapshot_scene()
    creation = runtime.preview_prompt("Create a cube.", scope="SCENE")
    check("creation_preview_status", "PREVIEWED", creation.status)
    check("creation_preview_non_persistent", before_creation, runtime.gateway.snapshot_scene())
    runtime.transactions.apply_pending()
    check("cube_created_by_changeset", len(before_creation) + 1, len(runtime.gateway.snapshot_scene()))
    cube = bpy.context.active_object
    stable_id = inspect_uuid(cube)
    check("cube_uuid_assigned", True, stable_id is not None)
    results["stable_uuid"] = stable_id
    original_uuid = stable_id
    cube.name = "Renamed Vibe Cube"
    check("uuid_survives_rename", original_uuid, inspect_uuid(cube))

    material = bpy.data.materials.new("Vibe Fixture Material")
    cube.data.materials.append(material)
    cube.animation_data_create()
    cube.hide_viewport = False
    cube.hide_render = False
    bpy.context.view_layer.objects.active = cube
    cube.select_set(True)

    before_transform = runtime.gateway.snapshot_scene()
    transform = runtime.preview_prompt("Move the selected object 1 metre upward.", scope="SELECTED")
    check("transform_preview_status", "PREVIEWED", transform.status)
    check("transform_preview_non_persistent", before_transform, runtime.gateway.snapshot_scene())
    applied = runtime.transactions.apply_pending()
    after_transform = runtime.gateway.snapshot_scene()
    check("transform_verification_passed", True, applied.verification["passed"])
    check("requested_location_applied", (0.0, 0.0, 1.0), after_transform[stable_id]["location"])
    for field in ("rotation", "scale", "materials", "animation", "hide_viewport", "hide_render"):
        check(
            f"preserved_{field}",
            before_transform[stable_id][field],
            after_transform[stable_id][field],
        )
    unrelated_ids = set(before_transform) - {stable_id}
    check(
        "unrelated_objects_preserved",
        {item: before_transform[item] for item in unrelated_ids},
        {item: after_transform[item] for item in unrelated_ids},
    )

    before_reject = runtime.gateway.snapshot_scene()
    runtime.preview_prompt("Rotate the selected object 45 degrees around Z.", scope="SELECTED")
    rejected = runtime.transactions.reject()
    check("reject_status", "REJECTED", rejected.status)
    check("reject_scene_unchanged", before_reject, runtime.gateway.snapshot_scene())
    undone = runtime.transactions.undo()
    check("undo_status", "ROLLED_BACK", undone.status)
    check("undo_exact_state", before_transform, runtime.gateway.snapshot_scene())
    redone = runtime.transactions.redo()
    check("redo_status", "APPLIED", redone.status)
    check("redo_exact_state", after_transform, runtime.gateway.snapshot_scene())

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    check("blend_saved", True, blend_path.is_file())
    results["passed"] = all(item["passed"] for item in results["checks"])
finally:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")

print("VIBE_MILESTONE_1_STAGE_1_PASS")
