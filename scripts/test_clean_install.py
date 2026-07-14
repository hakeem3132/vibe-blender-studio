#!/usr/bin/env python3
"""Exercise the complete no-index clean-install gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from install_offline import environment_python


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("--profile", choices=("core", "development"), default="core")
    parser.add_argument("--output", type=Path, default=Path("outputs/milestone2_1/clean-install.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="vibe-offline-install-") as temp:
        environment = Path(temp) / "environment"
        install = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/install_offline.py"),
                str(args.wheelhouse),
                str(environment),
                "--profile",
                args.profile,
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "PIP_INDEX_URL": "http://127.0.0.1:9/forbidden", "PIP_NO_INDEX": "1"},
        )
        python = environment_python(environment)
        checks: list[dict[str, object]] = [
            {"name": "offline_install", "passed": install.returncode == 0, "actual": install.stderr[-2000:]},
        ]
        commands = {
            "core_imports": "import fastmcp,pydantic,uvicorn; import server.main",
            "optional_ai_absent": (
                "import importlib.util; assert importlib.util.find_spec('transformers') is None; "
                "assert importlib.util.find_spec('sentence_transformers') is None"
            ),
            "proxy_diagnostics": (
                "from server.infrastructure.proxy_support import inspect_proxy_compatibility as i; "
                "assert i({}).outbound_supported; assert i({'HTTP_PROXY':'http://proxy.example:8080'}).outbound_supported; "
                "assert not i({'ALL_PROXY':'not-a-url'}).outbound_supported"
            ),
        }
        if install.returncode == 0:
            for name, expression in commands.items():
                result = subprocess.run(
                    [str(python), "-c", expression],
                    cwd=root,
                    env={**os.environ, "PYTHONPATH": str(root), "PIP_INDEX_URL": "http://127.0.0.1:9/forbidden"},
                    text=True,
                    capture_output=True,
                    check=False,
                )
                checks.append(
                    {"name": name, "passed": result.returncode == 0, "actual": (result.stderr or result.stdout)[-2000:]}
                )
        payload = {
            "profile": args.profile,
            "passed": all(bool(item["passed"]) for item in checks),
            "environment_size_bytes": directory_size(environment) if environment.exists() else 0,
            "wheelhouse_size_bytes": directory_size(args.wheelhouse),
            "checks": checks,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
