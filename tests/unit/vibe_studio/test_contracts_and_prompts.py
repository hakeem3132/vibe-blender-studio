import uuid

import pytest
from blender_addon.vibe_studio.contracts import ChangeSet, ChangeSetError
from blender_addon.vibe_studio.prompts import UNSUPPORTED_MESSAGE, UnsupportedPrompt, interpret_prompt

TARGET = str(uuid.uuid4())


@pytest.mark.parametrize("primitive", ["cube", "sphere", "cylinder", "plane", "empty"])
def test_creation_prompts_are_strict_allowlisted_changesets(primitive):
    change_set = interpret_prompt(f"Create a {primitive}.", None)
    assert change_set.intent == "object.create"
    assert change_set.operations[0].parameters["primitive"] == primitive


def test_move_prompt_preserves_unselected_state():
    change_set = interpret_prompt("Move the selected object 1 metre upward.", TARGET)
    assert change_set.operations[0].parameters["location_delta"] == [0.0, 0.0, 1.0]
    assert "all_unselected_objects" in change_set.preserve


def test_rotation_is_converted_to_radians():
    change_set = interpret_prompt("Rotate the selected object 45 degrees around Z.", TARGET)
    assert change_set.operations[0].parameters["rotation_delta"][2] == pytest.approx(0.7853981634)


def test_unsupported_prompt_never_executes():
    with pytest.raises(UnsupportedPrompt, match=UNSUPPORTED_MESSAGE):
        interpret_prompt("Make a cinematic character animation", TARGET)


def test_unknown_changeset_field_is_rejected():
    valid = interpret_prompt("Create a cube.", None)
    payload = {
        "schema_version": valid.schema_version,
        "change_set_id": valid.change_set_id,
        "request_id": valid.request_id,
        "prompt": valid.prompt,
        "intent": valid.intent,
        "scope": {"type": valid.scope.type, "target_ids": list(valid.scope.target_ids)},
        "operations": [
            {"tool": item.tool, "target_id": item.target_id, "parameters": item.parameters} for item in valid.operations
        ],
        "preserve": list(valid.preserve),
        "verification": list(valid.verification),
        "risk": valid.risk,
        "python": "exec('unsafe')",
    }
    with pytest.raises(ChangeSetError, match="Unknown ChangeSet fields"):
        ChangeSet.from_dict(payload)


def test_selected_transform_requires_selection():
    with pytest.raises(UnsupportedPrompt, match="Select one object"):
        interpret_prompt("Move the selected object 1 metre upward.", None)
