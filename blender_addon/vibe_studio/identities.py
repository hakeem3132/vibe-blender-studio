"""Stable UUID helpers for Blender data blocks."""

from __future__ import annotations

import uuid
from typing import Any, Iterable

UUID_KEY = "vibe_uuid"
REVISION_KEY = "vibe_revision"


def valid_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def inspect_uuid(data_block: Any) -> str | None:
    value = data_block.get(UUID_KEY)
    return str(value) if valid_uuid(value) else None


def ensure_uuid(data_block: Any) -> str:
    current = inspect_uuid(data_block)
    if current is not None:
        return current
    generated = str(uuid.uuid4())
    data_block[UUID_KEY] = generated
    if data_block.get(REVISION_KEY) is None:
        data_block[REVISION_KEY] = 0
    return generated


def lookup_unique(data_blocks: Iterable[Any], stable_id: str) -> Any:
    matches = [item for item in data_blocks if inspect_uuid(item) == stable_id]
    if len(matches) != 1:
        raise ValueError(f"Stable UUID must resolve to exactly one data block; found {len(matches)}")
    return matches[0]


def validation_report(data_blocks: Iterable[Any]) -> dict[str, Any]:
    missing: list[str] = []
    malformed: list[str] = []
    by_id: dict[str, list[str]] = {}
    for item in data_blocks:
        raw = item.get(UUID_KEY)
        if raw is None:
            missing.append(item.name)
        elif not valid_uuid(raw):
            malformed.append(item.name)
        else:
            by_id.setdefault(str(raw), []).append(item.name)
    duplicates = {stable_id: names for stable_id, names in by_id.items() if len(names) > 1}
    return {
        "missing": missing,
        "malformed": malformed,
        "duplicates": duplicates,
        "valid": not any((missing, malformed, duplicates)),
    }


def repair_duplicates(data_blocks: Iterable[Any]) -> dict[str, str]:
    seen: set[str] = set()
    repaired: dict[str, str] = {}
    for item in data_blocks:
        stable_id = inspect_uuid(item)
        if stable_id is None or stable_id in seen:
            generated = str(uuid.uuid4())
            item[UUID_KEY] = generated
            repaired[item.name] = generated
            stable_id = generated
        seen.add(stable_id)
    return repaired
