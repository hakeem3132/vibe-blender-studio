"""Allowlisted Blender gateway; every mutation is invoked from Blender's main thread."""

from __future__ import annotations

from typing import Any

from .contracts import ChangeSet
from .identities import REVISION_KEY, UUID_KEY, ensure_uuid, lookup_unique


def tracked_values_equal(expected: Any, actual: Any, tolerance: float = 1e-6) -> bool:
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        return len(expected) == len(actual) and all(
            tracked_values_equal(expected_item, actual_item, tolerance)
            for expected_item, actual_item in zip(expected, actual, strict=True)
        )
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return abs(float(expected) - float(actual)) <= tolerance
        except (TypeError, ValueError):
            return False
    return expected == actual


class BlenderSceneGateway:
    def __init__(self, bpy_module: Any):
        self.bpy = bpy_module

    def _objects(self) -> list[Any]:
        return list(self.bpy.context.scene.objects)

    def _find(self, stable_id: str) -> Any:
        return lookup_unique(self._objects(), stable_id)

    def validate_targets(self, change_set: ChangeSet) -> None:
        for operation in change_set.operations:
            if operation.target_id is not None:
                self._find(operation.target_id)

    def snapshot_scene(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for obj in self._objects():
            stable_id = ensure_uuid(obj)
            result[stable_id] = {
                "name": obj.name,
                "type": obj.type,
                "location": tuple(float(item) for item in obj.location),
                "rotation": tuple(float(item) for item in obj.rotation_euler),
                "scale": tuple(float(item) for item in obj.scale),
                "hide_viewport": bool(obj.hide_viewport),
                "hide_render": bool(obj.hide_render),
                "materials": tuple(slot.material.name for slot in obj.material_slots if slot.material),
                "animation": getattr(obj, "animation_data", None) is not None,
                "revision": int(obj.get(REVISION_KEY, 0)),
            }
        return result

    def _create(self, primitive: str, location: Any, stable_id: str | None = None) -> Any:
        if primitive == "cube":
            self.bpy.ops.mesh.primitive_cube_add(location=location)
        elif primitive == "sphere":
            self.bpy.ops.mesh.primitive_uv_sphere_add(location=location)
        elif primitive == "cylinder":
            self.bpy.ops.mesh.primitive_cylinder_add(location=location)
        elif primitive == "plane":
            self.bpy.ops.mesh.primitive_plane_add(location=location)
        elif primitive == "empty":
            self.bpy.ops.object.empty_add(type="PLAIN_AXES", location=location)
        else:
            raise ValueError(f"Unsupported primitive: {primitive}")
        obj = self.bpy.context.active_object
        obj[UUID_KEY] = stable_id or ensure_uuid(obj)
        obj[REVISION_KEY] = 0
        return obj

    def apply(self, change_set: ChangeSet) -> None:
        for operation in change_set.operations:
            params = operation.parameters
            if operation.tool == "object.create":
                self._create(params["primitive"], params.get("location", (0.0, 0.0, 0.0)))
                continue
            obj = self._find(str(operation.target_id))
            if operation.tool == "object.transform":
                if "location" in params:
                    obj.location = params["location"]
                if "location_delta" in params:
                    obj.location = [obj.location[index] + params["location_delta"][index] for index in range(3)]
                if "rotation" in params:
                    obj.rotation_euler = params["rotation"]
                if "rotation_delta" in params:
                    obj.rotation_euler = [
                        obj.rotation_euler[index] + params["rotation_delta"][index] for index in range(3)
                    ]
                if "scale" in params:
                    obj.scale = params["scale"]
                if "scale_factor" in params:
                    obj.scale = [item * params["scale_factor"] for item in obj.scale]
            elif operation.tool == "object.visibility":
                if "viewport_visible" in params:
                    obj.hide_viewport = not params["viewport_visible"]
                if "render_visible" in params:
                    obj.hide_render = not params["render_visible"]
            obj[REVISION_KEY] = int(obj.get(REVISION_KEY, 0)) + 1

    def restore_scene(self, snapshot: dict[str, Any]) -> None:
        current = {ensure_uuid(obj): obj for obj in self._objects()}
        for stable_id, obj in list(current.items()):
            if stable_id not in snapshot:
                self.bpy.data.objects.remove(obj, do_unlink=True)
        current = {ensure_uuid(obj): obj for obj in self._objects()}
        for stable_id, state in snapshot.items():
            obj = current.get(stable_id)
            if obj is None:
                primitive = {"MESH": "cube", "EMPTY": "empty"}.get(state["type"])
                if primitive is None:
                    raise RuntimeError(f"Cannot restore deleted object type {state['type']}")
                obj = self._create(primitive, state["location"], stable_id)
            obj.name = state["name"]
            obj.location = state["location"]
            obj.rotation_euler = state["rotation"]
            obj.scale = state["scale"]
            obj.hide_viewport = state["hide_viewport"]
            obj.hide_render = state["hide_render"]
            obj[REVISION_KEY] = state["revision"]

    def verify(self, change_set: ChangeSet, before: dict[str, Any]) -> dict[str, Any]:
        after = self.snapshot_scene()
        checks: list[dict[str, Any]] = []
        target_ids = set(change_set.scope.target_ids)
        for operation in change_set.operations:
            exists = operation.tool == "object.create" and len(after) == len(before) + 1
            if operation.target_id is not None:
                exists = operation.target_id in after
            checks.append({"name": "target_exists", "passed": exists, "expected": True, "actual": exists})
            if operation.target_id is not None and exists:
                target_before = before[operation.target_id]
                target_after = after[operation.target_id]
                requested_expected: dict[str, Any] = {}
                parameters = operation.parameters
                if operation.tool == "object.transform":
                    if "location" in parameters:
                        requested_expected["location"] = tuple(float(item) for item in parameters["location"])
                    if "location_delta" in parameters:
                        requested_expected["location"] = tuple(
                            target_before["location"][index] + parameters["location_delta"][index] for index in range(3)
                        )
                    if "rotation" in parameters:
                        requested_expected["rotation"] = tuple(float(item) for item in parameters["rotation"])
                    if "rotation_delta" in parameters:
                        requested_expected["rotation"] = tuple(
                            target_before["rotation"][index] + parameters["rotation_delta"][index] for index in range(3)
                        )
                    if "scale" in parameters:
                        requested_expected["scale"] = tuple(float(item) for item in parameters["scale"])
                    if "scale_factor" in parameters:
                        requested_expected["scale"] = tuple(
                            item * parameters["scale_factor"] for item in target_before["scale"]
                        )
                elif operation.tool == "object.visibility":
                    if "viewport_visible" in parameters:
                        requested_expected["hide_viewport"] = not parameters["viewport_visible"]
                    if "render_visible" in parameters:
                        requested_expected["hide_render"] = not parameters["render_visible"]
                for field, expected in requested_expected.items():
                    actual = target_after[field]
                    checks.append(
                        {
                            "name": f"requested_{field}_applied",
                            "passed": tracked_values_equal(expected, actual),
                            "expected": expected,
                            "actual": actual,
                        }
                    )
                preserved_fields = {
                    "location": ("location",),
                    "rotation": ("rotation",),
                    "scale": ("scale",),
                    "visibility": ("hide_viewport", "hide_render"),
                    "materials": ("materials",),
                    "animation": ("animation",),
                }
                for preserve in change_set.preserve:
                    fields = preserved_fields.get(preserve, ())
                    expected = tuple(target_before[field] for field in fields)
                    actual = tuple(target_after[field] for field in fields)
                    if fields:
                        checks.append(
                            {
                                "name": f"preserved_{preserve}_unchanged",
                                "passed": tracked_values_equal(expected, actual),
                                "expected": expected,
                                "actual": actual,
                            }
                        )
        if "all_unselected_objects" in change_set.preserve:
            preserved = all(before[key] == after.get(key) for key in before if key not in target_ids)
            checks.append(
                {
                    "name": "preserved_state_unchanged",
                    "passed": preserved,
                    "expected": "unchanged",
                    "actual": "unchanged" if preserved else "changed",
                }
            )
        return {"passed": all(check["passed"] for check in checks), "checks": checks}
