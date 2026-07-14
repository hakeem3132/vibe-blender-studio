import copy
import uuid

from blender_addon.vibe_studio.prompts import interpret_prompt
from blender_addon.vibe_studio.transactions import TransactionEngine


class MockSceneGateway:
    def __init__(self):
        self.target = str(uuid.uuid4())
        self.state = {
            self.target: {"location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]},
            "unrelated": {"location": [8.0, 9.0, 10.0]},
        }

    def validate_targets(self, change_set):
        assert change_set.scope.target_ids == (self.target,)

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
        preserved = self.state["unrelated"] == before["unrelated"]
        return {"passed": preserved, "checks": [{"name": "all_unselected_objects", "passed": preserved}]}


def test_preview_apply_reject_undo_and_redo_with_mock_gateway():
    gateway = MockSceneGateway()
    engine = TransactionEngine(gateway)
    before = gateway.snapshot_scene()
    change_set = interpret_prompt("Move the selected object 1 metre upward.", gateway.target)
    engine.preview(change_set)
    assert gateway.state == before
    engine.apply_pending()
    accepted = gateway.snapshot_scene()
    assert accepted[gateway.target]["location"] == [0.0, 0.0, 1.0]
    engine.undo()
    assert gateway.state == before
    engine.redo()
    assert gateway.state == accepted
    engine.preview(change_set)
    engine.reject()
    assert gateway.state == accepted
