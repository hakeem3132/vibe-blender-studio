#!/usr/bin/env python3
"""Build the installable add-on with deterministic metadata and notices."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _write(zip_file: zipfile.ZipFile, archive_name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(archive_name, FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zip_file.writestr(info, content)


def build_addon() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    addon_src = project_root / "blender_addon"
    output_dir = project_root / "outputs"
    zip_path = output_dir / "blender_ai_mcp.zip"
    output_dir.mkdir(exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
        print(f"Removed old build: {zip_path}")
    print(f"Building addon from: {addon_src}")
    files = sorted(
        path
        for path in addon_src.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and ".env" not in path.name
    )
    supplements: dict[str, bytes] = {}
    for source_name, archive_name in (
        ("LICENSE.md", "LICENSE.md"),
        ("NOTICE", "NOTICE"),
        ("THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
    ):
        source = project_root / source_name
        if source.is_file():
            supplements[archive_name] = source.read_bytes()
    version_file = addon_src / "version.py"
    if version_file.is_file():
        namespace: dict[str, str] = {}
        exec(version_file.read_text(encoding="utf-8"), namespace)
        supplements["version.json"] = (
            json.dumps(
                {
                    "product": "Vibe Blender Studio",
                    "version": namespace["DISPLAY_VERSION"],
                    "upstream_version": namespace["UPSTREAM_VERSION"],
                    "upstream_commit": namespace["UPSTREAM_COMMIT"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        supplements["INSTALL.md"] = (
            b"Install this ZIP in Blender Preferences > Add-ons, then enable Vibe Blender Studio.\n"
            b"Quick start: https://github.com/hakeem3132/vibe-blender-studio\n"
        )
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in files:
            archive_name = f"blender_ai_mcp/{path.relative_to(addon_src).as_posix()}"
            _write(archive, archive_name, path.read_bytes())
        for name in sorted(supplements):
            _write(archive, f"blender_ai_mcp/{name}", supplements[name])
    print(f"Build successful: {zip_path}")
    print(f"Size: {zip_path.stat().st_size} bytes")
    return zip_path


if __name__ == "__main__":
    build_addon()
