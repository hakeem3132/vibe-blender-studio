"""Bounded Blender 4.2 material, light, camera and animation operations."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from .contracts import ChangeSet, Operation, Scope
from .gateway import BlenderSceneGateway, tracked_values_equal
from .identities import REVISION_KEY, UUID_KEY, ensure_uuid, inspect_uuid, lookup_unique
from .transactions import TransactionEngine

MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    "matte": {"base_color": (0.5, 0.5, 0.5, 1.0), "metallic": 0.0, "roughness": 0.75},
    "glossy": {"base_color": (0.04, 0.04, 0.04, 1.0), "metallic": 0.0, "roughness": 0.12},
    "metal": {"base_color": (0.3, 0.32, 0.35, 1.0), "metallic": 1.0, "roughness": 0.24},
    "glass": {
        "base_color": (0.92, 0.97, 1.0, 0.16),
        "metallic": 0.0,
        "roughness": 0.08,
        "transmission": 1.0,
        "alpha": 0.16,
    },
    "plastic": {"base_color": (0.18, 0.18, 0.2, 1.0), "metallic": 0.0, "roughness": 0.3},
    "emissive": {
        "base_color": (0.02, 0.02, 0.02, 1.0),
        "emission_color": (1.0, 0.35, 0.08, 1.0),
        "emission_strength": 4.0,
    },
    "product_black": {"base_color": (0.008, 0.01, 0.015, 1.0), "metallic": 0.08, "roughness": 0.16},
    "product_white": {"base_color": (0.86, 0.86, 0.82, 1.0), "metallic": 0.0, "roughness": 0.22},
}

PRINCIPLED_INPUTS = {
    "base_color": "Base Color",
    "metallic": "Metallic",
    "roughness": "Roughness",
    "specular_ior_level": "IOR Level",
    "transmission": "Transmission Weight",
    "alpha": "Alpha",
    "emission_color": "Emission Color",
    "emission_strength": "Emission Strength",
}


def _vector(value: Any) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def _key(data_block: Any) -> str:
    return inspect_uuid(data_block) or f"name:{data_block.name}"


def _find_by_key(data_blocks: Any, key: str) -> Any | None:
    if key.startswith("name:"):
        return data_blocks.get(key[5:])
    matches = [item for item in data_blocks if inspect_uuid(item) == key]
    return matches[0] if len(matches) == 1 else None


def _principled(material: Any) -> Any:
    if not material.use_nodes or material.node_tree is None:
        raise ValueError("Material has no supported node graph")
    nodes = [node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"]
    if len(nodes) != 1:
        raise ValueError("Material graph must contain exactly one Principled BSDF node for bounded editing")
    return nodes[0]


def inspect_material(material: Any) -> dict[str, Any]:
    node = _principled(material)
    values: dict[str, Any] = {}
    for field, input_name in PRINCIPLED_INPUTS.items():
        socket = node.inputs.get(input_name)
        if socket is None:
            continue
        value = socket.default_value
        values[field] = tuple(float(item) for item in value) if hasattr(value, "__len__") else float(value)
    return {
        "stable_uuid": inspect_uuid(material),
        "name": material.name,
        "users": material.users,
        "shader_type": "Principled BSDF",
        **values,
        "animated_properties": bool(
            material.node_tree and material.node_tree.animation_data and material.node_tree.animation_data.action
        ),
        "node_count": len(material.node_tree.nodes),
        "link_count": len(material.node_tree.links),
    }


def _action_snapshot(owner: Any) -> dict[str, Any] | None:
    animation_data = getattr(owner, "animation_data", None)
    action = animation_data.action if animation_data else None
    if action is None:
        return None
    curves: list[dict[str, Any]] = []
    for curve in action.fcurves:
        if len(curve.modifiers):
            raise ValueError("F-curve modifiers are preserved but not editable in the bounded Milestone 2 workflow")
        points = []
        for point in curve.keyframe_points:
            points.append(
                {
                    "frame": float(point.co[0]),
                    "value": float(point.co[1]),
                    "interpolation": point.interpolation,
                    "easing": point.easing,
                    "handle_left": tuple(float(item) for item in point.handle_left),
                    "handle_right": tuple(float(item) for item in point.handle_right),
                    "handle_left_type": point.handle_left_type,
                    "handle_right_type": point.handle_right_type,
                }
            )
        curves.append(
            {
                "data_path": curve.data_path,
                "array_index": curve.array_index,
                "extrapolation": curve.extrapolation,
                "group": curve.group.name if curve.group else None,
                "points": points,
            }
        )
    return {
        "stable_uuid": ensure_uuid(action),
        "name": action.name,
        "frame_range": tuple(float(item) for item in action.frame_range),
        "curves": curves,
    }


def _restore_action(bpy_module: Any, owner: Any, snapshot: dict[str, Any] | None) -> None:
    animation_data = getattr(owner, "animation_data", None)
    current = animation_data.action if animation_data else None
    if snapshot is None:
        if animation_data is not None:
            animation_data.action = None
        if current is not None and inspect_uuid(current):
            bpy_module.data.actions.remove(current)
        return
    if animation_data is None:
        owner.animation_data_create()
        animation_data = owner.animation_data
    action = _find_by_key(bpy_module.data.actions, snapshot["stable_uuid"])
    if action is None:
        action = bpy_module.data.actions.new(snapshot["name"])
        action[UUID_KEY] = snapshot["stable_uuid"]
        action[REVISION_KEY] = 0
    animation_data.action = action
    while action.fcurves:
        action.fcurves.remove(action.fcurves[0])
    for curve_state in snapshot["curves"]:
        curve = action.fcurves.new(
            data_path=curve_state["data_path"],
            index=int(curve_state["array_index"]),
            action_group=curve_state["group"] or "Vibe Animation",
        )
        curve.extrapolation = curve_state["extrapolation"]
        for point_state in curve_state["points"]:
            point = curve.keyframe_points.insert(point_state["frame"], point_state["value"], options={"FAST"})
            point.interpolation = point_state["interpolation"]
            point.easing = point_state["easing"]
            point.handle_left_type = point_state["handle_left_type"]
            point.handle_right_type = point_state["handle_right_type"]
            point.handle_left = point_state["handle_left"]
            point.handle_right = point_state["handle_right"]
        curve.update()


class StudioGateway:
    """Transaction gateway for the bounded Milestone 2 Blender tools."""

    def __init__(self, bpy_module: Any):
        self.bpy = bpy_module
        self.foundation = BlenderSceneGateway(bpy_module)

    @staticmethod
    def states_equal(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
        return tracked_values_equal(expected, actual)

    def _object(self, stable_id: str) -> Any:
        return lookup_unique(self.bpy.context.scene.objects, stable_id)

    def _material(self, stable_id: str) -> Any:
        return lookup_unique(self.bpy.data.materials, stable_id)

    def validate_targets(self, change_set: ChangeSet) -> None:
        for operation in change_set.operations:
            if operation.target_id is None:
                continue
            owner_type = operation.parameters.get("owner_type")
            if operation.tool.startswith("animation.") and owner_type == "material":
                self._material(operation.target_id)
            elif operation.tool.startswith("material.") and operation.tool != "material.assign":
                self._material(operation.target_id)
            else:
                self._object(operation.target_id)

    def snapshot_scene(self) -> dict[str, Any]:
        objects: dict[str, Any] = {}
        lights: dict[str, Any] = {}
        cameras: dict[str, Any] = {}
        for obj in self.bpy.context.scene.objects:
            key = _key(obj)
            objects[key] = {
                "name": obj.name,
                "type": obj.type,
                "location": tuple(float(item) for item in obj.location),
                "rotation": tuple(float(item) for item in obj.rotation_euler),
                "scale": tuple(float(item) for item in obj.scale),
                "hide_viewport": bool(obj.hide_viewport),
                "hide_render": bool(obj.hide_render),
                "materials": tuple(_key(slot.material) for slot in obj.material_slots if slot.material),
                "action": _action_snapshot(obj),
            }
            if obj.type == "LIGHT":
                lights[key] = {
                    "data_uuid": inspect_uuid(obj.data),
                    "type": obj.data.type,
                    "energy": float(obj.data.energy),
                    "color": tuple(float(item) for item in obj.data.color),
                    "size": float(
                        getattr(obj.data, "shape", "")
                        and getattr(obj.data, "size", 0.25)
                        or getattr(obj.data, "shadow_soft_size", 0.25)
                    ),
                    "role": obj.get("vibe_light_role"),
                    "action": _action_snapshot(obj.data),
                }
            elif obj.type == "CAMERA":
                cameras[key] = {
                    "data_uuid": inspect_uuid(obj.data),
                    "lens": float(obj.data.lens),
                    "sensor_width": float(obj.data.sensor_width),
                    "clip_start": float(obj.data.clip_start),
                    "clip_end": float(obj.data.clip_end),
                    "dof": bool(obj.data.dof.use_dof),
                    "focus_uuid": inspect_uuid(obj.data.dof.focus_object) if obj.data.dof.focus_object else None,
                    "active": obj is self.bpy.context.scene.camera,
                }
        materials = {
            _key(material): {
                **inspect_material(material),
                "action": _action_snapshot(material.node_tree),
            }
            for material in self.bpy.data.materials
            if material.use_nodes
        }
        scene = self.bpy.context.scene
        return {
            "objects": objects,
            "materials": materials,
            "lights": lights,
            "cameras": cameras,
            "scene": {
                "frame_start": int(scene.frame_start),
                "frame_end": int(scene.frame_end),
                "frame_current": int(scene.frame_current),
                "fps": int(scene.render.fps),
                "camera": _key(scene.camera) if scene.camera else None,
            },
        }

    def restore_scene(self, state: dict[str, Any]) -> None:
        for obj in list(self.bpy.context.scene.objects):
            key = _key(obj)
            if key not in state["objects"] and inspect_uuid(obj):
                data = obj.data
                object_type = obj.type
                self.bpy.data.objects.remove(obj, do_unlink=True)
                if data and getattr(data, "users", 0) == 0:
                    collection = {
                        "MESH": self.bpy.data.meshes,
                        "LIGHT": self.bpy.data.lights,
                        "CAMERA": self.bpy.data.cameras,
                    }.get(object_type)
                    if collection is not None:
                        collection.remove(data)
        for material in list(self.bpy.data.materials):
            key = _key(material)
            if key not in state["materials"] and inspect_uuid(material) and material.users == 0:
                self.bpy.data.materials.remove(material)
        for key, object_state in state["objects"].items():
            obj = _find_by_key(self.bpy.context.scene.objects, key)
            if obj is None:
                continue
            obj.location = object_state["location"]
            obj.rotation_euler = object_state["rotation"]
            obj.scale = object_state["scale"]
            obj.hide_viewport = object_state["hide_viewport"]
            obj.hide_render = object_state["hide_render"]
            if hasattr(obj.data, "materials"):
                obj.data.materials.clear()
                for material_key in object_state["materials"]:
                    material = _find_by_key(self.bpy.data.materials, material_key)
                    if material is not None:
                        obj.data.materials.append(material)
            _restore_action(self.bpy, obj, object_state["action"])
        for key, material_state in state["materials"].items():
            material = _find_by_key(self.bpy.data.materials, key)
            if material is not None:
                self._update_material(
                    material, {field: material_state[field] for field in PRINCIPLED_INPUTS if field in material_state}
                )
                _restore_action(self.bpy, material.node_tree, material_state.get("action"))
        for key, light_state in state["lights"].items():
            obj = _find_by_key(self.bpy.context.scene.objects, key)
            if obj is not None:
                obj.data.energy = light_state["energy"]
                obj.data.color = light_state["color"]
                self._set_light_size(obj.data, light_state["size"])
                _restore_action(self.bpy, obj.data, light_state.get("action"))
        for key, camera_state in state["cameras"].items():
            obj = _find_by_key(self.bpy.context.scene.objects, key)
            if obj is not None:
                obj.data.lens = camera_state["lens"]
                obj.data.clip_start = camera_state["clip_start"]
                obj.data.clip_end = camera_state["clip_end"]
                obj.data.dof.use_dof = camera_state["dof"]
        scene_state = state["scene"]
        scene = self.bpy.context.scene
        scene.frame_start = scene_state["frame_start"]
        scene.frame_end = scene_state["frame_end"]
        if scene.frame_current != scene_state["frame_current"]:
            scene.frame_set(scene_state["frame_current"])
        scene.render.fps = scene_state["fps"]
        scene.camera = _find_by_key(scene.objects, scene_state["camera"]) if scene_state["camera"] else None

    def apply(self, change_set: ChangeSet) -> None:
        for operation in change_set.operations:
            self._apply_operation(operation)

    def _apply_operation(self, operation: Operation) -> None:
        tool = operation.tool
        parameters = operation.parameters
        if tool.startswith("object."):
            self.foundation.apply(
                ChangeSet(
                    schema_version="1.0",
                    change_set_id=str(uuid.uuid4()),
                    request_id=str(uuid.uuid4()),
                    prompt="Validated Milestone 2 object operation",
                    intent=tool,
                    scope=Scope("current_scene", ()),
                    operations=(operation,),
                    preserve=(),
                    verification=(),
                    risk="low",
                )
            )
        elif tool == "material.create":
            self._create_material(parameters)
        elif tool == "material.assign":
            self._assign_material(operation.target_id, parameters)
        elif tool == "material.duplicate":
            self._duplicate_material(self._material(str(operation.target_id)), parameters)
        elif tool == "material.update":
            self._update_material(self._material(str(operation.target_id)), parameters)
        elif tool == "light.create":
            self._create_light(parameters)
        elif tool == "light.update":
            self._update_light(self._object(str(operation.target_id)), parameters)
        elif tool == "camera.create":
            self._create_camera(parameters)
        elif tool in {"camera.configure", "camera.transform"}:
            self._configure_camera(self._object(str(operation.target_id)), parameters)
        elif tool == "camera.activate":
            self.bpy.context.scene.camera = self._object(str(operation.target_id))
        elif tool.startswith("animation."):
            self._apply_animation(operation)
        else:
            raise ValueError(f"{tool} is a job operation and cannot mutate Blender scene state directly")

    def _create_material(self, parameters: dict[str, Any]) -> Any:
        material = self.bpy.data.materials.new(parameters.get("name", "Vibe Material"))
        material.use_nodes = True
        ensure_uuid(material)
        values = dict(MATERIAL_PRESETS[parameters["preset"]])
        values.update(parameters.get("properties", {}))
        self._update_material(material, values)
        material["vibe_material_preset"] = parameters["preset"]
        return material

    @staticmethod
    def _update_material(material: Any, parameters: dict[str, Any]) -> None:
        node = _principled(material)
        for field, value in parameters.items():
            socket_name = PRINCIPLED_INPUTS[field]
            socket = node.inputs.get(socket_name)
            if socket is None:
                raise ValueError(f"Blender 4.2 Principled input is unavailable: {socket_name}")
            socket.default_value = value

    def _assign_material(self, object_id: str | None, parameters: dict[str, Any]) -> None:
        obj = self._object(str(object_id))
        if not hasattr(obj.data, "materials"):
            raise ValueError("Selected object does not support material assignment")
        material = self._material(parameters["material_id"])
        slot = int(parameters.get("slot", 0))
        while len(obj.data.materials) <= slot:
            obj.data.materials.append(material)
        obj.data.materials[slot] = material

    @staticmethod
    def _duplicate_material(material: Any, parameters: dict[str, Any]) -> Any:
        duplicate = material.copy()
        duplicate.name = parameters.get("name", f"{material.name} Copy")
        if UUID_KEY in duplicate:
            del duplicate[UUID_KEY]
        if REVISION_KEY in duplicate:
            del duplicate[REVISION_KEY]
        ensure_uuid(duplicate)
        duplicate["vibe_duplicated_from"] = inspect_uuid(material)
        return duplicate

    def _create_light(self, parameters: dict[str, Any]) -> Any:
        data = self.bpy.data.lights.new(parameters.get("name", "Vibe Light"), type=parameters["type"])
        obj = self.bpy.data.objects.new(parameters.get("name", "Vibe Light"), data)
        self.bpy.context.scene.collection.objects.link(obj)
        ensure_uuid(data)
        ensure_uuid(obj)
        obj["vibe_light_role"] = parameters.get("role", "custom")
        self._update_light(obj, parameters)
        return obj

    @staticmethod
    def _set_light_size(data: Any, value: float) -> None:
        if data.type == "AREA":
            data.size = value
        elif hasattr(data, "shadow_soft_size"):
            data.shadow_soft_size = value

    def _update_light(self, obj: Any, parameters: dict[str, Any]) -> None:
        if obj.type != "LIGHT":
            raise ValueError("Target is not a light")
        if "energy" in parameters:
            obj.data.energy = float(parameters["energy"])
        if "color" in parameters:
            obj.data.color = tuple(parameters["color"][:3])
        if "size" in parameters:
            self._set_light_size(obj.data, float(parameters["size"]))
        if "location" in parameters:
            obj.location = _vector(parameters["location"])
        if "rotation" in parameters:
            obj.rotation_euler = _vector(parameters["rotation"])

    def _create_camera(self, parameters: dict[str, Any]) -> Any:
        data = self.bpy.data.cameras.new(parameters.get("name", "Vibe Camera"))
        obj = self.bpy.data.objects.new(parameters.get("name", "Vibe Camera"), data)
        self.bpy.context.scene.collection.objects.link(obj)
        ensure_uuid(data)
        ensure_uuid(obj)
        obj.location = _vector(parameters.get("location", (5.5, -7.0, 4.2)))
        data.lens = float(parameters.get("lens", 70.0))
        data.clip_start = 0.05
        data.clip_end = 1000.0
        target_id = parameters.get("target_id")
        if target_id:
            self._aim_camera(obj, self._object(target_id))
            obj["vibe_camera_target"] = target_id
        return obj

    def _configure_camera(self, obj: Any, parameters: dict[str, Any]) -> None:
        if obj.type != "CAMERA":
            raise ValueError("Target is not a camera")
        if "location" in parameters:
            obj.location = _vector(parameters["location"])
        if "rotation" in parameters:
            obj.rotation_euler = _vector(parameters["rotation"])
        if "lens" in parameters:
            obj.data.lens = float(parameters["lens"])
        if "clip_start" in parameters:
            obj.data.clip_start = float(parameters["clip_start"])
        if "clip_end" in parameters:
            obj.data.clip_end = float(parameters["clip_end"])
        if obj.data.clip_end <= obj.data.clip_start:
            raise ValueError("Camera clip end must be greater than clip start")
        if "dof" in parameters:
            obj.data.dof.use_dof = parameters["dof"]
        if "focus_target_id" in parameters:
            target = self._object(parameters["focus_target_id"])
            obj.data.dof.focus_object = target
            self._aim_camera(obj, target)

    def _aim_camera(self, camera: Any, target: Any) -> None:
        camera.update_tag()
        target.update_tag()
        self.bpy.context.view_layer.update()
        direction = target.matrix_world.translation - camera.matrix_world.translation
        if direction.length == 0:
            raise ValueError("Camera cannot occupy the target position")
        camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    def _action(self, owner: Any, name: str) -> Any:
        owner.animation_data_create()
        action = owner.animation_data.action
        if action is None:
            action = self.bpy.data.actions.new(name)
            owner.animation_data.action = action
        ensure_uuid(action)
        return action

    @staticmethod
    def _set_interpolation(owner: Any, data_path: str, start: int, end: int, interpolation: str, easing: str) -> None:
        action = owner.animation_data.action if owner.animation_data else None
        if action is None:
            raise ValueError("Target has no animation action")
        found = False
        for curve in action.fcurves:
            if curve.data_path != data_path:
                continue
            for point in curve.keyframe_points:
                if start <= point.co[0] <= end:
                    point.interpolation = interpolation
                    if interpolation == "BEZIER":
                        point.handle_left_type = "AUTO_CLAMPED"
                        point.handle_right_type = "AUTO_CLAMPED"
                        point.easing = {"ease_in": "EASE_IN", "ease_out": "EASE_OUT"}.get(easing, "AUTO")
                    found = True
        if not found:
            raise ValueError("No keyframes matched the requested property and frame range")

    def _apply_animation(self, operation: Operation) -> None:
        p = operation.parameters
        owner_type = p.get("owner_type", "object")
        if (
            operation.tool
            in {
                "animation.keyframe_insert",
                "animation.keyframe_update",
                "animation.keyframe_delete",
            }
            and owner_type != "object"
        ):
            self._atomic_scalar_keyframe(operation, owner_type)
            return
        obj = self._object(str(operation.target_id))
        if operation.tool == "animation.object_rotate":
            self._action(obj, f"{obj.name} Rotation")
            start, end = int(p["frame_start"]), int(p["frame_end"])
            initial = float(obj.rotation_euler.z)
            obj.rotation_euler.z = initial
            obj.keyframe_insert(data_path="rotation_euler", index=2, frame=start, group="Vibe Rotation")
            obj.rotation_euler.z = initial + math.radians(float(p["degrees"]))
            obj.keyframe_insert(data_path="rotation_euler", index=2, frame=end, group="Vibe Rotation")
            self._set_interpolation(
                obj, "rotation_euler", start, end, p.get("interpolation", "LINEAR"), p.get("easing", "linear")
            )
        elif operation.tool == "animation.object_move":
            self._action(obj, f"{obj.name} Movement")
            start, end = int(p["frame_start"]), int(p["frame_end"])
            obj.location = _vector(p["from_location"])
            obj.keyframe_insert(data_path="location", frame=start, group="Vibe Movement")
            obj.location = _vector(p["to_location"])
            obj.keyframe_insert(data_path="location", frame=end, group="Vibe Movement")
            self._set_interpolation(
                obj, "location", start, end, p.get("interpolation", "BEZIER"), p.get("easing", "ease_in_out")
            )
        elif operation.tool == "animation.camera_push":
            target = self._object(p["target_id"])
            self._action(obj, f"{obj.name} Push")
            start, end = int(p["frame_start"]), int(p["frame_end"])
            start_location = obj.location.copy()
            direction = (target.matrix_world.translation - start_location).normalized()
            obj.location = start_location
            obj.keyframe_insert(data_path="location", frame=start, group="Vibe Camera Push")
            obj.location = start_location + direction * float(p["distance"])
            obj.keyframe_insert(data_path="location", frame=end, group="Vibe Camera Push")
            self._set_interpolation(obj, "location", start, end, "BEZIER", p.get("easing", "ease_in_out"))
            self._aim_camera(obj, target)
        elif operation.tool == "animation.camera_orbit":
            target = self._object(p["target_id"])
            self._action(obj, f"{obj.name} Orbit")
            start, end = int(p["frame_start"]), int(p["frame_end"])
            for frame, angle in ((start, p["start_angle"]), (end, p["end_angle"])):
                radians = math.radians(float(angle))
                obj.location = (
                    target.location.x + math.cos(radians) * float(p["radius"]),
                    target.location.y + math.sin(radians) * float(p["radius"]),
                    target.location.z + float(p["height"]),
                )
                self._aim_camera(obj, target)
                obj.keyframe_insert(data_path="location", frame=frame, group="Vibe Camera Orbit")
                obj.keyframe_insert(data_path="rotation_euler", frame=frame, group="Vibe Camera Orbit")
            self._set_interpolation(obj, "location", start, end, "BEZIER", p.get("easing", "ease_in_out"))
            self._set_interpolation(obj, "rotation_euler", start, end, "BEZIER", p.get("easing", "ease_in_out"))
        elif operation.tool == "animation.interpolation_update":
            self._set_interpolation(
                obj,
                p["property"],
                int(p["frame_start"]),
                int(p["frame_end"]),
                p["interpolation"],
                p.get("easing", "smooth"),
            )
        elif operation.tool == "animation.retime":
            self._retime_profile(obj, p)
        else:
            self._atomic_keyframe(obj, operation)

    def _atomic_scalar_keyframe(self, operation: Operation, owner_type: str) -> None:
        p = operation.parameters
        property_name = p["property"]
        frame = int(p["frame"])
        if owner_type == "material":
            material = self._material(str(operation.target_id))
            socket = _principled(material).inputs[PRINCIPLED_INPUTS[property_name]]
            owner = socket
            data_path = "default_value"
            action_owner = material.node_tree
        elif owner_type == "light":
            light = self._object(str(operation.target_id))
            if light.type != "LIGHT":
                raise ValueError("Target is not a light")
            owner = light.data
            data_path = "energy"
            action_owner = light.data
        else:
            raise ValueError("Unsupported scalar animation owner")
        if operation.tool == "animation.keyframe_delete":
            owner.keyframe_delete(data_path=data_path, frame=frame)
            return
        if owner_type == "material":
            owner.default_value = float(p["value"])
        else:
            owner.energy = float(p["value"])
        owner.keyframe_insert(data_path=data_path, frame=frame, group="Vibe Scalar Animation")
        if action_owner.animation_data and action_owner.animation_data.action:
            ensure_uuid(action_owner.animation_data.action)

    def _atomic_keyframe(self, obj: Any, operation: Operation) -> None:
        p = operation.parameters
        data_path = p["property"]
        index = int(p.get("array_index", -1))
        frame = int(p["frame"])
        self._action(obj, f"{obj.name} Action")
        if operation.tool == "animation.keyframe_delete":
            obj.keyframe_delete(data_path=data_path, index=index, frame=frame)
            return
        value = p.get("value")
        if value is not None:
            current = getattr(obj, data_path)
            if index >= 0:
                current[index] = float(value)
            else:
                setattr(obj, data_path, value)
        obj.keyframe_insert(data_path=data_path, index=index, frame=frame, group="Vibe Animation")

    @staticmethod
    def _retime_profile(obj: Any, parameters: dict[str, Any]) -> None:
        action = obj.animation_data.action if obj.animation_data else None
        if action is None:
            raise ValueError("Target has no animation to retime")
        data_path = parameters["property"]
        start, end = int(parameters["frame_start"]), int(parameters["frame_end"])
        factor = float(parameters["factor"])
        if not parameters.get("preserve_duration", False):
            for curve in action.fcurves:
                if curve.data_path != data_path:
                    continue
                for point in curve.keyframe_points:
                    if start < point.co[0] < end:
                        point.co[0] = start + (point.co[0] - start) * factor
                curve.update()
            return
        curves = [curve for curve in action.fcurves if curve.data_path == data_path]
        if not curves:
            raise ValueError("No matching animation curve exists")
        warped_frame = start + (end - start) * min(max(0.5 * factor, 0.05), 0.95)
        for curve in curves:
            start_value = curve.evaluate(start)
            end_value = curve.evaluate(end)
            midpoint = curve.keyframe_points.insert(warped_frame, (start_value + end_value) / 2.0, options={"FAST"})
            midpoint.interpolation = "BEZIER"
            midpoint.handle_left_type = "AUTO_CLAMPED"
            midpoint.handle_right_type = "AUTO_CLAMPED"
            curve.update()

    def verify(self, change_set: ChangeSet, before: dict[str, Any]) -> dict[str, Any]:
        after = self.snapshot_scene()
        checks: list[dict[str, Any]] = []
        target_ids = {operation.target_id for operation in change_set.operations if operation.target_id}
        for operation in change_set.operations:
            checks.append(
                {"name": "operation_executed", "passed": True, "expected": operation.tool, "actual": operation.tool}
            )
            if operation.tool == "material.update" and operation.target_id:
                expected_material = before["materials"][operation.target_id]
                actual_material = after["materials"].get(operation.target_id)
                if actual_material is not None:
                    if "material_color" in change_set.preserve:
                        checks.append(
                            {
                                "name": "preserved_material_color",
                                "passed": tracked_values_equal(
                                    expected_material.get("base_color"), actual_material.get("base_color")
                                ),
                                "expected": expected_material.get("base_color"),
                                "actual": actual_material.get("base_color"),
                            }
                        )
                    if "material_graph" in change_set.preserve:
                        expected_graph = (expected_material["node_count"], expected_material["link_count"])
                        actual_graph = (actual_material["node_count"], actual_material["link_count"])
                        checks.append(
                            {
                                "name": "preserved_material_graph",
                                "passed": expected_graph == actual_graph,
                                "expected": expected_graph,
                                "actual": actual_graph,
                            }
                        )
                    if "material_properties" in change_set.preserve:
                        preserved_fields = set(PRINCIPLED_INPUTS) - set(operation.parameters)
                        expected_properties = {field: expected_material.get(field) for field in preserved_fields}
                        actual_properties = {field: actual_material.get(field) for field in preserved_fields}
                        checks.append(
                            {
                                "name": "preserved_material_properties",
                                "passed": tracked_values_equal(expected_properties, actual_properties),
                                "expected": expected_properties,
                                "actual": actual_properties,
                            }
                        )
            if operation.tool == "light.update" and operation.target_id:
                expected_lights = {key: value for key, value in before["lights"].items() if key != operation.target_id}
                actual_lights = {key: after["lights"].get(key) for key in expected_lights}
                checks.append(
                    {
                        "name": "unrelated_lights_unchanged",
                        "passed": tracked_values_equal(expected_lights, actual_lights),
                        "expected": expected_lights,
                        "actual": actual_lights,
                    }
                )
        if "all_unselected_objects" in change_set.preserve:
            before_objects = {key: value for key, value in before["objects"].items() if key not in target_ids}
            after_objects = {key: after["objects"].get(key) for key in before_objects}
            checks.append(
                {
                    "name": "all_unselected_objects_unchanged",
                    "passed": tracked_values_equal(before_objects, after_objects),
                    "expected": before_objects,
                    "actual": after_objects,
                }
            )
        preserve_sections = {
            "materials": "materials",
            "lights": "lights",
            "camera": "cameras",
            "camera_animation": "cameras",
            "scene_duration": "scene",
        }
        for preserve, section in preserve_sections.items():
            if preserve in change_set.preserve:
                expected = before[section]
                actual = after[section]
                if preserve == "scene_duration":
                    expected = (before["scene"]["frame_start"], before["scene"]["frame_end"])
                    actual = (after["scene"]["frame_start"], after["scene"]["frame_end"])
                checks.append(
                    {
                        "name": f"preserved_{preserve}",
                        "passed": tracked_values_equal(expected, actual),
                        "expected": expected,
                        "actual": actual,
                    }
                )
        return {"passed": all(check["passed"] for check in checks), "checks": checks}

    def inspect_animation(self, target_id: str) -> dict[str, Any]:
        obj = self._object(target_id)
        action = _action_snapshot(obj)
        return {
            "target_uuid": target_id,
            "action": action,
            "nla_present": bool(obj.animation_data and len(obj.animation_data.nla_tracks)),
            "warnings": [] if action else ["No action assigned"],
        }


@dataclass
class StudioService:
    bpy: Any

    def __post_init__(self) -> None:
        self.gateway = StudioGateway(self.bpy)
        self.transactions = TransactionEngine(self.gateway)

    def preview(self, change_set: ChangeSet):
        return self.transactions.preview(change_set)

    def apply_pending(self):
        return self.transactions.apply_pending()

    def execute(self, change_set: ChangeSet):
        self.preview(change_set)
        return self.apply_pending()

    def undo(self):
        return self.transactions.undo()

    def redo(self):
        return self.transactions.redo()
