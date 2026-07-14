#!/usr/bin/env python3
"""Locate the pinned Blender runtime without mutating the host."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

PINNED_BLENDER_VERSION = "4.2.15"


def find_blender(explicit: str | None = None) -> Path | None:
    root = Path(__file__).resolve().parents[1]
    candidates = (
        explicit,
        os.environ.get("BLENDER_PATH"),
        "/tmp/vibe-blender-runtime/blender-4.2.15-linux-x64/blender",
        str(root / ".runtime/blender/blender-4.2.15-linux-x64/blender"),
        shutil.which("blender"),
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    found = find_blender(args.blender)
    if args.json:
        print(
            json.dumps(
                {"found": found is not None, "path": str(found) if found else None, "pinned": PINNED_BLENDER_VERSION}
            )
        )
    elif found:
        print(found)
    else:
        print("BLOCKED: Blender 4.2.15 not found; run scripts/install_blender_ci.sh")
    return 0 if found else 2


if __name__ == "__main__":
    raise SystemExit(main())
