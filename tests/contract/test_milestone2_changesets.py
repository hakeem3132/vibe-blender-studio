from __future__ import annotations

import uuid
from typing import Any

import pytest
from blender_addon.vibe_studio.contracts import ALLOWED_TOOLS, ChangeSet, ChangeSetError
from blender_addon.vibe_studio.milestone2_prompts import (
    MILESTONE_2_UNSUPPORTED,
    UnsupportedMilestone2Prompt,
    interpret_milestone2_prompt,
)

TARGET = str(uuid.uuid4())
MATERIAL = str(uuid.uuid4())
CAMERA = str(uuid.uuid4())


def test_milestone2_allowlist_has_no_python_execution() -> None:
    required = {
        "material.create",
        "material.assign",
        "material.duplicate",
        "material.update",
        "light.create",
        "light.update",
        "camera.create",
        "camera.activate",
        "animation.object_rotate",
        "animation.camera_push",
        "animation.retime",
        "render.image_sequence",
        "video.encode",
        "video.validate",
    }
    assert required <= ALLOWED_TOOLS
    assert all("python" not in item and "exec" not in item and "eval" not in item for item in ALLOWED_TOOLS)


@pytest.mark.parametrize(
    ("prompt", "tool"),
    [
        ("Create a glossy black material.", "material.create"),
        ("Create a transparent glass material.", "material.create"),
        ("Make the selected object metallic.", "material.update"),
        ("Reduce only roughness to 0.2.", "material.update"),
        ("Create three-point lighting.", "light.create"),
        ("Add a rim light.", "light.create"),
        ("Create a hero camera.", "camera.create"),
        ("Use a 70 mm lens.", "camera.configure"),
        ("Push the camera toward the selected object over 5 seconds.", "animation.camera_push"),
        ("Orbit the camera 90 degrees around the selected object.", "animation.camera_orbit"),
        ("Rotate the selected object 360 degrees over 5 seconds.", "animation.object_rotate"),
        ("Move the selected object upward between frames 1 and 60.", "animation.object_move"),
        ("Make the animation ease in and out.", "animation.interpolation_update"),
        ("Slow the selected animation by 20%.", "animation.retime"),
        ("Preview frames 1 to 60.", "render.preview_range"),
        ("Render the animation.", "render.image_sequence"),
        ("Export an MP4.", "video.encode"),
    ],
)
def test_offline_prompt_interpreter_returns_strict_tools(prompt: str, tool: str) -> None:
    change_set = interpret_milestone2_prompt(
        prompt,
        selected_id=TARGET,
        selected_material_id=MATERIAL,
        camera_id=CAMERA,
        key_light_id=str(uuid.uuid4()),
    )
    assert change_set.intent == tool
    assert all(operation.tool in ALLOWED_TOOLS for operation in change_set.operations)


def test_unknown_fields_and_unbounded_animation_are_rejected() -> None:
    valid = interpret_milestone2_prompt("Rotate the selected object 360 degrees over 5 seconds.", selected_id=TARGET)
    raw: dict[str, Any] = {
        "schema_version": valid.schema_version,
        "change_set_id": valid.change_set_id,
        "request_id": valid.request_id,
        "prompt": valid.prompt,
        "intent": valid.intent,
        "scope": {"type": valid.scope.type, "target_ids": list(valid.scope.target_ids)},
        "operations": [
            {
                "tool": "animation.object_rotate",
                "target_id": TARGET,
                "parameters": {"frame_start": 1, "frame_end": 10001, "degrees": 360},
            }
        ],
        "preserve": list(valid.preserve),
        "verification": list(valid.verification),
        "risk": "low",
    }
    with pytest.raises(ChangeSetError, match="at most"):
        ChangeSet.from_dict(raw)
    raw["unexpected"] = True
    with pytest.raises(ChangeSetError, match="Unknown"):
        ChangeSet.from_dict(raw)


def test_unsupported_prompt_is_actionable() -> None:
    with pytest.raises(UnsupportedMilestone2Prompt, match="Storyboards") as failure:
        interpret_milestone2_prompt("Create a talking character.", selected_id=TARGET)
    assert str(failure.value) == MILESTONE_2_UNSUPPORTED


@pytest.mark.parametrize(
    ("owner_type", "property_name"),
    [("material", "roughness"), ("material", "emission_strength"), ("light", "energy")],
)
def test_scalar_animation_targets_are_strict(owner_type: str, property_name: str) -> None:
    base = interpret_milestone2_prompt("Rotate the selected object 360 degrees over 5 seconds.", selected_id=TARGET)
    raw: dict[str, Any] = {
        "schema_version": base.schema_version,
        "change_set_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "prompt": "Animate one bounded scalar",
        "intent": "animation.keyframe_insert",
        "scope": {"type": "selected_object", "target_ids": [MATERIAL]},
        "operations": [
            {
                "tool": "animation.keyframe_insert",
                "target_id": MATERIAL,
                "parameters": {"owner_type": owner_type, "property": property_name, "frame": 1, "value": 0.5},
            }
        ],
        "preserve": ["all_unselected_objects"],
        "verification": ["requested_state_applied"],
        "risk": "low",
    }
    assert ChangeSet.from_dict(raw).operations[0].parameters["owner_type"] == owner_type
    raw["operations"][0]["parameters"]["property"] = "unsafe.path"
    with pytest.raises(ChangeSetError, match="Unsupported animated property"):
        ChangeSet.from_dict(raw)
