"""Real Blender 4.2 Milestone 2 product-animation acceptance workflow."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bpy


def arguments() -> tuple[Path, Path, Path, Path]:
    separator = sys.argv.index("--")
    values = [Path(item) for item in sys.argv[separator + 1 : separator + 5]]
    return values[0], values[1], values[2], values[3]


class RecordingLayout:
    def __init__(self, actions: list[Any], icons: list[str]):
        self.actions = actions
        self.icons = icons
        self.enabled = True

    def box(self):
        return RecordingLayout(self.actions, self.icons)

    def row(self, **_kwargs):
        return RecordingLayout(self.actions, self.icons)

    def label(self, **kwargs):
        if kwargs.get("icon"):
            self.icons.append(kwargs["icon"])

    def prop(self, owner, property_name, **_kwargs):
        getattr(owner, property_name)

    def operator(self, identifier, **kwargs):
        if identifier != "vibe.action":
            raise AssertionError(f"Unexpected operator: {identifier}")
        if kwargs.get("icon") and kwargs["icon"] != "NONE":
            self.icons.append(kwargs["icon"])
        result = SimpleNamespace(action="", enabled=self.enabled)
        self.actions.append(result)
        return result


def serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serializable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


zip_path, blend_path, results_path, diagnostics_path = arguments()
root = Path(os.environ["VIBE_REPOSITORY_ROOT"])
results: dict[str, Any] = {
    "passed": False,
    "checks": [],
    "versions": {"blender": bpy.app.version_string, "python": sys.version.split()[0]},
    "artifacts": {
        "blend": str(blend_path),
        "results": str(results_path),
        "diagnostics": str(diagnostics_path),
    },
    "timings_seconds": {},
}


def check(name: str, expected: Any, actual: Any, passed: bool | None = None) -> None:
    outcome = expected == actual if passed is None else passed
    results["checks"].append(
        {"name": name, "passed": bool(outcome), "expected": serializable(expected), "actual": serializable(actual)}
    )
    if not outcome:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")


def payload(prompt: str, tool: str, target: str | None, parameters: dict[str, Any], preserve: list[str]):
    from blender_ai_mcp.vibe_studio.contracts import ChangeSet

    return ChangeSet.from_dict(
        {
            "schema_version": "1.0",
            "change_set_id": str(uuid.uuid4()),
            "request_id": str(uuid.uuid4()),
            "prompt": prompt,
            "intent": tool,
            "scope": {
                "type": "selected_object" if target else "current_scene",
                "target_ids": [target] if target else [],
            },
            "operations": [{"tool": tool, "target_id": target, "parameters": parameters}],
            "preserve": preserve,
            "verification": ["requested_state_applied", "preserved_state_unchanged"],
            "risk": "low",
        }
    )


try:
    started = time.time()
    check("packaged_addon_installed", {"FINISHED"}, bpy.ops.preferences.addon_install(filepath=str(zip_path)))
    check("packaged_addon_enabled", {"FINISHED"}, bpy.ops.preferences.addon_enable(module="blender_ai_mcp"))
    from blender_ai_mcp.infrastructure.rpc_security import PROTOCOL_VERSION
    from blender_ai_mcp.version import DISPLAY_VERSION
    from blender_ai_mcp.vibe_studio import ui
    from blender_ai_mcp.vibe_studio.ffmpeg_adapter import FFmpegAdapter
    from blender_ai_mcp.vibe_studio.gateway import tracked_values_equal
    from blender_ai_mcp.vibe_studio.identities import ensure_uuid, inspect_uuid
    from blender_ai_mcp.vibe_studio.media_contracts import validate_frame_sequence
    from blender_ai_mcp.vibe_studio.render_pipeline import BlenderRenderPipeline
    from blender_ai_mcp.vibe_studio.runtime import VibeRuntime

    results["versions"].update({"addon": DISPLAY_VERSION, "protocol": PROTOCOL_VERSION})
    check(
        "background_monitor_operator_registered",
        ui.VIBE_OT_RenderMonitor,
        bpy.types.Operator.bl_rna_get_subclass_py("VIBE_OT_render_monitor"),
    )
    for panel in (
        ui.VIBE_PT_Studio,
        ui.VIBE_PT_Create,
        ui.VIBE_PT_Animate,
        ui.VIBE_PT_Camera,
        ui.VIBE_PT_Lighting,
        ui.VIBE_PT_Materials,
        ui.VIBE_PT_Render,
        ui.VIBE_PT_History,
        ui.VIBE_PT_Diagnostics,
    ):
        check(f"panel_registered_{panel.bl_idname}", panel, bpy.types.Panel.bl_rna_get_subclass_py(panel.bl_idname))
        actions: list[Any] = []
        icons: list[str] = []
        fake_panel = SimpleNamespace(layout=RecordingLayout(actions, icons))
        panel.draw(fake_panel, bpy.context)
        check(f"panel_draw_{panel.bl_idname}", True, True)
    mapped: set[str] = set()
    all_icons: list[str] = []
    for panel in (
        ui.VIBE_PT_Studio,
        ui.VIBE_PT_Create,
        ui.VIBE_PT_Animate,
        ui.VIBE_PT_Camera,
        ui.VIBE_PT_Lighting,
        ui.VIBE_PT_Materials,
        ui.VIBE_PT_Render,
        ui.VIBE_PT_History,
        ui.VIBE_PT_Diagnostics,
    ):
        actions = []
        panel.draw(SimpleNamespace(layout=RecordingLayout(actions, all_icons)), bpy.context)
        mapped.update(action.action for action in actions)
    check("all_enabled_controls_mapped", ui.ALL_ACTIONS, mapped)
    valid_icons = {
        item.identifier for item in bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
    }
    check("ui_icons_valid", True, all(icon in valid_icons for icon in all_icons))
    state = bpy.context.scene.vibe_studio
    state.render_progress = 0.5
    check("render_progress_property", 0.5, state.render_progress)
    render_actions: list[Any] = []
    ui.VIBE_PT_Render.draw(
        SimpleNamespace(layout=RecordingLayout(render_actions, [])),
        bpy.context,
    )
    render_video_control = next(action for action in render_actions if action.action == "RENDER_VIDEO")
    cancel_control = next(action for action in render_actions if action.action == "CANCEL")
    check("render_disabled_without_saved_project", False, render_video_control.enabled)
    check("cancel_control_available", True, cancel_control.enabled)

    backend = subprocess.run(
        [os.environ["VIBE_BACKEND_PYTHON"], str(root / "tests" / "blender_real" / "backend_probe.py")],
        cwd=root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    check("backend_probe_exit", 0, backend.returncode)
    health = json.loads(backend.stdout.strip().splitlines()[-1])
    check("backend_authenticated", True, health["result"]["authenticated_session"])
    results["versions"]["backend"] = health["result"]["backend_version"]

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)
    runtime = VibeRuntime(bpy)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 144
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.world.color = (0.008, 0.008, 0.012)

    runtime.preview_prompt("Create a cylinder.", scope="SCENE")
    runtime.transactions.apply_pending()
    product = bpy.context.active_object
    product.name = "Vibe Product Cylinder"
    product_id = ensure_uuid(product)
    runtime.studio.execute(
        payload(
            "Place the product above the floor",
            "object.transform",
            product_id,
            {"location": [0.0, 0.0, 1.1], "scale": [1.0, 1.0, 1.8]},
            ["rotation", "all_unselected_objects"],
        )
    )
    runtime.preview_prompt("Create a plane.", scope="SCENE")
    runtime.transactions.apply_pending()
    floor = bpy.context.active_object
    floor.name = "Vibe Product Floor"
    floor_id = ensure_uuid(floor)
    runtime.studio.execute(
        payload(
            "Scale the product floor",
            "object.transform",
            floor_id,
            {"scale": [5.0, 5.0, 5.0]},
            ["location", "rotation", "all_unselected_objects"],
        )
    )
    check("typed_primitives_created", {"MESH"}, {product.type, floor.type})

    bpy.context.view_layer.objects.active = product
    product.select_set(True)
    material_id = runtime.create_and_assign_material(product_id, "product_black")
    check("material_assigned", material_id, inspect_uuid(product.active_material))
    material_ids_before_duplicate = {
        inspect_uuid(material) for material in bpy.data.materials if inspect_uuid(material)
    }
    duplicate_material = payload(
        "Duplicate the selected managed material",
        "material.duplicate",
        material_id,
        {"name": "Glossy Product Copy"},
        ["all_unselected_objects"],
    )
    duplicate_preview = runtime.studio.preview(duplicate_material)
    check("material_duplicate_previewed", "PREVIEWED", duplicate_preview.status)
    check(
        "material_duplicate_preview_nonpersistent",
        material_ids_before_duplicate,
        {inspect_uuid(material) for material in bpy.data.materials if inspect_uuid(material)},
    )
    runtime.studio.apply_pending()
    material_ids_after_duplicate = {inspect_uuid(material) for material in bpy.data.materials if inspect_uuid(material)}
    duplicate_ids = material_ids_after_duplicate - material_ids_before_duplicate
    check("material_duplicate_created", 1, len(duplicate_ids))
    check("material_duplicate_uuid_is_unique", False, material_id in duplicate_ids)
    bpy.context.view_layer.objects.active = floor
    floor_material_id = runtime.create_and_assign_material(floor_id, "product_white")
    check("floor_material_assigned", floor_material_id, inspect_uuid(floor.active_material))

    bpy.context.view_layer.objects.active = product
    light_ids = runtime.create_studio_lighting(product_id)
    check("three_point_lights_created", 3, len(light_ids))
    check(
        "semantic_light_roles",
        {"key", "fill", "rim"},
        {obj.get("vibe_light_role") for obj in scene.objects if obj.type == "LIGHT"},
    )

    material_before = runtime.studio.gateway.snapshot_scene()
    material_edit = payload(
        "Reduce only roughness to 0.2",
        "material.update",
        material_id,
        {"roughness": 0.2},
        ["material_color", "material_graph", "material_properties", "all_unselected_objects"],
    )
    material_preview = runtime.studio.preview(material_edit)
    check("material_edit_previewed", "PREVIEWED", material_preview.status)
    check(
        "material_preview_nonpersistent",
        True,
        tracked_values_equal(material_before, runtime.studio.gateway.snapshot_scene()),
    )
    runtime.studio.apply_pending()
    material_after = runtime.studio.gateway.snapshot_scene()
    actual_roughness = material_after["materials"][material_id]["roughness"]
    check("material_roughness_updated", 0.2, actual_roughness, abs(actual_roughness - 0.2) <= 1e-6)
    check(
        "material_color_preserved",
        material_before["materials"][material_id]["base_color"],
        material_after["materials"][material_id]["base_color"],
    )
    check(
        "material_graph_preserved",
        (
            material_before["materials"][material_id]["node_count"],
            material_before["materials"][material_id]["link_count"],
        ),
        (
            material_after["materials"][material_id]["node_count"],
            material_after["materials"][material_id]["link_count"],
        ),
    )
    runtime.studio.undo()
    check("material_edit_undo", True, tracked_values_equal(material_before, runtime.studio.gateway.snapshot_scene()))
    runtime.studio.redo()
    check("material_edit_redo", True, tracked_values_equal(material_after, runtime.studio.gateway.snapshot_scene()))

    for frame, value in ((1, 0.2), (144, 0.35)):
        runtime.studio.execute(
            payload(
                f"Animate material roughness at frame {frame}",
                "animation.keyframe_insert",
                material_id,
                {"owner_type": "material", "property": "roughness", "frame": frame, "value": value},
                ["material_color", "material_graph", "all_unselected_objects"],
            )
        )
    material_action = product.active_material.node_tree.animation_data.action
    check("material_scalar_animation_created", True, material_action is not None and len(material_action.fcurves) == 1)
    check("material_action_stable_uuid", True, inspect_uuid(material_action) is not None)
    runtime.studio.execute(
        payload(
            "Update the final material roughness key",
            "animation.keyframe_update",
            material_id,
            {"owner_type": "material", "property": "roughness", "frame": 144, "value": 0.4},
            ["material_color", "material_graph", "all_unselected_objects"],
        )
    )
    final_material_key = material_action.fcurves[0].keyframe_points[-1]
    check(
        "material_keyframe_updated",
        0.4,
        float(final_material_key.co[1]),
        abs(float(final_material_key.co[1]) - 0.4) <= 1e-6,
    )
    runtime.studio.execute(
        payload(
            "Delete the final material roughness key",
            "animation.keyframe_delete",
            material_id,
            {"owner_type": "material", "property": "roughness", "frame": 144},
            ["material_color", "material_graph", "all_unselected_objects"],
        )
    )
    check("material_keyframe_deleted", 1, len(material_action.fcurves[0].keyframe_points))
    runtime.studio.execute(
        payload(
            "Restore the final material roughness key",
            "animation.keyframe_insert",
            material_id,
            {"owner_type": "material", "property": "roughness", "frame": 144, "value": 0.35},
            ["material_color", "material_graph", "all_unselected_objects"],
        )
    )
    scene.frame_set(scene.frame_current)

    key_light = next(obj for obj in scene.objects if obj.type == "LIGHT" and obj.get("vibe_light_role") == "key")
    key_light_id = ensure_uuid(key_light)
    light_before = runtime.studio.gateway.snapshot_scene()
    light_edit = payload(
        "Reduce only the key-light energy by 20%",
        "light.update",
        key_light_id,
        {"energy": float(key_light.data.energy) * 0.8},
        ["camera", "materials", "object_animation", "all_unselected_objects"],
    )
    runtime.studio.preview(light_edit)
    check(
        "light_preview_nonpersistent", True, tracked_values_equal(light_before, runtime.studio.gateway.snapshot_scene())
    )
    runtime.studio.apply_pending()
    light_after = runtime.studio.gateway.snapshot_scene()
    expected_key_energy = light_before["lights"][key_light_id]["energy"] * 0.8
    actual_key_energy = light_after["lights"][key_light_id]["energy"]
    check(
        "key_light_energy_updated",
        expected_key_energy,
        actual_key_energy,
        abs(actual_key_energy - expected_key_energy) <= 1e-6,
    )
    check("light_camera_preserved", light_before["cameras"], light_after["cameras"])
    check("light_materials_preserved", light_before["materials"], light_after["materials"])
    runtime.studio.undo()
    check("light_edit_undo", True, tracked_values_equal(light_before, runtime.studio.gateway.snapshot_scene()))
    runtime.studio.redo()
    check("light_edit_redo", True, tracked_values_equal(light_after, runtime.studio.gateway.snapshot_scene()))

    reject_edit = payload(
        "Reject a proposed key-light change",
        "light.update",
        key_light_id,
        {"energy": 100.0},
        ["camera", "materials", "object_animation", "all_unselected_objects"],
    )
    before_reject = runtime.studio.gateway.snapshot_scene()
    runtime.studio.preview(reject_edit)
    rejected = runtime.studio.transactions.reject()
    check("light_change_rejected", "REJECTED", rejected.status)
    check(
        "rejection_scene_unchanged", True, tracked_values_equal(before_reject, runtime.studio.gateway.snapshot_scene())
    )

    for frame, value in ((1, actual_key_energy), (144, 650.0)):
        runtime.studio.execute(
            payload(
                f"Animate key-light energy at frame {frame}",
                "animation.keyframe_insert",
                key_light_id,
                {"owner_type": "light", "property": "energy", "frame": frame, "value": value},
                ["camera", "materials", "all_unselected_objects"],
            )
        )
    check(
        "light_energy_animation_created",
        True,
        key_light.data.animation_data is not None and len(key_light.data.animation_data.action.fcurves) == 1,
    )
    check("light_action_stable_uuid", True, inspect_uuid(key_light.data.animation_data.action) is not None)
    scene.frame_set(scene.frame_current)

    camera_id = runtime.create_hero_camera(product_id)
    check("hero_camera_active", camera_id, inspect_uuid(scene.camera))
    from bpy_extras.object_utils import world_to_camera_view

    bpy.context.view_layer.update()
    projected = world_to_camera_view(scene, scene.camera, product.matrix_world.translation)
    projection = (float(projected.x), float(projected.y), float(projected.z))
    check(
        "camera_target_in_frame",
        "x/y in [0,1], target in front",
        projection,
        0.0 <= projected.x <= 1.0 and 0.0 <= projected.y <= 1.0 and projected.z > 0,
    )
    camera_distance = (scene.camera.matrix_world.translation - product.matrix_world.translation).length
    check("camera_outside_target_bounds", True, camera_distance > max(product.dimensions) / 2.0)

    runtime.animate_rotation(product_id, frame_start=1, frame_end=144)
    rotation_action = runtime.studio.gateway.inspect_animation(product_id)
    check("product_rotation_curves", True, len(rotation_action["action"]["curves"]) >= 1)
    camera_push = payload(
        "Push camera toward the product over six seconds",
        "animation.camera_push",
        camera_id,
        {
            "frame_start": 1,
            "frame_end": 144,
            "distance": 1.2,
            "target_id": product_id,
            "easing": "ease_in_out",
        },
        ["object_animation", "lights", "materials", "scene_duration"],
    )
    camera_preview = runtime.studio.preview(camera_push)
    camera_restored = runtime.studio.gateway.snapshot_scene()
    results["camera_preview_restore"] = {
        "expected": serializable(camera_preview.before_state),
        "actual": serializable(camera_restored),
    }
    check("camera_preview_nonpersistent", True, tracked_values_equal(camera_preview.before_state, camera_restored))
    runtime.studio.apply_pending()
    camera_action = runtime.studio.gateway.inspect_animation(camera_id)
    check("camera_push_curves", True, len(camera_action["action"]["curves"]) >= 1)

    project_root = blend_path.parent.parent.parent
    pipeline = BlenderRenderPipeline(bpy, project_root)
    before_preview_settings = {
        "engine": scene.render.engine,
        "resolution": (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage),
        "filepath": scene.render.filepath,
        "frame": scene.frame_current,
    }
    preview_job = runtime.create_render_job(
        "previews/representative",
        frame_start=72,
        frame_end=72,
        frame_step=1,
        preset="draft",
        resolution_x=320,
        resolution_y=180,
        resolution_percentage=100,
    )
    preview_path = pipeline.preview_frame(preview_job, 72)
    results["artifacts"]["preview"] = str(preview_path)
    check("representative_preview_exists", True, preview_path.is_file() and preview_path.stat().st_size > 0)
    after_preview_settings = {
        "engine": scene.render.engine,
        "resolution": (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage),
        "filepath": scene.render.filepath,
        "frame": scene.frame_current,
    }
    check("preview_settings_restored", before_preview_settings, after_preview_settings)
    range_job = runtime.create_render_job(
        "previews/range",
        frame_start=1,
        frame_end=5,
        frame_step=1,
        preset="draft",
        resolution_x=160,
        resolution_y=90,
        resolution_percentage=100,
    )
    check("preview_range_valid", True, pipeline.render(range_job, preview=True).passed)

    before_edit = runtime.studio.gateway.snapshot_scene()
    edit = payload(
        "Make only the product rotation 20% slower while preserving duration and endpoints",
        "animation.retime",
        product_id,
        {
            "property": "rotation_euler",
            "frame_start": 1,
            "frame_end": 144,
            "factor": 1.2,
            "preserve_duration": True,
        },
        [
            "camera_animation",
            "lights",
            "materials",
            "scene_duration",
            "first_pose",
            "final_pose",
            "all_unselected_objects",
        ],
    )
    preview_edit = runtime.studio.preview(edit)
    check("micro_edit_previewed", "PREVIEWED", preview_edit.status)
    check(
        "micro_edit_preview_nonpersistent",
        True,
        tracked_values_equal(before_edit, runtime.studio.gateway.snapshot_scene()),
    )
    applied_edit = runtime.studio.apply_pending()
    after_edit = runtime.studio.gateway.snapshot_scene()
    check("micro_edit_applied", "APPLIED", applied_edit.status)
    check(
        "product_curve_changed",
        False,
        tracked_values_equal(before_edit["objects"][product_id]["action"], after_edit["objects"][product_id]["action"]),
    )
    check(
        "camera_animation_preserved",
        before_edit["objects"][camera_id]["action"],
        after_edit["objects"][camera_id]["action"],
    )
    check("lights_preserved", before_edit["lights"], after_edit["lights"])
    check("materials_preserved", before_edit["materials"], after_edit["materials"])
    check("duration_preserved", (1, 144), (after_edit["scene"]["frame_start"], after_edit["scene"]["frame_end"]))
    before_curves = before_edit["objects"][product_id]["action"]["curves"]
    after_curves = after_edit["objects"][product_id]["action"]["curves"]
    for index, (before_curve, after_curve) in enumerate(zip(before_curves, after_curves, strict=True)):
        check(f"first_pose_preserved_{index}", before_curve["points"][0]["value"], after_curve["points"][0]["value"])
        check(f"final_pose_preserved_{index}", before_curve["points"][-1]["value"], after_curve["points"][-1]["value"])
    runtime.studio.undo()
    check("micro_edit_undo_exact", True, tracked_values_equal(before_edit, runtime.studio.gateway.snapshot_scene()))
    runtime.studio.redo()
    check("micro_edit_redo_exact", True, tracked_values_equal(after_edit, runtime.studio.gateway.snapshot_scene()))

    render_started = time.time()
    final_job = runtime.create_render_job(
        "frames/product_demo",
        frame_start=1,
        frame_end=144,
        frame_step=1,
        preset="draft",
        resolution_x=320,
        resolution_y=180,
        resolution_percentage=100,
    )
    final_validation = pipeline.render(final_job)
    results["timings_seconds"]["image_sequence"] = round(time.time() - render_started, 3)
    check("image_sequence_valid", True, final_validation.passed)
    check("image_sequence_frame_count", 144, len(final_validation.valid_frames))
    frames_dir = project_root / "outputs" / "frames" / "product_demo"
    results["artifacts"]["frames"] = str(frames_dir)
    check("frame_rescan_valid", True, validate_frame_sequence(frames_dir, final_job.expected_frames).passed)

    adapter = FFmpegAdapter()
    results["versions"].update(adapter.version())
    video_path = Path("videos/product_demo.mp4")
    command = adapter.build_encode_command(
        project_root=project_root,
        frames_directory=Path("frames/product_demo"),
        output_path=video_path,
        fps=24.0,
        overwrite=True,
        start_number=1,
    )
    encode_started = time.time()
    adapter.encode(command)
    results["timings_seconds"]["ffmpeg_encode"] = round(time.time() - encode_started, 3)
    probe = adapter.probe(project_root=project_root, video_path=video_path)
    mp4_path = project_root / "outputs" / video_path
    probe_path = project_root / "outputs" / "diagnostics" / "product_demo_ffprobe.json"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    probe_path.write_text(json.dumps(probe, indent=2), encoding="utf-8")
    results["artifacts"].update({"mp4": str(mp4_path), "ffprobe": str(probe_path)})
    stream = probe["streams"][0]
    check("mp4_codec", "h264", stream["codec_name"])
    check("mp4_dimensions", (320, 180), (stream["width"], stream["height"]))
    duration = float(stream.get("duration") or probe["format"]["duration"])
    check("mp4_duration_seconds", 6.0, duration, abs(duration - 6.0) <= 0.1)
    frame_count = int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0)
    check("mp4_frame_count", 144, frame_count)

    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    check("blend_saved", True, blend_path.is_file())
    results["persistent_ids"] = {
        "product": product_id,
        "floor": floor_id,
        "material": material_id,
        "floor_material": floor_material_id,
        "lights": light_ids,
        "camera": camera_id,
        "product_action": inspect_uuid(product.animation_data.action),
        "camera_action": inspect_uuid(scene.camera.animation_data.action),
    }
    results["timings_seconds"]["stage_one"] = round(time.time() - started, 3)
    results["passed"] = all(item["passed"] for item in results["checks"])
finally:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")

print("VIBE_MILESTONE_2_STAGE_1_PASS")
