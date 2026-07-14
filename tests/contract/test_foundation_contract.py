import uuid

import pytest
from blender_addon.infrastructure.rpc_security import PROTOCOL_VERSION as ADDON_PROTOCOL_VERSION
from blender_addon.vibe_studio.contracts import ChangeSet, ChangeSetError
from server.domain.models.rpc import PROTOCOL_VERSION as BACKEND_PROTOCOL_VERSION


def valid_changeset():
    return {
        "schema_version": "1.0",
        "change_set_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "prompt": "Create a cube.",
        "intent": "object.create",
        "scope": {"type": "current_scene", "target_ids": []},
        "operations": [
            {"tool": "object.create", "target_id": None, "parameters": {"primitive": "cube", "location": [0, 0, 0]}}
        ],
        "preserve": ["all_unselected_objects"],
        "verification": ["target_exists"],
        "risk": "low",
    }


def test_protocol_version_is_shared():
    assert ADDON_PROTOCOL_VERSION == BACKEND_PROTOCOL_VERSION == "1.0"


def test_changeset_unknown_fields_are_rejected_atomically():
    payload = valid_changeset()
    payload["raw_python"] = "pass"
    with pytest.raises(ChangeSetError, match="Unknown ChangeSet fields"):
        ChangeSet.from_dict(payload)
