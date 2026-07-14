#!/usr/bin/env python3
"""Execute a real non-blocking Blender child-process render acceptance."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from blender_addon.vibe_studio.background_render import BackgroundRenderRunner  # noqa: E402
from blender_addon.vibe_studio.media_contracts import RenderJob  # noqa: E402


def blender_path(root: Path, explicit: str | None) -> Path:
    candidates = [
        explicit,
        os.environ.get("BLENDER_PATH"),
        "/tmp/vibe-blender-runtime/blender-4.2.15-linux-x64/blender",
        str(root / ".runtime/blender/blender-4.2.15-linux-x64/blender"),
    ]
    for item in candidates:
        if item and Path(item).is_file():
            return Path(item).resolve()
    raise FileNotFoundError("Blender 4.2.15 was not found; run scripts/install_blender_ci.sh first")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender")
    args = parser.parse_args()
    root = ROOT
    output = root / "outputs/milestone2_1"
    output.mkdir(parents=True, exist_ok=True)
    blend = output / "background_acceptance.blend"
    blender = blender_path(root, args.blender)
    setup_log = output / "background_setup.log"
    with setup_log.open("w", encoding="utf-8") as log:
        setup = subprocess.run(
            [
                str(blender),
                "--background",
                "--factory-startup",
                "--python",
                str(root / "tests/blender_real/background_render_setup.py"),
                "--",
                str(blend),
            ],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=120,
        )
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, expected: object, actual: object) -> None:
        checks.append({"name": name, "passed": passed, "expected": expected, "actual": actual})

    check("setup_exit", setup.returncode == 0, 0, setup.returncode)
    check("blend_created", blend.is_file(), True, blend.is_file())
    if setup.returncode != 0 or not blend.is_file():
        result = {"passed": False, "checks": checks, "setup_log": str(setup_log)}
        (output / "background_acceptance.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 1
    job = RenderJob(
        project_id=str(uuid.uuid4()),
        scene_uuid=str(uuid.uuid4()),
        camera_uuid=str(uuid.uuid4()),
        frame_start=1,
        frame_end=3,
        frame_step=1,
        engine="CYCLES",
        resolution_x=160,
        resolution_y=90,
        resolution_percentage=100,
        output_directory="milestone2_1/background_frames",
        quality_preset="draft",
    )
    frame_output = root / "outputs" / job.output_directory
    for owned_name in (
        *(f"frame_{frame:06d}.png" for frame in job.expected_frames),
        "background_job.json",
        "background_result.json",
        "background_render.stderr.log",
        "render_job.json",
        "frame_validation.json",
    ):
        owned = frame_output / owned_name
        if owned.is_file():
            owned.unlink()
    runner = BackgroundRenderRunner(
        blender_path=blender,
        project_root=root,
        blend_file=blend,
        worker_script=root / "blender_addon/vibe_studio/background_worker.py",
        stall_timeout=120.0,
    )
    started_at = time.monotonic()
    first = runner.start(job)
    launch_duration = time.monotonic() - started_at
    check("non_blocking_launch", launch_duration < 2.0, "<2 seconds", launch_duration)
    check("child_running", first.status == "RENDERING", "RENDERING", first.status)
    progress_samples = [first.progress]
    deadline = time.monotonic() + 180
    snapshot = first
    while snapshot.status == "RENDERING" and time.monotonic() < deadline:
        time.sleep(0.2)
        snapshot = runner.poll()
        progress_samples.append(snapshot.progress)
    if snapshot.status == "RENDERING":
        snapshot = runner.cancel(grace_seconds=2.0)
    check("completed", snapshot.status == "COMPLETED", "COMPLETED", snapshot.status)
    check("exit_code", snapshot.exit_code == 0, 0, snapshot.exit_code)
    check("all_frames", len(snapshot.valid_frames) == 3, 3, len(snapshot.valid_frames))
    check("progress_reported", max(progress_samples) == 1.0, 1.0, max(progress_samples))
    check("stderr_recorded", Path(snapshot.stderr_path).is_file(), True, Path(snapshot.stderr_path).is_file())
    result = {
        "passed": all(bool(item["passed"]) for item in checks),
        "blender": str(blender),
        "blend_artifact": str(blend),
        "manifest": str(runner.manifest_path),
        "stderr": snapshot.stderr_path,
        "progress_samples": progress_samples,
        "checks": checks,
    }
    result_path = output / "background_acceptance.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
