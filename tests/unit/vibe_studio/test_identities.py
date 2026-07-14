from blender_addon.vibe_studio.identities import ensure_uuid, inspect_uuid, repair_duplicates, validation_report


class Block(dict):
    def __init__(self, name):
        super().__init__()
        self.name = name


def test_uuid_is_stable_across_rename():
    block = Block("Cube")
    stable_id = ensure_uuid(block)
    block.name = "Renamed"
    assert ensure_uuid(block) == stable_id
    assert inspect_uuid(block) == stable_id


def test_duplicate_uuid_repair_keeps_first_and_repairs_second():
    first, second = Block("A"), Block("B")
    stable_id = ensure_uuid(first)
    second["vibe_uuid"] = stable_id
    assert validation_report([first, second])["valid"] is False
    repaired = repair_duplicates([first, second])
    assert repaired.keys() == {"B"}
    assert inspect_uuid(first) != inspect_uuid(second)
