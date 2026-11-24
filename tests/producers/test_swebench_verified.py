import json

from producers.nemotron import save_json
from producers.swebench_verified import SOURCE, TEST, edit_is_scoped, model_loop, parse_model_action


class FixtureRepo:
    def __init__(self):
        self.source = "broken"
        self.tests = 0

    def read(self, name, *, full=False):
        assert name in (SOURCE, TEST)
        return self.source if name == SOURCE else "assert fixed"

    def replace(self, old, new):
        if self.source != old:
            return {"exit_code": 1, "stdout": "", "stderr": "no exact match"}
        self.source = new
        return {"exit_code": 0, "stdout": "", "stderr": ""}

    def target_test(self):
        self.tests += 1
        passed = self.source == "fixed"
        return {"exit_code": 0 if passed else 1,
                "stdout": "1 passed" if passed else "assert broken == fixed"}

    def execute(self, *command):
        return {"exit_code": 0, "stdout": "", "stderr": ""}


class FixtureClient:
    def __init__(self, actions):
        self.actions = iter(actions)

    def complete(self, model, messages, **kwargs):
        return json.dumps(next(self.actions))


def test_b_resumes_assessed_handoff_and_retests_actual_edit(tmp_path):
    save_json(tmp_path / "actions.json", [
        {"action": {"action": "assess", "stored_exit_code": 1,
                    "conclusion": "A's target failed"}, "result": {"accepted": True}},
        {"action": {"action": "read", "path": SOURCE}, "result": "broken"},
        {"action": {"action": "read", "path": TEST}, "result": "assert fixed"},
    ])
    handoff = {"run_id": "run-a", "receipt_hash": "receipt-a",
               "artifact": {"open_loops": ["fix target"], "evidence": {"target_test": {"exit_code": 1}}}}
    repo = FixtureRepo()
    client = FixtureClient([
        {"action": "replace", "old": "broken", "new": "fixed", "proposal": "fix failure"},
    ])
    result = model_loop(client, "fixture-model", repo, "b", handoff, tmp_path)
    assert result["target_test"]["exit_code"] == 0
    assert result["assessment"]["conclusion"] == "A's target failed"
    assert repo.source == "fixed"
    assert repo.tests >= 3
    events = json.loads((tmp_path / "actions.json").read_text())
    assert [event["action"]["action"] for event in events[-4:]] == ["read", "read", "replace", "test"]


def test_single_wrapped_command_is_not_executed_as_arbitrary_plan():
    assert parse_model_action(json.dumps({"commands": [{"action": "test"}]})) == {"action": "test"}
    assert parse_model_action(json.dumps({"commands": [{"action": "test"}, {"action": "test"}]})) == {"action": "invalid"}


def test_b_edits_are_limited_to_the_two_mark_functions():
    source = ("header\ndef get_unpacked_marks():\n    return 1\n\ndef normalize_mark_list():\n"
              "    return 1\n\ndef store_mark():\n    return 1\n\n# Typing for builtin\n")
    assert edit_is_scoped(source, source.replace("def store_mark():\n    return 1",
                                                  "def store_mark():\n    return 2"))
    assert edit_is_scoped(source, source.replace("def get_unpacked_marks():\n    return 1",
                                                  "def get_unpacked_marks():\n    return 2"))
    assert not edit_is_scoped(source, source.replace("def normalize_mark_list():\n    return 1",
                                                      "def normalize_mark_list():\n    return 2"))
