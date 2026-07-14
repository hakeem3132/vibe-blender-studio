"""Blender-side worker invoked only by the bounded background runner."""

from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any


def _modules() -> tuple[Any, Any]:
    package_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(package_root.parent))
    package = package_root.name
    contracts = importlib.import_module(f"{package}.vibe_studio.media_contracts")
    pipeline = importlib.import_module(f"{package}.vibe_studio.render_pipeline")
    return contracts, pipeline


def _manifest_argument() -> Path:
    if "--" not in sys.argv:
        raise RuntimeError("Background render worker requires a manifest argument")
    values = sys.argv[sys.argv.index("--") + 1 :]
    if len(values) != 1:
        raise RuntimeError("Background render worker accepts exactly one manifest")
    return Path(values[0]).resolve()


def main() -> int:
    import bpy

    contracts, pipeline_module = _modules()
    manifest_path = _manifest_argument()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise RuntimeError("Unsupported background render manifest schema")
    project_root = Path(payload["project_root"]).resolve()
    if manifest_path.parent != contracts.safe_output_path(project_root, payload["job"]["output_directory"]):
        raise contracts.RenderSafetyError("Background manifest is outside the approved job output directory")
    job = contracts.RenderJob(**payload["job"])
    job.validate()
    payload["runner_status"] = "RENDERING"
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    renderer = pipeline_module.BlenderRenderPipeline(bpy, project_root)
    validation = renderer.resume_missing(job) if payload.get("resume") else renderer.render(job)
    result = {
        "schema_version": "1.0",
        "job": job.to_dict(),
        "validation": validation.to_dict(),
        "blender_version": bpy.app.version_string,
        "finished_at": time.time(),
    }
    Path(payload["result_path"]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if validation.passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
