import copy
import uuid

import pytest
from blender_addon.vibe_studio.gateway import tracked_values_equal
from blender_addon.vibe_studio.prompts import interpret_prompt
from blender_addon.vibe_studio.transactions import TransactionEngine


class Gateway:
    def __init__(self):
        self.target = str(uuid.uuid4())
        self.state = {self.target: {"location": [0.0, 0.0, 0.0]}, "other": {"value": 7}}

    def validate_targets(self, change_set):
        assert change_set.scope.target_ids[0] in self.state

    def snapshot_scene(self):
        return copy.deepcopy(self.state)

    def restore_scene(self, state):
        self.state = copy.deepcopy(state)

    def apply(self, change_set):
        delta = change_set.operations[0].parameters["location_delta"]
        self.state[self.target]["location"] = [
            self.state[self.target]["location"][index] + delta[index] for index in range(3)
        ]

    def verify(self, change_set, before):
        unchanged = before["other"] == self.state["other"]
        return {"passed": unchanged, "checks": [{"name": "preserved_state_unchanged", "passed": unchanged}]}


def test_preview_apply_reject_undo_redo_are_exact():
    gateway = Gateway()
    engine = TransactionEngine(gateway)
    change_set = interpret_prompt("Move the selected object 1 metre upward.", gateway.target)
    before = gateway.snapshot_scene()
    transaction = engine.preview(change_set)
    assert transaction.status == "PREVIEWED"
    assert gateway.state == before
    engine.apply_pending()
    after = gateway.snapshot_scene()
    assert after[gateway.target]["location"] == [0.0, 0.0, 1.0]
    engine.undo()
    assert gateway.state == before
    engine.redo()
    assert gateway.state == after
    engine.preview(change_set)
    engine.reject()
    assert gateway.state == after


def test_failed_verification_rolls_preview_back():
    gateway = Gateway()
    gateway.verify = lambda change_set, before: {"passed": False, "checks": []}
    engine = TransactionEngine(gateway)
    before = gateway.snapshot_scene()
    with pytest.raises(RuntimeError, match="verification failed"):
        engine.preview(interpret_prompt("Move the selected object 1 metre upward.", gateway.target))
    assert gateway.state == before


def test_blender_float_verification_uses_small_deterministic_tolerance():
    assert tracked_values_equal((0.0, 0.0, 0.7853981633974483), (0.0, 0.0, 0.7853981852531433))
    assert not tracked_values_equal((0.0, 0.0, 0.7853981633974483), (0.0, 0.0, 0.79))
