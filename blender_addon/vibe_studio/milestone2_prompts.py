"""Deterministic offline Milestone 2 prompt-to-ChangeSet interpreter."""

from __future__ import annotations

import re
import uuid
from typing import Any

from .contracts import ChangeSet

MILESTONE_2_UNSUPPORTED = (
    "Milestone 2 supports bounded materials, studio lighting, cameras, object/camera animation, "
    "preview rendering and MP4 export. Storyboards, audio, characters and games are not enabled."
)


class UnsupportedMilestone2Prompt(ValueError):
    pass


def _changeset(
    prompt: str,
    tool: str,
    target_id: str | None,
    parameters: dict[str, Any],
    preserve: list[str],
) -> ChangeSet:
    payload = {
        "schema_version": "1.0",
        "change_set_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "prompt": prompt,
        "intent": tool,
        "scope": {
            "type": "selected_object" if target_id else "current_scene",
            "target_ids": [target_id] if target_id else [],
        },
        "operations": [{"tool": tool, "target_id": target_id, "parameters": parameters}],
        "preserve": preserve,
        "verification": ["requested_state_applied", "preserved_state_unchanged"],
        "risk": "low",
    }
    return ChangeSet.from_dict(payload)


def _multi_changeset(prompt: str, intent: str, operations: list[dict[str, Any]], preserve: list[str]) -> ChangeSet:
    return ChangeSet.from_dict(
        {
            "schema_version": "1.0",
            "change_set_id": str(uuid.uuid4()),
            "request_id": str(uuid.uuid4()),
            "prompt": prompt,
            "intent": intent,
            "scope": {"type": "current_scene", "target_ids": []},
            "operations": operations,
            "preserve": preserve,
            "verification": ["requested_state_applied", "preserved_state_unchanged"],
            "risk": "low",
        }
    )


