"""Non-blocking Blender child-process render orchestration."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .media_contracts import (
    MAX_BLENDER_RENDER_TIMEOUT_SECONDS,
    RenderJob,
    RenderSafetyError,
    safe_output_path,
    validate_frame_sequence,
)

BACKGROUND_MANIFEST_SCHEMA = "1.0"


@dataclass(frozen=True)
class BackgroundRenderSnapshot:
    job_id: str
    status: str
    progress: float
    exit_code: int | None
    valid_frames: tuple[int, ...]
    missing_frames: tuple[int, ...]
    stderr_path: str
    error: str | None = None


class BackgroundRenderRunner:
    """Manage one bounded Blender child process without blocking the UI thread."""

    def __init__(
        self,
        *,
        blender_path: Path,
        project_root: Path,
        blend_file: Path,
        worker_script: Path,
        popen_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        clock: Callable[[], float] = time.monotonic,
        stall_timeout: float = 300.0,
    ):
        self.blender_path = blender_path.resolve()
        self.project_root = project_root.resolve()
        self.blend_file = blend_file.resolve()
        self.worker_script = worker_script.resolve()
        self.popen_factory = popen_factory
        self.clock = clock
        self.stall_timeout = min(stall_timeout, float(MAX_BLENDER_RENDER_TIMEOUT_SECONDS))
        self.process: subprocess.Popen[str] | None = None
        self.job: RenderJob | None = None
        self.manifest_path: Path | None = None
        self.stderr_path: Path | None = None
        self.result_path: Path | None = None
        self._stderr_handle: Any = None
        self._started_at = 0.0
        self._last_progress_at = 0.0
        self._last_valid_count = 0
        self._exit_code: int | None = None

    def _validate_runtime_paths(self) -> None:
        if not self.blender_path.is_file():
            raise RenderSafetyError(f"Blender executable is unavailable: {self.blender_path}")
        if not self.worker_script.is_file():
            raise RenderSafetyError(f"Background render worker is unavailable: {self.worker_script}")
        if not self.blend_file.is_file() or self.project_root not in self.blend_file.parents:
            raise RenderSafetyError("Background rendering requires a saved project inside the approved project root")

    def start(self, job: RenderJob, *, resume: bool = False) -> BackgroundRenderSnapshot:
        if self.process is not None and self.process.poll() is None:
            raise RenderSafetyError("Another background render job is already active")
        self._validate_runtime_paths()
        job.validate()
        output = safe_output_path(self.project_root, job.output_directory)
        output.mkdir(parents=True, exist_ok=True)
        self.manifest_path = output / "background_job.json"
        self.stderr_path = output / "background_render.stderr.log"
        self.result_path = output / "background_result.json"
        if self.manifest_path.is_file():
            previous = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if previous.get("job", {}).get("job_id") == job.job_id and previous.get("runner_status") in {
                "PREPARING",
                "RENDERING",
                "CANCELLING",
            }:
                raise RenderSafetyError("This render job is already marked active; recover it before restarting")
        payload = {
            "schema_version": BACKGROUND_MANIFEST_SCHEMA,
            "runner_status": "PREPARING",
            "job": job.to_dict(),
            "project_root": str(self.project_root),
            "blend_file": str(self.blend_file),
            "result_path": str(self.result_path),
            "resume": resume,
        }
        self.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._stderr_handle = self.stderr_path.open("w", encoding="utf-8")
        command = [
            str(self.blender_path),
            "--background",
            str(self.blend_file),
            "--python",
            str(self.worker_script),
            "--",
            str(self.manifest_path),
        ]
        environment = dict(os.environ)
        environment.setdefault("VIBE_RENDER_ENGINE_OVERRIDE", "CYCLES")
        self.process = self.popen_factory(
            command,
            cwd=str(self.project_root),
            env=environment,
            stdout=self._stderr_handle,
            stderr=subprocess.STDOUT,
            text=True,
            shell=False,
        )
        self.job = job
        self.job.status = "RENDERING"
        self.job.started_time = time.time()
        self._started_at = self.clock()
        self._last_progress_at = self._started_at
        self._last_valid_count = 0
        self._exit_code = None
        return self.poll()

    def _write_runner_status(self, status: str, error: str | None = None) -> None:
        if self.manifest_path is None or not self.manifest_path.is_file():
            return
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        payload["runner_status"] = status
        payload["runner_exit_code"] = self._exit_code
        payload["runner_error"] = error
        self.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def poll(self) -> BackgroundRenderSnapshot:
        if self.job is None or self.process is None or self.stderr_path is None:
            raise RenderSafetyError("No background render job is active")
        output = safe_output_path(self.project_root, self.job.output_directory)
        validation = validate_frame_sequence(output, self.job.expected_frames)
        valid_count = len(validation.valid_frames)
        if valid_count > self._last_valid_count:
            self._last_valid_count = valid_count
            self._last_progress_at = self.clock()
        self.job.progress = valid_count / max(1, len(self.job.expected_frames))
        exit_code = self.process.poll()
        error: str | None = None
        if exit_code is None and self.clock() - self._last_progress_at > self.stall_timeout:
            error = f"Background Blender process stalled for more than {self.stall_timeout:g} seconds"
            self._terminate(grace_seconds=2.0)
            exit_code = self.process.poll()
            self.job.status = "FAILED"
        elif exit_code is not None:
            self._exit_code = exit_code
            if self._stderr_handle is not None and not self._stderr_handle.closed:
                self._stderr_handle.close()
            if self.job.cancellation_requested:
                self.job.status = "CANCELLED"
            elif exit_code != 0:
                self.job.status = "FAILED"
                error = f"Background Blender exited with code {exit_code}"
            elif validation.passed:
                self.job.status = "COMPLETED"
                self.job.progress = 1.0
            else:
                self.job.status = "FAILED"
                error = f"Background render completed with missing frames: {list(validation.missing_frames)}"
            self.job.finished_time = time.time()
        else:
            self.job.status = "RENDERING"
        self.job.error_details = error
        self._write_runner_status(self.job.status, error)
        return BackgroundRenderSnapshot(
            job_id=self.job.job_id,
            status=self.job.status,
            progress=self.job.progress,
            exit_code=self._exit_code,
            valid_frames=validation.valid_frames,
            missing_frames=validation.missing_frames,
            stderr_path=str(self.stderr_path),
            error=error,
        )

    def _terminate(self, *, grace_seconds: float) -> bool:
        if self.process is None or self.process.poll() is not None:
            return False
        self.process.terminate()
        try:
            self.process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5.0)
        self._exit_code = self.process.returncode
        if self._stderr_handle is not None and not self._stderr_handle.closed:
            self._stderr_handle.close()
        return True

    def cancel(self, *, grace_seconds: float = 5.0) -> BackgroundRenderSnapshot:
        if self.job is None:
            raise RenderSafetyError("No background render job is active")
        self.job.cancellation_requested = True
        self.job.status = "CANCELLING"
        self._write_runner_status("CANCELLING")
        self._terminate(grace_seconds=grace_seconds)
        self.job.status = "CANCELLED"
        self.job.finished_time = time.time()
        return self.poll()

    def resume(self, job: RenderJob) -> BackgroundRenderSnapshot:
        return self.start(job, resume=True)

    def recover_stale(self, manifest_path: Path) -> dict[str, Any]:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("runner_status") not in {"PREPARING", "RENDERING", "CANCELLING"}:
            return manifest
        manifest["runner_status"] = "FAILED"
        manifest["runner_error"] = "Recovered stale background job after its child process was lost"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return manifest

    def cleanup_owned_files(self) -> list[Path]:
        if self.job is None:
            return []
        output = safe_output_path(self.project_root, self.job.output_directory)
        owned = [output / f"frame_{frame:06d}.png" for frame in self.job.expected_frames]
        owned.extend(path for path in (self.manifest_path, self.result_path, self.stderr_path) if path is not None)
        removed: list[Path] = []
        for path in owned:
            if path.is_file():
                path.unlink()
                removed.append(path)
        return removed
