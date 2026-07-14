#!/usr/bin/env python3
"""Prepare a locked, wheel-only offline dependency artifact."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from offline_dependencies import (
    MANIFEST_NAME,
    REQUIREMENTS_NAME,
    WheelhouseError,
    compatible_locked_wheels,
    load_locked_packages,
    write_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("core", "development"), default="core")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lock", type=Path, default=Path("poetry.lock"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    wheelhouse = args.output or Path(".runtime/wheelhouse") / args.profile
    wheelhouse.mkdir(parents=True, exist_ok=True)
    if args.refresh:
        for path in [*wheelhouse.glob("*.whl"), wheelhouse / MANIFEST_NAME, wheelhouse / REQUIREMENTS_NAME]:
            if path.is_file():
                path.unlink()
    try:
        packages = load_locked_packages(args.lock, args.profile)
        requirements: list[str] = []
        for package in packages:
            candidates = compatible_locked_wheels(package)
            if not candidates:
                raise WheelhouseError(
                    f"No locked binary wheel for {package.name}=={package.version} matches this Python/platform"
                )
            requirements.append(f"{package.name}=={package.version}")
        command = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--disable-pip-version-check",
            "--only-binary=:all:",
            "--no-deps",
            "--dest",
            str(wheelhouse),
            *requirements,
        ]
        result = subprocess.run(command, check=False)
        if result.returncode:
            raise WheelhouseError(
                "Could not download every locked wheel; run the preparation step in a network-enabled "
                "environment or restore the matching CI cache"
            )
        manifest = write_manifest(wheelhouse, args.profile, args.lock)
    except WheelhouseError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
