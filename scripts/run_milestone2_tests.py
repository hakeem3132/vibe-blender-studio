#!/usr/bin/env python3
"""Run the real Milestone 2 animation, render, encode and reopen acceptance."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from find_blender import find_blender  # noqa: E402


def _run(command: list[str], log: Path, environment: dict[str, str], timeout: int = 600) -> int:
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout,
        )
    return result.returncode


def main() -> int:
    blender = find_blender()
    if blender is None:
        print("BLOCKED: Blender 4.2.15 not found")
        return 2
    output = ROOT / "outputs/blender_real/milestone2"
    output.mkdir(parents=True, exist_ok=True)
    home = ROOT / ".runtime/blender-home-milestone2"
    archive = ROOT / "outputs/blender_ai_mcp.zip"
    environment = {
        **os.environ,
        "BLENDER_USER_CONFIG": str(home / "config"),
        "BLENDER_USER_SCRIPTS": str(home / "scripts"),
        "BLENDER_USER_DATAFILES": str(home / "datafiles"),
        "VIBE_BACKEND_PYTHON": sys.executable,
        "VIBE_REPOSITORY_ROOT": str(ROOT),
        "VIBE_RPC_SESSION_DIR": str(home / "session"),
        "VIBE_RENDER_ENGINE_OVERRIDE": "CYCLES",
        "PYTHONPATH": str(ROOT),
    }
    blend = output / "milestone2_acceptance.blend"
    result_path = output / "milestone2_acceptance.json"
    diagnostics = output / "milestone2_diagnostics.json"
    stage_one = _run(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--python",
            str(ROOT / "tests/blender_real/milestone_2_acceptance.py"),
            "--",
            str(archive),
            str(blend),
            str(result_path),
            str(diagnostics),
        ],
        output / "milestone2_stage1.log",
        environment,
    )
    if stage_one != 0 or not result_path.is_file():
        print(f"Milestone 2 stage one failed: exit {stage_one}")
        return 1
    stage_two = _run(
        [
            str(blender),
            "--background",
            str(blend),
            "--addons",
            "blender_ai_mcp",
            "--python",
            str(ROOT / "tests/blender_real/milestone_2_reopen.py"),
            "--",
            str(result_path),
            str(diagnostics),
        ],
        output / "milestone2_stage2.log",
        environment,
    )
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    passed = stage_two == 0 and bool(payload.get("passed"))
    print(
        json.dumps({"passed": passed, "checks": len(payload.get("checks", [])), "result": str(result_path)}, indent=2)
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
