"""Compact deterministic Blender scene inspection."""

from __future__ import annotations

import json
from typing import Any

from .identities import REVISION_KEY, ensure_uuid, inspect_uuid
from .studio import inspect_material

MAX_CONTEXT_BYTES = 256 * 1024


def _vector(value: Any) -> list[float]:
    return [round(float(item), 6) for item in value]


def inspect_object(obj: Any, active: Any = None, *, assign_missing: bool = False) -> dict[str, Any]:
    stable_id = ensure_uuid(obj) if assign_missing else inspect_uuid(obj)
    parent_id = inspect_uuid(obj.parent) if getattr(obj, "parent", None) else None
    materials = [slot.material.name for slot in getattr(obj, "material_slots", []) if slot.material]
    return {
        "stable_uuid": stable_id,
        "name": obj.name,
        "type": obj.type,
        "collections": sorted(collection.name for collection in getattr(obj, "users_collection", [])),
        "parent_uuid": parent_id,
        "location": _vector(obj.location),
        "rotation": _vector(obj.rotation_euler),
        "scale": _vector(obj.scale),
        "dimensions": _vector(obj.dimensions),
        "viewport_visible": not bool(obj.hide_viewport),
        "render_visible": not bool(obj.hide_render),
        "selected": bool(obj.select_get()),
        "active": obj is active,
        "materials": materials,
        "animation_present": getattr(obj, "animation_data", None) is not None,
        "locked": bool(obj.hide_select or any(obj.lock_location) or any(obj.lock_rotation) or any(obj.lock_scale)),
        "revision": int(obj.get(REVISION_KEY, 0)),
    }


def _inspect_action(obj: Any, *, max_points: int = 64) -> dict[str, Any] | None:
    animation_data = getattr(obj, "animation_data", None)
    action = animation_data.action if animation_data else None
    if action is None:
        return None
    curves: list[dict[str, Any]] = []
    retained = 0
    truncated = False
    for curve in action.fcurves:
        points = []
        for point in curve.keyframe_points:
            if retained >= max_points:
                truncated = True
                break
            points.append(
                {
                    "frame": round(float(point.co[0]), 4),
                    "value": round(float(point.co[1]), 6),
                    "interpolation": point.interpolation,
                    "handle_left_type": point.handle_left_type,
                    "handle_right_type": point.handle_right_type,
                }
            )
            retained += 1
        curves.append({"data_path": curve.data_path, "array_index": curve.array_index, "keyframes": points})
    return {
        "target_uuid": inspect_uuid(obj),
        "action_uuid": inspect_uuid(action),
        "action_name": action.name,
        "frame_range": _vector(action.frame_range),
        "nla_present": bool(animation_data and animation_data.nla_tracks),
        "curves": curves,
        "truncated": truncated,
    }


def _inspect_light(obj: Any) -> dict[str, Any]:
    data = obj.data
    size = data.size if data.type == "AREA" else getattr(data, "shadow_soft_size", 0.0)
    return {
        "uuid": inspect_uuid(obj),
        "data_uuid": inspect_uuid(data),
        "name": obj.name,
        "type": data.type,
        "role": obj.get("vibe_light_role"),
        "energy": round(float(data.energy), 4),
        "color": _vector(data.color),
        "location": _vector(obj.location),
        "rotation": _vector(obj.rotation_euler),
        "size": round(float(size), 4),
        "animation_present": bool(obj.animation_data or data.animation_data),
    }


def _inspect_camera(obj: Any, active: Any) -> dict[str, Any]:
    data = obj.data
    return {
        "uuid": inspect_uuid(obj),
        "data_uuid": inspect_uuid(data),
        "name": obj.name,
        "active": obj is active,
        "lens": round(float(data.lens), 4),
        "sensor_width": round(float(data.sensor_width), 4),
        "clip_start": round(float(data.clip_start), 6),
        "clip_end": round(float(data.clip_end), 4),
        "depth_of_field": bool(data.dof.use_dof),
        "focus_target": inspect_uuid(data.dof.focus_object) if data.dof.focus_object else None,
        "location": _vector(obj.location),
        "rotation": _vector(obj.rotation_euler),
        "animation_present": bool(obj.animation_data or data.animation_data),
    }


def inspect_scene(bpy_module: Any, *, assign_missing: bool = False) -> dict[str, Any]:
    scene = bpy_module.context.scene
    scene_id = ensure_uuid(scene) if assign_missing else inspect_uuid(scene)
    active = bpy_module.context.view_layer.objects.active
    objects = [inspect_object(obj, active, assign_missing=assign_missing) for obj in scene.objects]
    materials = []
    for material in bpy_module.data.materials:
        if material.use_nodes:
            try:
                materials.append(inspect_material(material))
            except ValueError:
                materials.append(
                    {
                        "stable_uuid": inspect_uuid(material),
                        "name": material.name,
                        "users": material.users,
                        "shader_type": "unsupported",
                    }
                )
    lights = [_inspect_light(obj) for obj in scene.objects if obj.type == "LIGHT"]
    cameras = [_inspect_camera(obj, scene.camera) for obj in scene.objects if obj.type == "CAMERA"]
    animations = [animation for obj in scene.objects if (animation := _inspect_action(obj)) is not None]
    result = {
        "scene_uuid": scene_id,
        "scene_name": scene.name,
        "object_count": len(scene.objects),
        "collection_count": len(scene.collection.children) + 1,
        "active_object": inspect_uuid(active) if active else None,
        "active_camera": inspect_uuid(scene.camera) if scene.camera else None,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "fps": scene.render.fps / scene.render.fps_base,
        "render_engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
        "filepath": bpy_module.data.filepath,
        "unsaved": not bool(bpy_module.data.filepath) or bool(getattr(bpy_module.data, "is_dirty", False)),
        "objects": objects,
        "materials": materials,
        "lights": lights,
        "cameras": cameras,
        "animations": animations,
        "render": {
            "engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
            "fps": scene.render.fps / scene.render.fps_base,
            "frame_range": [scene.frame_start, scene.frame_end, scene.frame_step],
            "output_path": scene.render.filepath,
            "image_format": scene.render.image_settings.file_format,
            "color_management": scene.view_settings.look,
            "device": getattr(scene.cycles, "device", None) if hasattr(scene, "cycles") else None,
        },
        "truncated": False,
    }
    for section in ("animations", "objects", "materials", "lights", "cameras"):
        while len(json.dumps(result, separators=(",", ":")).encode("utf-8")) > MAX_CONTEXT_BYTES and result[section]:
            result[section].pop()
            result["truncated"] = True
    return result
