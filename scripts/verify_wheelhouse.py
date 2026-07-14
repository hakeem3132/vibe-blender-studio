#!/usr/bin/env python3
"""Verify every offline wheel and its lock/manifest checksum."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from offline_dependencies import WheelhouseError, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("--lock", type=Path, default=Path("poetry.lock"))
    parser.add_argument("--profile", choices=("core", "development"))
    args = parser.parse_args()
    try:
        manifest = verify_manifest(args.wheelhouse, args.lock, args.profile)
    except (WheelhouseError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"verified {len(manifest['packages'])} wheels for {manifest['profile']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
