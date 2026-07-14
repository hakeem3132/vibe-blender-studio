import json
import zipfile
from pathlib import Path

from blender_addon.version import DISPLAY_VERSION, PACKAGE_VERSION, UPSTREAM_COMMIT, UPSTREAM_VERSION

ROOT = Path(__file__).resolve().parents[3]


def test_product_and_upstream_versions_are_distinct_and_coherent():
    assert PACKAGE_VERSION == "0.2.0.dev0"
    assert DISPLAY_VERSION == "0.2.0-dev"
    assert UPSTREAM_VERSION == "3.3.0"
    assert UPSTREAM_COMMIT == "43253155440f78ce208f7c4264bb8be6fb784ec7"


def test_built_archive_contains_license_notices_and_version_manifest():
    archive_path = ROOT / "outputs" / "blender_ai_mcp.zip"
    assert archive_path.is_file(), "Run scripts/build_addon.py before the package integrity test"
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        required = {
            "blender_ai_mcp/LICENSE.md",
            "blender_ai_mcp/NOTICE",
            "blender_ai_mcp/THIRD_PARTY_NOTICES.md",
            "blender_ai_mcp/version.json",
            "blender_ai_mcp/INSTALL.md",
        }
        assert required <= names
        manifest = json.loads(archive.read("blender_ai_mcp/version.json"))
        assert manifest["version"] == DISPLAY_VERSION
        assert manifest["upstream_commit"] == UPSTREAM_COMMIT
        assert not any("__pycache__" in name or name.endswith(".pyc") or ".env" in name for name in names)


def test_built_archive_has_reproducible_metadata_and_no_local_paths():
    archive_path = ROOT / "outputs" / "blender_ai_mcp.zip"
    with zipfile.ZipFile(archive_path) as archive:
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        content = b"\n".join(archive.read(name) for name in archive.namelist())
    assert b"/workspace/scratch/" not in content
    assert b"VIBE_RPC_SESSION_TOKEN=" not in content
