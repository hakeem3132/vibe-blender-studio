#!/usr/bin/env python3
"""Install a verified wheelhouse into a new isolated environment."""

from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path

from offline_dependencies import REQUIREMENTS_NAME, WheelhouseError, verify_manifest


def environment_python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("environment", type=Path)
    parser.add_argument("--lock", type=Path, default=Path("poetry.lock"))
    parser.add_argument("--profile", choices=("core", "development"), default="core")
    args = parser.parse_args()
    if args.environment.exists() and any(args.environment.iterdir()):
        print(f"ERROR: destination must be absent or empty: {args.environment}", file=sys.stderr)
        return 2
    try:
        verify_manifest(args.wheelhouse, args.lock, args.profile)
    except WheelhouseError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    venv.EnvBuilder(with_pip=True, clear=False).create(args.environment)
    command = [
        str(environment_python(args.environment)),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--only-binary=:all:",
        "--require-hashes",
        "--find-links",
        str(args.wheelhouse.resolve()),
        "-r",
        str((args.wheelhouse / REQUIREMENTS_NAME).resolve()),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode:
        print("ERROR: offline installation failed; verify that all target-platform wheels are present", file=sys.stderr)
        return result.returncode
    print(environment_python(args.environment))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
