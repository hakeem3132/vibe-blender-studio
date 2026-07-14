from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

import pytest
from blender_addon.vibe_studio.background_render import BackgroundRenderRunner
from blender_addon.vibe_studio.media_contracts import RenderJob, RenderSafetyError


class FakeProcess:
    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.returncode = None
        self.terminated = False
        self.killed = False
        self.force_timeout = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        if not self.force_timeout:
            self.returncode = -15

    def wait(self, timeout=None):
        if self.force_timeout and not self.killed:
            raise subprocess.TimeoutExpired(self.command, timeout)
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def _png(path: Path, width: int = 32, height: int = 18) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")
    )


def _job(output: str = "frames/background") -> RenderJob:
    return RenderJob(
        project_id=str(uuid.uuid4()),
        scene_uuid=str(uuid.uuid4()),
        camera_uuid=str(uuid.uuid4()),
        frame_start=1,
        frame_end=3,
        frame_step=1,
        engine="CYCLES",
        resolution_x=32,
        resolution_y=18,
        resolution_percentage=100,
        output_directory=output,
        quality_preset="draft",
    )


def _runner(tmp_path: Path, *, clock=lambda: 1.0):
    blender = tmp_path / "blender"
    blender.write_text("binary", encoding="utf-8")
    worker = tmp_path / "background_worker.py"
    worker.write_text("worker", encoding="utf-8")
    blend = tmp_path / "project.blend"
    blend.write_text("blend", encoding="utf-8")
    processes = []

    def factory(command, **kwargs):
        process = FakeProcess(command, **kwargs)
        processes.append(process)
        return process

    return (
        BackgroundRenderRunner(
            blender_path=blender,
            project_root=tmp_path,
            blend_file=blend,
            worker_script=worker,
            popen_factory=factory,
            clock=clock,
            stall_timeout=10.0,
        ),
        processes,
    )


def test_background_success_and_progress(tmp_path):
    runner, processes = _runner(tmp_path)
    job = _job()
    start = runner.start(job)
    assert start.status == "RENDERING"
    assert processes[0].kwargs["shell"] is False
    assert isinstance(processes[0].command, list)
    _png(tmp_path / "outputs/frames/background/frame_000001.png")
    assert runner.poll().progress == pytest.approx(1 / 3)
    _png(tmp_path / "outputs/frames/background/frame_000002.png")
    _png(tmp_path / "outputs/frames/background/frame_000003.png")
    processes[0].returncode = 0
    completed = runner.poll()
    assert completed.status == "COMPLETED"
    assert completed.exit_code == 0


def test_cancel_preserves_completed_frames(tmp_path):
    runner, processes = _runner(tmp_path)
    runner.start(_job())
    frame = tmp_path / "outputs/frames/background/frame_000001.png"
    _png(frame)
    cancelled = runner.cancel()
    assert cancelled.status == "CANCELLED"
    assert processes[0].terminated
    assert frame.is_file()


def test_cancel_forces_kill_after_grace_timeout(tmp_path):
    runner, processes = _runner(tmp_path)
    runner.start(_job())
    processes[0].force_timeout = True
    runner.cancel(grace_seconds=0.01)
    assert processes[0].terminated
    assert processes[0].killed


def test_child_failure_records_exit_code_and_stderr(tmp_path):
    runner, processes = _runner(tmp_path)
    runner.start(_job())
    processes[0].returncode = 7
    snapshot = runner.poll()
    assert snapshot.status == "FAILED"
    assert snapshot.exit_code == 7
    assert "code 7" in (snapshot.error or "")
    assert Path(snapshot.stderr_path).is_file()


def test_successful_child_with_missing_frames_fails(tmp_path):
    runner, processes = _runner(tmp_path)
    runner.start(_job())
    processes[0].returncode = 0
    snapshot = runner.poll()
    assert snapshot.status == "FAILED"
    assert snapshot.missing_frames == (1, 2, 3)


def test_resume_sets_manifest_and_rejects_duplicate_active_job(tmp_path):
    runner, _ = _runner(tmp_path)
    job = _job()
    runner.resume(job)
    manifest = json.loads((tmp_path / "outputs/frames/background/background_job.json").read_text())
    assert manifest["resume"] is True
    with pytest.raises(RenderSafetyError, match="active"):
        runner.start(job)


def test_stale_job_recovery(tmp_path):
    runner, _ = _runner(tmp_path)
    manifest = tmp_path / "stale.json"
    manifest.write_text(json.dumps({"runner_status": "RENDERING"}), encoding="utf-8")
    recovered = runner.recover_stale(manifest)
    assert recovered["runner_status"] == "FAILED"
    assert "stale" in recovered["runner_error"]


def test_stalled_process_is_terminated(tmp_path):
    now = [0.0]
    runner, processes = _runner(tmp_path, clock=lambda: now[0])
    runner.start(_job())
    now[0] = 11.0
    snapshot = runner.poll()
    assert snapshot.status == "FAILED"
    assert processes[0].terminated
    assert "stalled" in (snapshot.error or "")


def test_unsafe_output_is_rejected_before_process_start(tmp_path):
    runner, processes = _runner(tmp_path)
    with pytest.raises(RenderSafetyError, match="approved"):
        runner.start(_job("../escape"))
    assert processes == []


def test_cleanup_removes_only_job_owned_files(tmp_path):
    runner, processes = _runner(tmp_path)
    runner.start(_job())
    output = tmp_path / "outputs/frames/background"
    _png(output / "frame_000001.png")
    unrelated = output / "artist-notes.txt"
    unrelated.write_text("keep", encoding="utf-8")
    processes[0].returncode = 7
    runner.poll()
    removed = runner.cleanup_owned_files()
    assert output / "frame_000001.png" in removed
    assert unrelated.is_file()
