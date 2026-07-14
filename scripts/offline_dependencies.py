"""Locked, wheel-only dependency artifact helpers.

The wheelhouse is intentionally a release/CI artifact, not source-controlled
content.  Every downloaded wheel must be named and hashed by ``poetry.lock``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import tomllib
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable

from packaging.markers import Marker
from packaging.tags import Tag, sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

MANIFEST_NAME = "wheelhouse-manifest.json"
REQUIREMENTS_NAME = "requirements-locked.txt"
MANIFEST_SCHEMA = "1.0"
OPTIONAL_AI_GROUPS = frozenset({"semantic", "vision"})


class WheelhouseError(RuntimeError):
    """An actionable wheelhouse validation failure."""


@dataclass(frozen=True)
class LockedPackage:
    name: str
    version: str
    groups: tuple[str, ...]
    files: dict[str, str]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _marker_applies(value: Any, groups: tuple[str, ...], wanted_groups: set[str]) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        relevant = [value[group] for group in groups if group in wanted_groups and group in value]
        return any(_marker_applies(item, groups, wanted_groups) for item in relevant) if relevant else True
    if not isinstance(value, str):
        raise WheelhouseError(f"Unsupported Poetry marker value: {value!r}")
    try:
        return Marker(value).evaluate()
    except Exception as error:
        raise WheelhouseError(f"Cannot evaluate Poetry marker {value!r}: {error}") from error


def load_locked_packages(lock_path: Path, profile: str) -> list[LockedPackage]:
    if profile not in {"core", "development"}:
        raise WheelhouseError("Profile must be 'core' or 'development'")
    payload = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    wanted_groups = {"main"} if profile == "core" else {"main", "dev"}
    selected: list[LockedPackage] = []
    for raw in payload.get("package", []):
        groups = tuple(str(item) for item in raw.get("groups", ()))
        if not wanted_groups.intersection(groups) or not _marker_applies(raw.get("markers"), groups, wanted_groups):
            continue
        if OPTIONAL_AI_GROUPS.intersection(groups) and not wanted_groups.intersection(groups):
            continue
        files = {
            str(item["file"]): str(item["hash"]).removeprefix("sha256:")
            for item in raw.get("files", ())
            if str(item.get("file", "")).endswith(".whl") and str(item.get("hash", "")).startswith("sha256:")
        }
        if not files:
            raise WheelhouseError(
                f"{raw['name']}=={raw['version']} has no locked wheel; source archives are not accepted"
            )
        selected.append(
            LockedPackage(
                name=str(raw["name"]),
                version=str(raw["version"]),
                groups=groups,
                files=files,
            )
        )
    return sorted(selected, key=lambda package: canonicalize_name(package.name))


def compatible_locked_wheels(package: LockedPackage, tags: Iterable[Tag] | None = None) -> set[str]:
    supported = set(tags or sys_tags())
    compatible: set[str] = set()
    for filename in package.files:
        try:
            _, _, _, wheel_tags = parse_wheel_filename(filename)
        except Exception:
            continue
        if supported.intersection(wheel_tags):
            compatible.add(filename)
    return compatible


def wheel_metadata(path: Path) -> dict[str, str | list[str]]:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise WheelhouseError(f"{path.name} does not contain exactly one distribution METADATA file")
        message = BytesParser().parsebytes(archive.read(metadata_names[0]))
    classifiers = message.get_all("Classifier", [])
    license_classifiers = [item for item in classifiers if item.startswith("License ::")]
    return {
        "name": message.get("Name", ""),
        "version": message.get("Version", ""),
        "license": message.get("License-Expression") or message.get("License") or "UNKNOWN",
        "license_classifiers": license_classifiers,
    }


def write_manifest(wheelhouse: Path, profile: str, lock_path: Path) -> Path:
    packages = load_locked_packages(lock_path, profile)
    expected = {canonicalize_name(item.name): item for item in packages}
    wheels = sorted(wheelhouse.glob("*.whl"))
    entries: list[dict[str, Any]] = []
    found: set[str] = set()
    for path in wheels:
        name, version, _, _ = parse_wheel_filename(path.name)
        canonical = canonicalize_name(name)
        package = expected.get(canonical)
        if package is None:
            raise WheelhouseError(f"Unexpected wheel is not in the {profile} lock profile: {path.name}")
        if str(version) != package.version:
            raise WheelhouseError(f"Wrong version for {package.name}: {version}; expected {package.version}")
        digest = sha256_file(path)
        locked_digest = package.files.get(path.name)
        if locked_digest != digest:
            raise WheelhouseError(f"Checksum for {path.name} is not the checksum recorded in poetry.lock")
        found.add(canonical)
        entries.append(
            {
                "name": package.name,
                "version": package.version,
                "filename": path.name,
                "sha256": digest,
                "groups": list(package.groups),
                "metadata": wheel_metadata(path),
            }
        )
    missing = sorted(set(expected) - found)
    if missing:
        raise WheelhouseError(f"Wheelhouse is incomplete; missing locked wheels for: {', '.join(missing)}")
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "profile": profile,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "poetry_lock_sha256": sha256_file(lock_path),
        "optional_ai_groups_included": False,
        "packages": entries,
    }
    manifest_path = wheelhouse / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    requirements = wheelhouse / REQUIREMENTS_NAME
    requirements.write_text(
        "".join(
            f"{item['name']}=={item['version']} --hash=sha256:{item['sha256']}\n"
            for item in sorted(entries, key=lambda entry: canonicalize_name(str(entry["name"])))
        ),
        encoding="utf-8",
    )
    return manifest_path


def verify_manifest(wheelhouse: Path, lock_path: Path, profile: str | None = None) -> dict[str, Any]:
    manifest_path = wheelhouse / MANIFEST_NAME
    if not manifest_path.is_file():
        raise WheelhouseError(f"Missing {MANIFEST_NAME} in {wheelhouse}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise WheelhouseError("Unsupported wheelhouse manifest schema")
    if profile is not None and manifest.get("profile") != profile:
        raise WheelhouseError(f"Wheelhouse profile is {manifest.get('profile')!r}; expected {profile!r}")
    current_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    recorded_python = str(manifest.get("python", ""))
    if not recorded_python.startswith(current_python + "."):
        raise WheelhouseError(
            f"Wheelhouse targets Python {recorded_python}; this interpreter is Python {current_python}. "
            "Build a wheelhouse for the target interpreter."
        )
    if manifest.get("poetry_lock_sha256") != sha256_file(lock_path):
        raise WheelhouseError("Wheelhouse was generated from a different poetry.lock")
    if manifest.get("optional_ai_groups_included") is not False:
        raise WheelhouseError("Core/development wheelhouses must exclude optional AI/model groups")
    expected_files = {str(item["filename"]) for item in manifest.get("packages", ())}
    actual_files = {path.name for path in wheelhouse.glob("*.whl")}
    if expected_files != actual_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise WheelhouseError(f"Wheel set differs from manifest; missing={missing}, extra={extra}")
    for item in manifest["packages"]:
        path = wheelhouse / str(item["filename"])
        if sha256_file(path) != item["sha256"]:
            raise WheelhouseError(f"Checksum mismatch: {path.name}")
    requirements = wheelhouse / REQUIREMENTS_NAME
    if not requirements.is_file():
        raise WheelhouseError(f"Missing {REQUIREMENTS_NAME}")
    return manifest
