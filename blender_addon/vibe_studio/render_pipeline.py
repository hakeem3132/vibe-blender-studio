"""Bounded Blender image-sequence rendering with restorable preview settings."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .media_contracts import (
    MIN_FREE_DISK_BYTES,
    FrameValidation,
    RenderJob,
    RenderSafetyError,
    safe_output_path,
    validate_frame_sequence,
)


@dataclass(frozen=True)
class RenderPreset:
    name: str
    engine: str
    resolution_x: int
    resolution_y: int
    percentage: int
    samples: int


RENDER_PRESETS: dict[str, RenderPreset] = {
    "draft": RenderPreset("draft", "BLENDER_EEVEE_NEXT", 320, 180, 50, 1),
    "preview": RenderPreset("preview", "BLENDER_EEVEE_NEXT", 640, 360, 50, 8),
    "balanced": RenderPreset("balanced", "BLENDER_EEVEE_NEXT", 1280, 720, 50, 32),
    "high": RenderPreset("high", "BLENDER_EEVEE_NEXT", 1920, 1080, 100, 64),
}


def _snapshot_settings(scene: Any) -> dict[str, Any]:
    image = scene.render.image_settings
    eevee = getattr(scene, "eevee", None)
    return {
        "engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "filepath": scene.render.filepath,
        "file_format": image.file_format,
        "color_mode": image.color_mode,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "frame_step": scene.frame_step,
        "frame_current": scene.frame_current,
        "samples": getattr(eevee, "taa_render_samples", None),
        "cycles_samples": getattr(getattr(scene, "cycles", None), "samples", None),
    }


def _restore_settings(scene: Any, state: dict[str, Any]) -> None:
    scene.render.engine = state["engine"]
    scene.render.resolution_x = state["resolution_x"]
    scene.render.resolution_y = state["resolution_y"]
    scene.render.resolution_percentage = state["resolution_percentage"]
    scene.render.filepath = state["filepath"]
    scene.render.image_settings.file_format = state["file_format"]
    scene.render.image_settings.color_mode = state["color_mode"]
    scene.frame_start = state["frame_start"]
    scene.frame_end = state["frame_end"]
    scene.frame_step = state["frame_step"]
    scene.frame_set(state["frame_current"])
    if state["samples"] is not None and getattr(scene, "eevee", None) is not None:
        scene.eevee.taa_render_samples = state["samples"]
    if state["cycles_samples"] is not None and getattr(scene, "cycles", None) is not None:
        scene.cycles.samples = state["cycles_samples"]


class BlenderRenderPipeline:
    """Execute only bounded, camera-backed renders on Blender's main thread."""

    def __init__(self, bpy_module: Any, project_root: Path):
        self.bpy = bpy_module
        self.project_root = project_root.resolve()

    def _configure(self, preset_name: str, job: RenderJob) -> None:
        scene = self.bpy.context.scene
        preset = RENDER_PRESETS.get(preset_name)
        if preset is None and preset_name != "custom":
            raise RenderSafetyError(f"Unknown render preset: {preset_name}")
        engine_override = os.environ.get("VIBE_RENDER_ENGINE_OVERRIDE")
        if engine_override and engine_override not in {"CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"}:
            raise RenderSafetyError("VIBE_RENDER_ENGINE_OVERRIDE is not allowlisted")
        if engine_override:
            scene.render.engine = engine_override
        elif preset_name == "custom":
            scene.render.engine = job.engine
        else:
            assert preset is not None
            scene.render.engine = preset.engine
        scene.render.resolution_x = job.resolution_x
        scene.render.resolution_y = job.resolution_y
        scene.render.resolution_percentage = job.resolution_percentage
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        if preset is not None and hasattr(scene, "eevee"):
            scene.eevee.taa_render_samples = preset.samples
        if preset is not None and scene.render.engine == "CYCLES" and hasattr(scene, "cycles"):
            scene.cycles.samples = preset.samples
            scene.cycles.use_denoising = False

    def _check(self, job: RenderJob, *, preview: bool) -> Path:
        job.validate(preview=preview)
        scene = self.bpy.context.scene
        if scene.camera is None:
            raise RenderSafetyError("An active camera is required before rendering")
        output = safe_output_path(self.project_root, job.output_directory)
        output.mkdir(parents=True, exist_ok=True)
        if output.stat().st_dev != self.project_root.stat().st_dev:
            raise RenderSafetyError("Output directory must use the approved project filesystem")
        import shutil

        if shutil.disk_usage(output).free < MIN_FREE_DISK_BYTES:
            raise RenderSafetyError("Insufficient free disk space for the bounded render job")
        return output

    def render(
        self,
        job: RenderJob,
        *,
        preview: bool = False,
        only_frames: list[int] | None = None,
        progress: Callable[[float], None] | None = None,
    ) -> FrameValidation:
        output = self._check(job, preview=preview)
        scene = self.bpy.context.scene
        settings = _snapshot_settings(scene)
        frames = only_frames if only_frames is not None else job.expected_frames
        expected = job.expected_frames
        job.status = "RENDERING"
        job.started_time = job.started_time or time.time()
        try:
            self._configure(job.quality_preset, job)
            scene.frame_start = job.frame_start
            scene.frame_end = job.frame_end
            scene.frame_step = job.frame_step
            for index, frame in enumerate(frames, start=1):
                if job.cancellation_requested:
                    job.status = "CANCELLED"
                    break
                scene.frame_set(frame)
                destination = output / f"frame_{frame:06d}.png"
                scene.render.filepath = str(destination)
                self.bpy.ops.render.render(write_still=True)
                if not destination.is_file() or destination.stat().st_size == 0:
                    job.failed_frames.append(frame)
                else:
                    job.created_files.append(str(destination))
                job.progress = index / len(frames)
                if progress:
                    progress(job.progress)
            validation = validate_frame_sequence(output, expected)
            job.failed_frames = sorted(set(validation.missing_frames + validation.invalid_frames))
            if not job.cancellation_requested:
                job.status = "COMPLETED" if validation.passed else "FAILED"
            job.error_details = None if validation.passed else f"Invalid or missing frames: {job.failed_frames}"
            return validation
        finally:
            job.finished_time = time.time()
            _restore_settings(scene, settings)
            job.write_manifest(output / "render_job.json")
            (output / "frame_validation.json").write_text(
                json.dumps(asdict(validate_frame_sequence(output, expected)), indent=2), encoding="utf-8"
            )

    def resume_missing(self, job: RenderJob, *, preview: bool = False) -> FrameValidation:
        output = self._check(job, preview=preview)
        validation = validate_frame_sequence(output, job.expected_frames)
        missing = sorted(set(validation.missing_frames + validation.invalid_frames))
        if not missing:
            return validation
        for frame in validation.invalid_frames:
            invalid_path = output / f"frame_{frame:06d}.png"
            if invalid_path.is_file() and str(invalid_path) in job.created_files:
                invalid_path.unlink()
        return self.render(job, preview=preview, only_frames=missing)

    def preview_frame(self, job: RenderJob, frame: int) -> Path:
        if frame not in job.expected_frames:
            raise RenderSafetyError("Preview frame is outside the bounded job range")
        validation = self.render(job, preview=True, only_frames=[frame])
        path = safe_output_path(self.project_root, job.output_directory) / f"frame_{frame:06d}.png"
        if frame not in validation.valid_frames:
            raise RenderSafetyError("Preview frame did not render successfully")
        return path
