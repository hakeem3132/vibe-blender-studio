"""Typed render jobs, output safety and frame-sequence validation."""

from __future__ import annotations

import json
import shutil
import struct
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

RenderStatus = Literal[
    "QUEUED",
    "PREPARING",
    "RENDERING",
    "CANCELLING",
    "CANCELLED",
    "FAILED",
    "COMPLETED",
    "VALIDATING",
    "ENCODING",
]

MAX_PREVIEW_FRAMES = 240
MAX_FINAL_FRAMES = 10000
MAX_RESOLUTION = 8192
MAX_RESOLUTION_PERCENTAGE = 100
MAX_OUTPUT_PATH_LENGTH = 1024
MAX_SIMULTANEOUS_RENDER_JOBS = 1
MAX_FFMPEG_TIMEOUT_SECONDS = 3600
MAX_BLENDER_RENDER_TIMEOUT_SECONDS = 7200
MIN_FREE_DISK_BYTES = 128 * 1024 * 1024


class RenderSafetyError(ValueError):
    """A render or output request violated a bounded safety policy."""


def safe_output_path(project_root: Path, requested: Path | str, *, allow_existing: bool = True) -> Path:
    root = project_root.expanduser().resolve()
    output_root = (root / "outputs").resolve()
    raw = Path(requested).expanduser()
    candidate = (output_root / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if len(str(candidate)) > MAX_OUTPUT_PATH_LENGTH:
        raise RenderSafetyError("Output path exceeds the configured length limit")
    if candidate != output_root and output_root not in candidate.parents:
        raise RenderSafetyError("Output must remain inside the approved project outputs directory")
    if any(part in {".git", ".hg", ".svn"} for part in candidate.parts):
        raise RenderSafetyError("Repository metadata is not a permitted output location")
    if candidate.exists() and not allow_existing:
        raise RenderSafetyError("Output already exists; explicit overwrite confirmation is required")
    return candidate


def validate_render_bounds(
    *,
    frame_start: int,
    frame_end: int,
    frame_step: int,
    resolution_x: int,
    resolution_y: int,
    resolution_percentage: int,
    preview: bool,
) -> int:
    if frame_start < 1 or frame_end < frame_start or frame_step < 1:
        raise RenderSafetyError("Frame range and step must be positive and ordered")
    count = ((frame_end - frame_start) // frame_step) + 1
    limit = MAX_PREVIEW_FRAMES if preview else MAX_FINAL_FRAMES
    if count > limit:
        raise RenderSafetyError(f"Render requests are limited to {limit} frames")
    if not 16 <= resolution_x <= MAX_RESOLUTION or not 16 <= resolution_y <= MAX_RESOLUTION:
        raise RenderSafetyError(f"Resolution must be between 16 and {MAX_RESOLUTION} pixels per dimension")
    if not 1 <= resolution_percentage <= MAX_RESOLUTION_PERCENTAGE:
        raise RenderSafetyError("Resolution percentage must be between 1 and 100")
    return count


@dataclass
class RenderJob:
    project_id: str
    scene_uuid: str
    camera_uuid: str
    frame_start: int
    frame_end: int
    frame_step: int
    engine: str
    resolution_x: int
    resolution_y: int
    resolution_percentage: int
    output_directory: str
    image_format: str = "PNG"
    quality_preset: str = "preview"
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: RenderStatus = "QUEUED"
    progress: float = 0.0
    started_time: float | None = None
    finished_time: float | None = None
    failed_frames: list[int] = field(default_factory=list)
    cancellation_requested: bool = False
    error_details: str | None = None
    created_files: list[str] = field(default_factory=list)

    def validate(self, *, preview: bool = False) -> int:
        for field_name in ("project_id", "scene_uuid", "camera_uuid", "job_id"):
            try:
                uuid.UUID(str(getattr(self, field_name)))
            except (TypeError, ValueError, AttributeError) as exc:
                raise RenderSafetyError(f"{field_name} must be a valid UUID") from exc
        if self.image_format != "PNG":
            raise RenderSafetyError("Milestone 2 image sequences use PNG")
        if self.engine not in {"BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH", "CYCLES"}:
            raise RenderSafetyError("Render engine is not allowlisted")
        if self.quality_preset not in {"draft", "preview", "balanced", "high", "custom"}:
            raise RenderSafetyError("Render quality preset is not allowlisted")
        return validate_render_bounds(
            frame_start=self.frame_start,
            frame_end=self.frame_end,
            frame_step=self.frame_step,
            resolution_x=self.resolution_x,
            resolution_y=self.resolution_y,
            resolution_percentage=self.resolution_percentage,
            preview=preview,
        )

    @property
    def expected_frames(self) -> list[int]:
        return list(range(self.frame_start, self.frame_end + 1, self.frame_step))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_manifest(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


@dataclass(frozen=True)
class FrameValidation:
    passed: bool
    expected_count: int
    valid_frames: tuple[int, ...]
    missing_frames: tuple[int, ...]
    invalid_frames: tuple[int, ...]
    dimensions: tuple[int, int] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise RenderSafetyError(f"Unreadable PNG frame: {path.name}")
    return struct.unpack(">II", header[16:24])


def validate_frame_sequence(directory: Path, expected_frames: list[int]) -> FrameValidation:
    valid: list[int] = []
    missing: list[int] = []
    invalid: list[int] = []
    dimensions: tuple[int, int] | None = None
    for frame in expected_frames:
        path = directory / f"frame_{frame:06d}.png"
        if not path.is_file():
            missing.append(frame)
            continue
        try:
            current = png_dimensions(path)
            if path.stat().st_size == 0 or (dimensions is not None and current != dimensions):
                invalid.append(frame)
                continue
            dimensions = dimensions or current
            valid.append(frame)
        except (OSError, RenderSafetyError):
            invalid.append(frame)
    return FrameValidation(
        passed=not missing and not invalid and len(valid) == len(expected_frames),
        expected_count=len(expected_frames),
        valid_frames=tuple(valid),
        missing_frames=tuple(missing),
        invalid_frames=tuple(invalid),
        dimensions=dimensions,
    )


class RenderJobQueue:
    """One-active-job local queue with cooperative cancellation."""

    def __init__(self, maximum_jobs: int = MAX_SIMULTANEOUS_RENDER_JOBS):
        if maximum_jobs != 1:
            raise RenderSafetyError("Milestone 2 permits one active local render job")
        self.maximum_jobs = maximum_jobs
        self.active: RenderJob | None = None
        self.history: list[RenderJob] = []
        self._lock = threading.Lock()

    def run(self, job: RenderJob, worker: Callable[[RenderJob], None]) -> RenderJob:
        with self._lock:
            if self.active is not None:
                raise RenderSafetyError("Another render job is already active")
            job.validate()
            self.active = job
            self.history.append(job)
        job.status = "PREPARING"
        job.started_time = time.time()
        try:
            if job.cancellation_requested:
                job.status = "CANCELLED"
                return job
            job.status = "RENDERING"
            worker(job)
            job.status = "CANCELLED" if job.cancellation_requested else "COMPLETED"
            job.progress = 1.0 if job.status == "COMPLETED" else job.progress
        except Exception as exc:
            job.status = "FAILED"
            job.error_details = str(exc)
        finally:
            job.finished_time = time.time()
            with self._lock:
                self.active = None
        return job

    def cancel(self) -> bool:
        with self._lock:
            if self.active is None:
                return False
            self.active.cancellation_requested = True
            self.active.status = "CANCELLING"
            return True


def environment_doctor(
    project_root: Path, *, blender: str | None, ffmpeg: str | None, ffprobe: str | None
) -> dict[str, Any]:
    output_root = (project_root / "outputs").resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(output_root)
    return {
        "blender": {"status": "available" if blender else "unavailable", "path": blender},
        "ffmpeg": {"status": "available" if ffmpeg else "unavailable", "path": ffmpeg},
        "ffprobe": {"status": "available" if ffprobe else "unavailable", "path": ffprobe},
        "output_directory": {
            "status": "available" if output_root.is_dir() else "unavailable",
            "path": str(output_root),
            "free_bytes": disk.free,
            "minimum_free_bytes": MIN_FREE_DISK_BYTES,
        },
    }
