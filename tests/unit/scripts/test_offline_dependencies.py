from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest
from scripts.offline_dependencies import WheelhouseError, load_locked_packages, verify_manifest, write_manifest


def _wheel(path: Path) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("demo_pkg-1.0.dist-info/METADATA", "Name: demo-pkg\nVersion: 1.0\nLicense: MIT\n")
        archive.writestr("demo_pkg-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nTag: py3-none-any\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lock(path: Path, wheel_name: str, digest: str) -> None:
    path.write_text(
        f'''[[package]]
name = "demo-pkg"
version = "1.0"
description = "fixture"
optional = false
python-versions = ">=3.11"
groups = ["main"]
files = [{{file = "{wheel_name}", hash = "sha256:{digest}"}}]

[[package]]
name = "ai-only"
version = "9.0"
description = "excluded"
optional = false
python-versions = ">=3.11"
groups = ["vision"]
files = [{{file = "ai_only-9.0-py3-none-any.whl", hash = "sha256:{"0" * 64}"}}]
''',
        encoding="utf-8",
    )


def test_manifest_verifies_hashes_and_excludes_optional_ai(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "demo_pkg-1.0-py3-none-any.whl"
    digest = _wheel(wheel)
    lock = tmp_path / "poetry.lock"
    _lock(lock, wheel.name, digest)
    packages = load_locked_packages(lock, "core")
    assert [item.name for item in packages] == ["demo-pkg"]
    write_manifest(wheelhouse, "core", lock)
    manifest = verify_manifest(wheelhouse, lock, "core")
    assert manifest["packages"][0]["sha256"] == digest
    assert manifest["packages"][0]["metadata"]["license"] == "MIT"


def test_tampered_or_missing_wheel_has_actionable_failure(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "demo_pkg-1.0-py3-none-any.whl"
    digest = _wheel(wheel)
    lock = tmp_path / "poetry.lock"
    _lock(lock, wheel.name, digest)
    write_manifest(wheelhouse, "core", lock)
    wheel.write_bytes(b"tampered")
    with pytest.raises(WheelhouseError, match="Checksum mismatch"):
        verify_manifest(wheelhouse, lock, "core")
    wheel.unlink()
    with pytest.raises(WheelhouseError, match="missing"):
        verify_manifest(wheelhouse, lock, "core")
