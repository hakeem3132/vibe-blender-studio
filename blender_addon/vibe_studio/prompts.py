"""Deterministic, offline Milestone 1 prompt interpreter."""

from __future__ import annotations

import math
import re
import uuid
from typing import Any

from .contracts import ChangeSet

UNSUPPORTED_MESSAGE = (
    "This milestone currently supports object creation, transform and visibility changes. "
    "Animation, materials, video, characters and game generation are not enabled yet."
)


class UnsupportedPrompt(ValueError):
    pass


def interpret_prompt(prompt: str, selected_id: str | None) -> ChangeSet:
    text = " ".join(prompt.strip().lower().split())
    preserve = ["rotation", "scale", "visibility", "materials", "animation", "all_unselected_objects"]
    tool: str
    parameters: dict[str, Any]
    target_id: str | None
    scope_type = "selected_object"
    creation = re.fullmatch(r"create (?:a |an )?(cube|sphere|cylinder|plane|empty)\.?", text)
    if creation:
        tool = "object.create"
        parameters = {"primitive": creation.group(1), "location": [0.0, 0.0, 0.0]}
        target_id = None
        scope_type = "current_scene"
        preserve = ["all_unselected_objects"]
    else:
        if selected_id is None:
            raise UnsupportedPrompt("Select one object before using a transform or visibility prompt.")
        target_id = selected_id
        move_delta = re.search(
            r"move (?:only )?(?:the )?(?:selected )?(?:object|cube).*?([\d.]+) metre(?:s)? (upward|downward)", text
        )
        move_absolute = re.search(
            r"move (?:only )?(?:the )?(?:selected )?(?:object|cube).*?x\s*(-?[\d.]+)[, ]+y\s*(-?[\d.]+)[, ]+z\s*(-?[\d.]+)",
            text,
        )
        rotate = re.search(r"rotate (?:the )?selected object ([-\d.]+) degrees around ([xyz])", text)
        scale = re.search(r"scale (?:the )?selected object to (twice|double|[-\d.]+) (?:its )?current size", text)
        if move_delta:
            amount = float(move_delta.group(1)) * (1.0 if move_delta.group(2) == "upward" else -1.0)
            tool, parameters = "object.transform", {"location_delta": [0.0, 0.0, amount]}
        elif move_absolute:
            tool = "object.transform"
            parameters = {"location": [float(move_absolute.group(i)) for i in range(1, 4)]}
        elif rotate:
            values = [0.0, 0.0, 0.0]
            values["xyz".index(rotate.group(2))] = math.radians(float(rotate.group(1)))
            tool, parameters = "object.transform", {"rotation_delta": values}
            preserve = ["location", "scale", "visibility", "materials", "animation", "all_unselected_objects"]
        elif scale:
            factor = 2.0 if scale.group(1) in {"twice", "double"} else float(scale.group(1))
            tool, parameters = "object.transform", {"scale_factor": factor}
            preserve = ["location", "rotation", "visibility", "materials", "animation", "all_unselected_objects"]
        elif re.fullmatch(r"hide (?:the )?selected object from rendering\.?", text):
            tool, parameters = "object.visibility", {"render_visible": False}
            preserve = ["location", "rotation", "scale", "materials", "animation", "all_unselected_objects"]
        else:
            raise UnsupportedPrompt(UNSUPPORTED_MESSAGE)
    payload = {
        "schema_version": "1.0",
        "change_set_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "prompt": prompt,
        "intent": tool,
        "scope": {"type": scope_type, "target_ids": [] if target_id is None else [target_id]},
        "operations": [{"tool": tool, "target_id": target_id, "parameters": parameters}],
        "preserve": preserve,
        "verification": ["target_exists", "requested_state_applied", "preserved_state_unchanged"],
        "risk": "low",
    }
    return ChangeSet.from_dict(payload)
