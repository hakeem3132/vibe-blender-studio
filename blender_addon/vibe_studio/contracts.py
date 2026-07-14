"""Strict, dependency-free ChangeSet contracts shared by Blender runtime code."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

SCHEMA_VERSION = "1.0"
MAX_OPERATIONS = 16
ALLOWED_TOOLS = {
    "object.create",
    "object.transform",
    "object.visibility",
    "material.create",
    "material.assign",
    "material.duplicate",
    "material.update",
    "light.create",
    "light.update",
    "camera.create",
    "camera.configure",
    "camera.activate",
    "camera.transform",
    "animation.keyframe_insert",
    "animation.keyframe_update",
    "animation.keyframe_delete",
    "animation.interpolation_update",
    "animation.retime",
    "animation.object_rotate",
    "animation.object_move",
    "animation.camera_push",
    "animation.camera_orbit",
    "render.preview_frame",
    "render.preview_range",
    "render.image_sequence",
    "video.encode",
    "video.validate",
}
ALLOWED_PRESERVE = {
    "location",
    "rotation",
    "scale",
    "visibility",
    "materials",
    "animation",
    "all_unselected_objects",
    "material_graph",
    "material_color",
    "material_properties",
    "lights",
    "camera",
    "camera_animation",
    "object_animation",
    "keyframes_outside_range",
    "scene_duration",
    "first_pose",
    "final_pose",
}
ALLOWED_PRIMITIVES = {"cube", "sphere", "cylinder", "plane", "empty"}
MATERIAL_PRESETS = {
    "matte",
    "glossy",
    "metal",
    "glass",
    "plastic",
    "emissive",
    "product_black",
    "product_white",
}
LIGHT_TYPES = {"POINT", "AREA", "SPOT", "SUN"}
INTERPOLATIONS = {"CONSTANT", "LINEAR", "BEZIER"}
EASINGS = {"linear", "smooth", "ease_in", "ease_out", "ease_in_out", "hold"}
RENDER_PRESETS = {"draft", "preview", "balanced", "high", "custom"}


class ChangeSetError(ValueError):
    """A ChangeSet failed strict validation."""


def _uuid(value: Any, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ChangeSetError(f"{field} must be a valid UUID") from exc


def _vector(value: Any, field: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ChangeSetError(f"{field} must contain exactly three numbers")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ChangeSetError(f"{field} must contain only numbers")
    return (float(value[0]), float(value[1]), float(value[2]))


def _number(value: Any, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ChangeSetError(f"{field} must be numeric")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ChangeSetError(f"{field} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise ChangeSetError(f"{field} must be at most {maximum}")
    return result


def _frame(value: Any, field: str) -> int:
    result = _number(value, field, minimum=1, maximum=10000)
    if not result.is_integer():
        raise ChangeSetError(f"{field} must be an integer frame")
    return int(result)


def _color(value: Any, field: str) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) not in {3, 4}:
        raise ChangeSetError(f"{field} must contain three or four numbers")
    values = tuple(_number(item, field, minimum=0.0, maximum=1.0) for item in value)
    return (values[0], values[1], values[2], values[3] if len(values) == 4 else 1.0)


@dataclass(frozen=True)
class Scope:
    type: Literal["selected_object", "current_scene"]
    target_ids: tuple[str, ...]


@dataclass(frozen=True)
class Operation:
    tool: str
    target_id: str | None
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ChangeSet:
    schema_version: str
    change_set_id: str
    request_id: str
    prompt: str
    intent: str
    scope: Scope
    operations: tuple[Operation, ...]
    preserve: tuple[str, ...]
    verification: tuple[str, ...]
    risk: Literal["low"]

    @classmethod
    def from_dict(cls, value: Any) -> "ChangeSet":
        if not isinstance(value, dict):
            raise ChangeSetError("ChangeSet must be an object")
        expected = {
            "schema_version",
            "change_set_id",
            "request_id",
            "prompt",
            "intent",
            "scope",
            "operations",
            "preserve",
            "verification",
            "risk",
        }
        unknown = set(value) - expected
        missing = expected - set(value)
        if unknown:
            raise ChangeSetError(f"Unknown ChangeSet fields: {', '.join(sorted(unknown))}")
        if missing:
            raise ChangeSetError(f"Missing ChangeSet fields: {', '.join(sorted(missing))}")
        if value["schema_version"] != SCHEMA_VERSION:
            raise ChangeSetError(f"schema_version must be {SCHEMA_VERSION}")
        prompt = value["prompt"]
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 2000:
            raise ChangeSetError("prompt must contain 1 to 2000 characters")
        scope_value = value["scope"]
        if not isinstance(scope_value, dict) or set(scope_value) != {"type", "target_ids"}:
            raise ChangeSetError("scope must contain only type and target_ids")
        if scope_value["type"] not in {"selected_object", "current_scene"}:
            raise ChangeSetError("Unsupported scope type")
        raw_targets = scope_value["target_ids"]
        if not isinstance(raw_targets, list) or len(raw_targets) > MAX_OPERATIONS:
            raise ChangeSetError("scope target_ids must be a bounded list")
        targets = tuple(_uuid(item, "target_id") for item in raw_targets)
        operations_value = value["operations"]
        if not isinstance(operations_value, list) or not 1 <= len(operations_value) <= MAX_OPERATIONS:
            raise ChangeSetError(f"operations must contain 1 to {MAX_OPERATIONS} items")
        operations = tuple(_operation(item) for item in operations_value)
        preserve = value["preserve"]
        if not isinstance(preserve, list) or any(item not in ALLOWED_PRESERVE for item in preserve):
            raise ChangeSetError("preserve contains an unsupported property")
        verification = value["verification"]
        if not isinstance(verification, list) or not all(isinstance(item, str) for item in verification):
            raise ChangeSetError("verification must be a list of check names")
        if value["risk"] != "low":
            raise ChangeSetError("Vibe Studio supports low-risk ChangeSets only")
        return cls(
            schema_version=SCHEMA_VERSION,
            change_set_id=_uuid(value["change_set_id"], "change_set_id"),
            request_id=_uuid(value["request_id"], "request_id"),
            prompt=prompt.strip(),
            intent=str(value["intent"]),
            scope=Scope(scope_value["type"], targets),
            operations=operations,
            preserve=tuple(preserve),
            verification=tuple(verification),
            risk="low",
        )


def _operation(value: Any) -> Operation:
    if not isinstance(value, dict) or set(value) != {"tool", "target_id", "parameters"}:
        raise ChangeSetError("Each operation must contain only tool, target_id and parameters")
    tool = value["tool"]
    if tool not in ALLOWED_TOOLS:
        raise ChangeSetError(f"Tool is not allowlisted: {tool}")
    target_id = None if value["target_id"] is None else _uuid(value["target_id"], "target_id")
    parameters = value["parameters"]
    if not isinstance(parameters, dict):
        raise ChangeSetError("operation parameters must be an object")
    allowed: set[str]
    if tool == "object.create":
        allowed = {"primitive", "location"}
        if target_id is not None:
            raise ChangeSetError("object.create target_id must be null")
        if parameters.get("primitive") not in ALLOWED_PRIMITIVES:
            raise ChangeSetError("Unsupported primitive")
        if "location" in parameters:
            _vector(parameters["location"], "location")
    elif tool == "object.transform":
        allowed = {"location", "location_delta", "rotation", "rotation_delta", "scale", "scale_factor"}
        if target_id is None:
            raise ChangeSetError("object.transform requires target_id")
        if not parameters:
            raise ChangeSetError("object.transform requires parameters")
        for name in {"location", "location_delta", "rotation", "rotation_delta", "scale"} & set(parameters):
            _vector(parameters[name], name)
        if "scale_factor" in parameters and (
            isinstance(parameters["scale_factor"], bool) or not isinstance(parameters["scale_factor"], (int, float))
        ):
            raise ChangeSetError("scale_factor must be numeric")
    elif tool == "object.visibility":
        allowed = {"viewport_visible", "render_visible"}
        if target_id is None:
            raise ChangeSetError("object.visibility requires target_id")
        if not parameters or any(not isinstance(item, bool) for item in parameters.values()):
            raise ChangeSetError("visibility values must be booleans")
    elif tool == "material.create":
        allowed = {"name", "preset", "properties"}
        if target_id is not None:
            raise ChangeSetError("material.create target_id must be null")
        if parameters.get("preset") not in MATERIAL_PRESETS:
            raise ChangeSetError("Unsupported material preset")
        if "name" in parameters and (not isinstance(parameters["name"], str) or not parameters["name"].strip()):
            raise ChangeSetError("Material name must be non-empty")
        _validate_material_properties(parameters.get("properties", {}))
    elif tool == "material.assign":
        allowed = {"material_id", "slot"}
        if target_id is None:
            raise ChangeSetError("material.assign requires an object target_id")
        _uuid(parameters.get("material_id"), "material_id")
        if "slot" in parameters:
            _number(parameters["slot"], "slot", minimum=0, maximum=64)
    elif tool == "material.duplicate":
        allowed = {"name"}
        if target_id is None:
            raise ChangeSetError("material.duplicate requires a material target_id")
        if "name" in parameters and (not isinstance(parameters["name"], str) or not parameters["name"].strip()):
            raise ChangeSetError("Duplicated material name must be non-empty")
    elif tool == "material.update":
        allowed = {
            "base_color",
            "metallic",
            "roughness",
            "specular_ior_level",
            "transmission",
            "alpha",
            "emission_color",
            "emission_strength",
        }
        if target_id is None or not parameters:
            raise ChangeSetError("material.update requires a material target and properties")
        _validate_material_properties(parameters)
    elif tool == "light.create":
        allowed = {"name", "type", "role", "energy", "color", "location", "rotation", "size"}
        if target_id is not None or parameters.get("type") not in LIGHT_TYPES:
            raise ChangeSetError("light.create requires a supported type and no target_id")
        _validate_light_parameters(parameters)
    elif tool == "light.update":
        allowed = {"energy", "color", "location", "rotation", "size"}
        if target_id is None or not parameters:
            raise ChangeSetError("light.update requires a light target and properties")
        _validate_light_parameters(parameters)
    elif tool == "camera.create":
        allowed = {"name", "preset", "target_id", "location", "lens"}
        if target_id is not None:
            raise ChangeSetError("camera.create target_id must be null")
        if "target_id" in parameters:
            _uuid(parameters["target_id"], "camera target_id")
        if "location" in parameters:
            _vector(parameters["location"], "location")
        if "lens" in parameters:
            _number(parameters["lens"], "lens", minimum=1, maximum=500)
    elif tool in {"camera.configure", "camera.transform"}:
        allowed = {
            "location",
            "rotation",
            "lens",
            "clip_start",
            "clip_end",
            "dof",
            "focus_target_id",
        }
        if target_id is None or not parameters:
            raise ChangeSetError(f"{tool} requires a camera target and properties")
        for field in {"location", "rotation"} & set(parameters):
            _vector(parameters[field], field)
        for field in {"lens", "clip_start", "clip_end"} & set(parameters):
            _number(parameters[field], field, minimum=0.001, maximum=100000)
        if "dof" in parameters and not isinstance(parameters["dof"], bool):
            raise ChangeSetError("dof must be boolean")
        if "focus_target_id" in parameters:
            _uuid(parameters["focus_target_id"], "focus_target_id")
    elif tool == "camera.activate":
        allowed = set()
        if target_id is None or parameters:
            raise ChangeSetError("camera.activate requires only a target_id")
    elif tool.startswith("animation."):
        allowed = _validate_animation_operation(tool, target_id, parameters)
    elif tool.startswith("render."):
        allowed = _validate_render_operation(tool, target_id, parameters)
    elif tool == "video.encode":
        allowed = {"frames_dir", "output_path", "fps", "codec", "overwrite"}
        if target_id is not None:
            raise ChangeSetError("video.encode target_id must be null")
        for field in ("frames_dir", "output_path"):
            if not isinstance(parameters.get(field), str) or not parameters[field]:
                raise ChangeSetError(f"{field} is required")
        _number(parameters.get("fps"), "fps", minimum=1, maximum=240)
        if parameters.get("codec", "libx264") not in {"libx264", "h264"}:
            raise ChangeSetError("Unsupported Milestone 2 video codec")
        if "overwrite" in parameters and not isinstance(parameters["overwrite"], bool):
            raise ChangeSetError("overwrite must be boolean")
    else:
        allowed = {"video_path"}
        if target_id is not None or not isinstance(parameters.get("video_path"), str):
            raise ChangeSetError("video.validate requires video_path and no target_id")
    unknown = set(parameters) - allowed
    if unknown:
        raise ChangeSetError(f"Unsupported parameters for {tool}: {', '.join(sorted(unknown))}")
    return Operation(tool=tool, target_id=target_id, parameters=dict(parameters))


def _validate_material_properties(parameters: Any) -> None:
    if not isinstance(parameters, dict):
        raise ChangeSetError("material properties must be an object")
    scalar_fields = {
        "metallic",
        "roughness",
        "specular_ior_level",
        "transmission",
        "alpha",
        "emission_strength",
    }
    for field in scalar_fields & set(parameters):
        maximum = 1000.0 if field == "emission_strength" else 1.0
        _number(parameters[field], field, minimum=0.0, maximum=maximum)
    for field in {"base_color", "emission_color"} & set(parameters):
        _color(parameters[field], field)


def _validate_light_parameters(parameters: dict[str, Any]) -> None:
    for field in {"location", "rotation"} & set(parameters):
        _vector(parameters[field], field)
    if "energy" in parameters:
        _number(parameters["energy"], "energy", minimum=0, maximum=1000000)
    if "size" in parameters:
        _number(parameters["size"], "size", minimum=0.001, maximum=10000)
    if "color" in parameters:
        _color(parameters["color"], "color")
    for field in {"name", "role"} & set(parameters):
        if not isinstance(parameters[field], str) or not parameters[field].strip():
            raise ChangeSetError(f"{field} must be non-empty")


def _validate_animation_operation(tool: str, target_id: str | None, parameters: dict[str, Any]) -> set[str]:
    if target_id is None:
        raise ChangeSetError(f"{tool} requires a target_id")
    common = {
        "property",
        "owner_type",
        "frame",
        "frame_start",
        "frame_end",
        "value",
        "array_index",
        "interpolation",
        "easing",
    }
    macro = {
        "degrees",
        "from_location",
        "to_location",
        "distance",
        "target_id",
        "radius",
        "start_angle",
        "end_angle",
        "height",
        "factor",
        "preserve_duration",
    }
    allowed = common | macro
    for field in {"frame", "frame_start", "frame_end"} & set(parameters):
        _frame(parameters[field], field)
    if (
        "frame_start" in parameters
        and "frame_end" in parameters
        and parameters["frame_end"] < parameters["frame_start"]
    ):
        raise ChangeSetError("frame_end must be greater than or equal to frame_start")
    if "property" in parameters and parameters["property"] not in {
        "location",
        "rotation_euler",
        "scale",
        "energy",
        "roughness",
        "emission_strength",
    }:
        raise ChangeSetError("Unsupported animated property")
    if "owner_type" in parameters and parameters["owner_type"] not in {"object", "material", "light"}:
        raise ChangeSetError("owner_type must be object, material or light")
    if parameters.get("owner_type") == "material" and parameters.get("property") not in {
        "roughness",
        "emission_strength",
    }:
        raise ChangeSetError("Material keyframes support roughness and emission_strength")
    if parameters.get("owner_type") == "light" and parameters.get("property") != "energy":
        raise ChangeSetError("Light keyframes support energy")
    if "interpolation" in parameters and parameters["interpolation"] not in INTERPOLATIONS:
        raise ChangeSetError("Unsupported interpolation")
    if "easing" in parameters and parameters["easing"] not in EASINGS:
        raise ChangeSetError("Unsupported easing")
    for field in {"from_location", "to_location"} & set(parameters):
        _vector(parameters[field], field)
    for field in {"degrees", "distance", "radius", "start_angle", "end_angle", "height", "factor"} & set(parameters):
        _number(parameters[field], field, minimum=0.0, maximum=100000.0)
    if "target_id" in parameters:
        _uuid(parameters["target_id"], "animation target_id")
    if "preserve_duration" in parameters and not isinstance(parameters["preserve_duration"], bool):
        raise ChangeSetError("preserve_duration must be boolean")
    required_by_tool = {
        "animation.keyframe_insert": {"property", "frame", "value"},
        "animation.keyframe_update": {"property", "frame", "value"},
        "animation.keyframe_delete": {"property", "frame"},
        "animation.object_rotate": {"frame_start", "frame_end", "degrees"},
        "animation.object_move": {"frame_start", "frame_end", "from_location", "to_location"},
        "animation.camera_push": {"frame_start", "frame_end", "distance", "target_id"},
        "animation.camera_orbit": {
            "frame_start",
            "frame_end",
            "radius",
            "start_angle",
            "end_angle",
            "height",
            "target_id",
        },
        "animation.retime": {"property", "frame_start", "frame_end", "factor"},
        "animation.interpolation_update": {"property", "frame_start", "frame_end", "interpolation"},
    }
    required = required_by_tool.get(tool, {"property", "frame"})
    missing = required - set(parameters)
    if missing:
        raise ChangeSetError(f"Missing parameters for {tool}: {', '.join(sorted(missing))}")
    return allowed


def _validate_render_operation(tool: str, target_id: str | None, parameters: dict[str, Any]) -> set[str]:
    if target_id is not None:
        raise ChangeSetError(f"{tool} target_id must be null")
    allowed = {
        "frame",
        "frame_start",
        "frame_end",
        "frame_step",
        "preset",
        "output_dir",
        "resolution_x",
        "resolution_y",
        "resolution_percentage",
    }
    for field in {"frame", "frame_start", "frame_end", "frame_step"} & set(parameters):
        _frame(parameters[field], field)
    if "preset" in parameters and parameters["preset"] not in RENDER_PRESETS:
        raise ChangeSetError("Unsupported render preset")
    if "output_dir" in parameters and (not isinstance(parameters["output_dir"], str) or not parameters["output_dir"]):
        raise ChangeSetError("output_dir must be non-empty")
    for field in {"resolution_x", "resolution_y"} & set(parameters):
        _number(parameters[field], field, minimum=16, maximum=8192)
    if "resolution_percentage" in parameters:
        _number(parameters["resolution_percentage"], "resolution_percentage", minimum=1, maximum=100)
    required = {"frame"} if tool == "render.preview_frame" else {"frame_start", "frame_end", "output_dir"}
    missing = required - set(parameters)
    if missing:
        raise ChangeSetError(f"Missing parameters for {tool}: {', '.join(sorted(missing))}")
    return allowed