def interpret_milestone2_prompt(
    prompt: str,
    *,
    selected_id: str | None,
    selected_material_id: str | None = None,
    camera_id: str | None = None,
    target_id: str | None = None,
    key_light_id: str | None = None,
    fps: int = 24,
    frame_start: int = 1,
    frame_end: int = 144,
    output_dir: str = "outputs",
) -> ChangeSet:
    text = " ".join(prompt.strip().lower().split())
    if re.fullmatch(r"create a glossy black material\.?", text):
        return _changeset(
            prompt,
            "material.create",
            None,
            {"name": "Glossy Black", "preset": "product_black"},
            ["all_unselected_objects"],
        )
    if re.fullmatch(r"create a transparent glass material\.?", text):
        return _changeset(
            prompt,
            "material.create",
            None,
            {"name": "Transparent Glass", "preset": "glass"},
            ["all_unselected_objects"],
        )
    if re.fullmatch(r"make the selected object metallic\.?", text):
        if not selected_material_id:
            raise UnsupportedMilestone2Prompt("The selected object needs a managed material first.")
        return _changeset(
            prompt,
            "material.update",
            selected_material_id,
            {"metallic": 1.0},
            ["material_color", "material_graph", "all_unselected_objects"],
        )
    roughness = re.fullmatch(r"reduce (?:only )?roughness to (0(?:\.\d+)?|1(?:\.0+)?)\.?", text)
    if roughness:
        if not selected_material_id:
            raise UnsupportedMilestone2Prompt("The selected object needs a managed material first.")
        return _changeset(
            prompt,
            "material.update",
            selected_material_id,
            {"roughness": float(roughness.group(1))},
            ["material_color", "material_graph", "all_unselected_objects"],
        )
    if re.fullmatch(r"create three-point lighting(?: for the selected object)?\.?", text):
        definitions = (
            ("Studio Key", "key", 900.0, [4.0, -4.0, 5.0], [1.0, 0.82, 0.68, 1.0], 3.0),
            ("Studio Fill", "fill", 420.0, [-4.0, -2.0, 2.5], [0.62, 0.75, 1.0, 1.0], 4.0),
            ("Studio Rim", "rim", 700.0, [0.0, 4.0, 4.5], [1.0, 0.45, 0.22, 1.0], 2.0),
        )
        return _multi_changeset(
            prompt,
            "light.create",
            [
                {
                    "tool": "light.create",
                    "target_id": None,
                    "parameters": {
                        "name": name,
                        "type": "AREA",
                        "role": role,
                        "energy": energy,
                        "location": location,
                        "color": color,
                        "size": size,
                    },
                }
                for name, role, energy, location, color, size in definitions
            ],
            ["camera", "object_animation"],
        )
    if re.fullmatch(r"add a (?:soft )?rim light(?: behind the product)?\.?", text):
        return _changeset(
            prompt,
            "light.create",
            None,
            {
                "name": "Studio Rim",
                "type": "AREA",
                "role": "rim",
                "energy": 700.0,
                "location": [0.0, 4.0, 4.5],
                "color": [1.0, 0.45, 0.22, 1.0],
                "size": 2.0,
            },
            ["camera", "object_animation", "all_unselected_objects"],
        )
    if re.fullmatch(r"reduce (?:only )?the key-light energy by 20%\.?", text):
        if key_light_id is None:
            raise UnsupportedMilestone2Prompt("A uniquely managed key light is required for this prompt.")
        return _changeset(
            prompt,
            "light.update",
            key_light_id,
            {"energy": 720.0},
            ["camera", "object_animation", "all_unselected_objects"],
        )
    if re.fullmatch(r"create a hero camera(?: focused on the selected product)?\.?", text):
        if selected_id is None:
            raise UnsupportedMilestone2Prompt("Select the product before creating a hero camera.")
        return _changeset(
            prompt,
            "camera.create",
            None,
            {
                "name": "Hero Camera",
                "preset": "hero_product",
                "target_id": selected_id,
                "location": [7.5, -9.0, 4.8],
                "lens": 55.0,
            },
            ["lights", "materials", "object_animation"],
        )
    lens = re.fullmatch(r"use a (\d+(?:\.\d+)?) mm lens\.?", text)
    if lens and camera_id:
        return _changeset(
            prompt,
            "camera.configure",
            camera_id,
            {"lens": float(lens.group(1))},
            ["camera_animation", "all_unselected_objects"],
        )
    push = re.fullmatch(
        r"(?:push|move) the camera (?:slowly )?(?:toward|towards) the selected "
        r"(?:object|product|bottle) over (\d+(?:\.\d+)?) seconds\.?",
        text,
    )
    if push and camera_id and selected_id:
        end = frame_start + round(float(push.group(1)) * fps) - 1
        return _changeset(
            prompt,
            "animation.camera_push",
            camera_id,
            {
                "frame_start": frame_start,
                "frame_end": end,
                "distance": 1.2,
                "target_id": selected_id,
                "easing": "ease_in_out",
            },
            ["object_animation", "lights", "materials", "scene_duration"],
        )
    if (
        re.fullmatch(r"orbit the camera(?: 90 degrees)? around the selected object\.?", text)
        and camera_id
        and selected_id
    ):
        return _changeset(
            prompt,
            "animation.camera_orbit",
            camera_id,
            {
                "frame_start": frame_start,
                "frame_end": frame_end,
                "radius": 8.0,
                "start_angle": 0.0,
                "end_angle": 90.0,
                "height": 3.5,
                "target_id": selected_id,
                "easing": "ease_in_out",
            },
            ["object_animation", "lights", "materials", "scene_duration"],
        )
    rotate = re.fullmatch(r"rotate the selected (?:object|bottle) 360 degrees over (\d+(?:\.\d+)?) seconds\.?", text)
    if rotate and selected_id:
        end = frame_start + round(float(rotate.group(1)) * fps) - 1
        return _changeset(
            prompt,
            "animation.object_rotate",
            selected_id,
            {
                "frame_start": frame_start,
                "frame_end": end,
                "degrees": 360.0,
                "interpolation": "LINEAR",
                "easing": "linear",
            },
            ["camera_animation", "lights", "materials", "all_unselected_objects"],
        )
    move = re.fullmatch(r"move the selected object upward between frames (\d+) and (\d+)\.?", text)
    if move and selected_id:
        return _changeset(
            prompt,
            "animation.object_move",
            selected_id,
            {
                "frame_start": int(move.group(1)),
                "frame_end": int(move.group(2)),
                "from_location": [0.0, 0.0, 0.0],
                "to_location": [0.0, 0.0, 1.0],
                "interpolation": "BEZIER",
                "easing": "ease_in_out",
            },
            ["camera_animation", "lights", "materials", "all_unselected_objects"],
        )
    if re.fullmatch(r"make the animation ease in and out\.?", text) and selected_id:
        return _changeset(
            prompt,
            "animation.interpolation_update",
            selected_id,
            {
                "property": "rotation_euler",
                "frame_start": frame_start,
                "frame_end": frame_end,
                "interpolation": "BEZIER",
                "easing": "ease_in_out",
            },
            ["camera_animation", "keyframes_outside_range", "all_unselected_objects"],
        )
    if re.fullmatch(r"slow the selected animation by 20%\.?", text) and selected_id:
        return _changeset(
            prompt,
            "animation.retime",
            selected_id,
            {
                "property": "rotation_euler",
                "frame_start": frame_start,
                "frame_end": frame_end,
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
    if re.fullmatch(r"preview frames (\d+) to (\d+)\.?", text):
        match = re.fullmatch(r"preview frames (\d+) to (\d+)\.?", text)
        assert match is not None
        return _changeset(
            prompt,
            "render.preview_range",
            None,
            {
                "frame_start": int(match.group(1)),
                "frame_end": int(match.group(2)),
                "frame_step": 1,
                "preset": "draft",
                "output_dir": output_dir,
            },
            [],
        )
    if re.fullmatch(r"render the animation\.?", text):
        return _changeset(
            prompt,
            "render.image_sequence",
            None,
            {
                "frame_start": frame_start,
                "frame_end": frame_end,
                "frame_step": 1,
                "preset": "preview",
                "output_dir": output_dir,
            },
            [],
        )
    if re.fullmatch(r"export an mp4\.?", text):
        return _changeset(
            prompt,
            "video.encode",
            None,
            {
                "frames_dir": f"{output_dir}/frames",
                "output_path": f"{output_dir}/videos/vibe_animation.mp4",
                "fps": fps,
                "codec": "libx264",
                "overwrite": False,
            },
            [],
        )
    raise UnsupportedMilestone2Prompt(MILESTONE_2_UNSUPPORTED)
