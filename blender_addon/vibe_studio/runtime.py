"""Composition root for the Blender-native Vibe Studio slice."""

from __future__ import annotations

import json
import os
import platform
import tempfile
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..infrastructure.rpc_security import PROTOCOL_VERSION, redact
from ..version import DISPLAY_VERSION, UPSTREAM_COMMIT, UPSTREAM_VERSION
from .background_render import BackgroundRenderRunner, BackgroundRenderSnapshot
from .ffmpeg_adapter import FFmpegAdapter
from .gateway import BlenderSceneGateway
from .identities import ensure_uuid, inspect_uuid, repair_duplicates, validation_report
from .inspection import inspect_scene
from .media_contracts import RenderJob, RenderJobQueue
from .milestone2_prompts import UnsupportedMilestone2Prompt, interpret_milestone2_prompt
from .prompts import interpret_prompt
from .render_pipeline import BlenderRenderPipeline
from .studio import StudioService
from .transactions import TransactionEngine


class VibeRuntime:
    def __init__(self, bpy_module: Any):
        self.bpy = bpy_module
        self.gateway = BlenderSceneGateway(bpy_module)
        self.transactions = TransactionEngine(self.gateway)
        self.studio = StudioService(bpy_module)
        self.last_transactions = self.transactions
        self.render_queue = RenderJobQueue()
        self.background_runner: BackgroundRenderRunner | None = None
        self.background_job: RenderJob | None = None
        self.last_scene_summary: dict[str, Any] = {}
        self.cancelled = False

    def selected_id(self, assign: bool = True) -> str | None:
        obj = self.bpy.context.view_layer.objects.active
        if obj is None:
            return None
        return ensure_uuid(obj) if assign else inspect_uuid(obj)

    def preview_prompt(self, prompt: str, *, scope: str = "SELECTED", preserve_unselected: bool = True):
        self.cancelled = False
        try:
            change_set = interpret_prompt(prompt, self.selected_id())
            transactions = self.transactions
        except ValueError as foundation_error:
            selected = self.bpy.context.view_layer.objects.active
            material_id = None
            if selected is not None and getattr(selected, "active_material", None) is not None:
                material_id = ensure_uuid(selected.active_material)
            camera_id = ensure_uuid(self.bpy.context.scene.camera) if self.bpy.context.scene.camera else None
            try:
                change_set = interpret_milestone2_prompt(
                    prompt,
                    selected_id=self.selected_id(),
                    selected_material_id=material_id,
                    camera_id=camera_id,
                    fps=int(self.bpy.context.scene.render.fps),
                    frame_start=int(self.bpy.context.scene.frame_start),
                    frame_end=int(self.bpy.context.scene.frame_end),
                )
            except UnsupportedMilestone2Prompt as milestone_error:
                raise milestone_error from foundation_error
            if change_set.intent.startswith(("render.", "video.")):
                raise ValueError("Render and video requests use the bounded Render controls")
            transactions = self.studio.transactions
        if scope == "SCENE" and change_set.scope.type != "current_scene":
            raise ValueError("Current-scene scope supports object creation only in Milestone 1")
        if scope == "SELECTED" and change_set.scope.type != "selected_object":
            raise ValueError("Choose Current scene when creating a new object")
        if not preserve_unselected:
            change_set = replace(
                change_set,
                preserve=tuple(item for item in change_set.preserve if item != "all_unselected_objects"),
            )
        self.last_transactions = transactions
        return transactions.preview(change_set)

    def active_transactions(self) -> TransactionEngine:
        return self.last_transactions

    def project_root(self) -> Path:
        if not self.bpy.data.filepath:
            raise ValueError("Save the .blend project before creating render outputs")
        return Path(self.bpy.data.filepath).resolve().parent

    def create_render_job(
        self,
        output_directory: str,
        *,
        frame_start: int,
        frame_end: int,
        frame_step: int,
        preset: str,
        resolution_x: int,
        resolution_y: int,
        resolution_percentage: int,
    ) -> RenderJob:
        scene = self.bpy.context.scene
        if scene.camera is None:
            raise ValueError("Create and activate a camera before rendering")
        return RenderJob(
            project_id=ensure_uuid(scene),
            scene_uuid=ensure_uuid(scene),
            camera_uuid=ensure_uuid(scene.camera),
            frame_start=frame_start,
            frame_end=frame_end,
            frame_step=frame_step,
            engine="BLENDER_EEVEE_NEXT",
            resolution_x=resolution_x,
            resolution_y=resolution_y,
            resolution_percentage=resolution_percentage,
            output_directory=output_directory,
            quality_preset=preset,
        )

    def render(self, job: RenderJob, *, preview: bool = False):
        pipeline = BlenderRenderPipeline(self.bpy, self.project_root())

        def worker(active: RenderJob) -> None:
            validation = pipeline.render(active, preview=preview)
            if not validation.passed:
                raise RuntimeError(
                    f"Missing or invalid frames: {list(validation.missing_frames + validation.invalid_frames)}"
                )

        return self.render_queue.run(job, worker)

    def render_preview_frame(self, output_directory: str, frame: int, *, preset: str = "draft") -> Path:
        job = self.create_render_job(
            output_directory,
            frame_start=frame,
            frame_end=frame,
            frame_step=1,
            preset=preset,
            resolution_x=320,
            resolution_y=180,
            resolution_percentage=100,
        )
        pipeline = BlenderRenderPipeline(self.bpy, self.project_root())
        return pipeline.preview_frame(job, frame)

    def create_studio_lighting(self, target_id: str) -> list[str]:
        target = self.studio.gateway._object(target_id)
        location = tuple(float(item) for item in target.location)
        definitions = (
            ("Studio Key", "key", 900.0, (4.0, -4.0, 5.0), (1.0, 0.82, 0.68, 1.0), 3.0),
            ("Studio Fill", "fill", 420.0, (-4.0, -2.0, 2.5), (0.62, 0.75, 1.0, 1.0), 4.0),
            ("Studio Rim", "rim", 700.0, (0.0, 4.0, 4.5), (1.0, 0.45, 0.22, 1.0), 2.0),
        )
        created: list[str] = []
        from .contracts import ChangeSet

        for name, role, energy, offset, color, size in definitions:
            payload = {
                "schema_version": "1.0",
                "change_set_id": str(uuid.uuid4()),
                "request_id": str(uuid.uuid4()),
                "prompt": "Create deterministic three-point studio lighting",
                "intent": "light.create",
                "scope": {"type": "current_scene", "target_ids": []},
                "operations": [
                    {
                        "tool": "light.create",
                        "target_id": None,
                        "parameters": {
                            "name": name,
                            "type": "AREA",
                            "role": role,
                            "energy": energy,
                            "color": color,
                            "size": size,
                            "location": [location[i] + offset[i] for i in range(3)],
                        },
                    }
                ],
                "preserve": ["camera", "object_animation"],
                "verification": ["requested_state_applied"],
                "risk": "low",
            }
            before = set(obj.name for obj in self.bpy.context.scene.objects)
            self.studio.execute(ChangeSet.from_dict(payload))
            self.last_transactions = self.studio.transactions
            obj = next(obj for obj in self.bpy.context.scene.objects if obj.name not in before)
            created.append(ensure_uuid(obj))
        return created

    def create_and_assign_material(self, target_id: str, preset: str) -> str:
        from .contracts import ChangeSet

        existing = {ensure_uuid(material) for material in self.bpy.data.materials}
        create = ChangeSet.from_dict(
            {
                "schema_version": "1.0",
                "change_set_id": str(uuid.uuid4()),
                "request_id": str(uuid.uuid4()),
                "prompt": f"Create the {preset} material preset",
                "intent": "material.create",
                "scope": {"type": "current_scene", "target_ids": []},
                "operations": [
                    {
                        "tool": "material.create",
                        "target_id": None,
                        "parameters": {"name": f"Vibe {preset.replace('_', ' ').title()}", "preset": preset},
                    }
                ],
                "preserve": ["all_unselected_objects"],
                "verification": ["requested_state_applied"],
                "risk": "low",
            }
        )
        self.studio.execute(create)
        self.last_transactions = self.studio.transactions
        material = next(material for material in self.bpy.data.materials if ensure_uuid(material) not in existing)
        material_id = ensure_uuid(material)
        assign = ChangeSet.from_dict(
            {
                "schema_version": "1.0",
                "change_set_id": str(uuid.uuid4()),
                "request_id": str(uuid.uuid4()),
                "prompt": "Assign the managed material to the selected object",
                "intent": "material.assign",
                "scope": {"type": "selected_object", "target_ids": [target_id]},
                "operations": [
                    {
                        "tool": "material.assign",
                        "target_id": target_id,
                        "parameters": {"material_id": material_id, "slot": 0},
                    }
                ],
                "preserve": ["animation", "all_unselected_objects"],
                "verification": ["requested_state_applied", "preserved_state_unchanged"],
                "risk": "low",
            }
        )
        self.studio.execute(assign)
        self.last_transactions = self.studio.transactions
        return material_id

    def create_hero_camera(self, target_id: str) -> str:
        from .contracts import ChangeSet

        existing = {ensure_uuid(obj) for obj in self.bpy.context.scene.objects}
        change_set = ChangeSet.from_dict(
            {
                "schema_version": "1.0",
                "change_set_id": str(uuid.uuid4()),
                "request_id": str(uuid.uuid4()),
                "prompt": "Create a hero product camera",
                "intent": "camera.create",
                "scope": {"type": "current_scene", "target_ids": []},
                "operations": [
                    {
                        "tool": "camera.create",
                        "target_id": None,
                        "parameters": {
                            "name": "Hero Camera",
                            "preset": "hero_product",
                            "target_id": target_id,
                            "location": [7.5, -9.0, 4.8],
                            "lens": 55.0,
                        },
                    }
                ],
                "preserve": ["lights", "materials", "object_animation"],
                "verification": ["requested_state_applied", "preserved_state_unchanged"],
                "risk": "low",
            }
        )
        self.studio.execute(change_set)
        self.last_transactions = self.studio.transactions
        camera = next(obj for obj in self.bpy.context.scene.objects if ensure_uuid(obj) not in existing)
        camera_id = ensure_uuid(camera)
        activate = replace(
            change_set,
            change_set_id=str(uuid.uuid4()),
            request_id=str(uuid.uuid4()),
            intent="camera.activate",
            operations=(
                change_set.operations[0].__class__(tool="camera.activate", target_id=camera_id, parameters={}),
            ),
        )
        self.studio.execute(activate)
        self.last_transactions = self.studio.transactions
        return camera_id

    def animate_rotation(self, target_id: str, *, frame_start: int, frame_end: int) -> None:
        change_set = interpret_milestone2_prompt(
            f"Rotate the selected object 360 degrees over {(frame_end - frame_start + 1) / self.bpy.context.scene.render.fps:g} seconds.",
            selected_id=target_id,
            fps=int(self.bpy.context.scene.render.fps),
            frame_start=frame_start,
            frame_end=frame_end,
        )
        self.studio.execute(change_set)
        self.last_transactions = self.studio.transactions

    def render_video(self, job: RenderJob, output_path: str = "videos/vibe_animation.mp4") -> dict[str, Any]:
        completed = self.render(job)
        if completed.status != "COMPLETED":
            raise RuntimeError(completed.error_details or "Image-sequence render failed")
        return self.encode_render_job(completed, output_path)

    def encode_render_job(self, completed: RenderJob, output_path: str) -> dict[str, Any]:
        if completed.status != "COMPLETED":
            raise RuntimeError(completed.error_details or "Image-sequence render is not complete")
        root = self.project_root()
        adapter = FFmpegAdapter()
        command = adapter.build_encode_command(
            project_root=root,
            frames_directory=Path(completed.output_directory),
            output_path=Path(output_path),
            fps=float(self.bpy.context.scene.render.fps / self.bpy.context.scene.render.fps_base),
            overwrite=True,
            start_number=completed.frame_start,
        )
        completed.status = "ENCODING"
        adapter.encode(command)
        probe = adapter.probe(project_root=root, video_path=Path(output_path))
        completed.status = "COMPLETED"
        return probe

    def start_background_render(self, job: RenderJob) -> BackgroundRenderSnapshot:
        if not self.bpy.data.filepath:
            raise ValueError("Save the .blend project before starting a background render")
        self.bpy.ops.wm.save_mainfile(filepath=self.bpy.data.filepath)
        runner = BackgroundRenderRunner(
            blender_path=Path(self.bpy.app.binary_path),
            project_root=self.project_root(),
            blend_file=Path(self.bpy.data.filepath),
            worker_script=Path(__file__).with_name("background_worker.py"),
        )
        snapshot = runner.start(job)
        self.background_runner = runner
        self.background_job = job
        return snapshot

    def poll_background_render(self) -> BackgroundRenderSnapshot:
        if self.background_runner is None:
            raise RuntimeError("No background render is active")
        return self.background_runner.poll()

    def cancel_background_render(self) -> BackgroundRenderSnapshot | None:
        if self.background_runner is None or self.background_job is None:
            return None
        if self.background_job.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return self.background_runner.poll()
        return self.background_runner.cancel()

    def finish_background_video(self, output_path: str) -> dict[str, Any]:
        if self.background_job is None:
            raise RuntimeError("No completed background render is available")
        return self.encode_render_job(self.background_job, output_path)

    def inspect(self, assign_missing: bool = False) -> dict[str, Any]:
        self.last_scene_summary = inspect_scene(self.bpy, assign_missing=assign_missing)
        return self.last_scene_summary

    def diagnostics(self, rpc_server: Any) -> Path:
        payload = redact(
            {
                "product_version": DISPLAY_VERSION,
                "upstream_foundation": UPSTREAM_VERSION,
                "upstream_commit": UPSTREAM_COMMIT,
                "protocol_version": PROTOCOL_VERSION,
                "python_version": platform.python_version(),
                "blender_version": self.bpy.app.version_string,
                "connection": {
                    "listener_running": rpc_server.is_listener_healthy(),
                    "authenticated_session": rpc_server.last_authenticated_at is not None,
                    "last_error": rpc_server.last_error,
                },
                "scene": {
                    key: "<redacted>" if key == "filepath" and value else value
                    for key, value in self.inspect().items()
                    if key != "objects"
                },
                "environment": {key: "<set>" for key in os.environ if "PROXY" in key.upper()},
            }
        )
        path = Path(tempfile.gettempdir()) / f"vibe-diagnostics-{int(time.time())}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def identity_report(self) -> dict[str, Any]:
        return validation_report(self.bpy.context.scene.objects)

    def repair_identities(self) -> dict[str, str]:
        return repair_duplicates(self.bpy.context.scene.objects)
