import json

import pytest

from producers.nemotron import Budget, coding_loop, save_json

MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


def test_budget_survives_restart_and_stops_before_thirteenth_call(tmp_path):
    path = tmp_path / "budget.json"
    initial = Budget(path)
    initial.state["max_calls"] = 12
    save_json(path, initial.state)
    for _ in range(12):
        Budget(path).reserve(MODEL, {"messages": [], "max_tokens": 1})
    with pytest.raises(ValueError, match="Call allowance"):
        Budget(path).reserve(MODEL, {"messages": [], "max_tokens": 1})
    assert len(json.loads(path.read_text())["calls"]) == 12


def test_budget_stops_before_dollar_cap(tmp_path):
    budget = Budget(tmp_path / "budget.json")
    budget.state["limit_usd"] = "0.00001"
    with pytest.raises(ValueError, match="Dollar allowance"):
        budget.reserve(MODEL, {"messages": [], "max_tokens": 4096})
    assert not budget.state["calls"]


def test_missing_usage_keeps_reservation(tmp_path):
    budget = Budget(tmp_path / "budget.json")
    index = budget.reserve(MODEL, {"messages": [], "max_tokens": 4096})
    with pytest.raises(ValueError, match="Missing valid usage"):
        budget.settle(index, {})
    assert Budget(budget.path).state["calls"][0]["status"] == "reserved"
    with pytest.raises(ValueError, match="blocked"):
        Budget(budget.path).reserve(MODEL, {"messages": [], "max_tokens": 4096})


def test_provider_overrun_blocks_future_calls(tmp_path):
    budget = Budget(tmp_path / "budget.json")
    index = budget.reserve(MODEL, {"messages": [], "max_tokens": 1})
    with pytest.raises(ValueError, match="exceeded reserved"):
        budget.settle(index, {"prompt_tokens": 10, "completion_tokens": 2})
    with pytest.raises(ValueError, match="blocked"):
        Budget(budget.path).reserve(MODEL, {"messages": [], "max_tokens": 1})


class FixtureRepo:
    def __init__(self):
        self.source = "broken\n"
        self.tests = 0

    def read(self, name):
        return self.source if name == "workstate.py" else "immutable tests"

    def write(self, content):
        self.source = content
        return {"exit_code": 0}

    def test(self):
        self.tests += 1
        return {"exit_code": int(self.source != "fixed\n"), "stdout": self.source}


class FixtureClient:
    def __init__(self, actions):
        self.actions = iter(actions)

    def complete(self, model, messages):
        return json.dumps(next(self.actions))


def test_loop_reads_failures_and_retries_then_independently_tests(tmp_path):
    client = FixtureClient([
        {"action": "read", "path": "workstate.py"},
        {"action": "read", "path": "test_workstate.py"},
        {"action": "write", "proposal": "first attempt", "content": "still broken\n"},
        {"action": "test"},
        {"action": "write", "proposal": "fix failure", "content": "fixed\n"},
        {"action": "test"},
    ])
    repo = FixtureRepo()
    result = coding_loop(client, MODEL, repo, tmp_path)
    assert result["baseline_test"]["exit_code"] == 1
    assert result["final_test"]["exit_code"] == 0
    assert repo.tests == 4
    assert "-broken" in result["diff"]


def test_loop_does_not_accept_unexecuted_success_claim(tmp_path):
    with pytest.raises(ValueError, match="without an observed passing"):
        coding_loop(FixtureClient([{"action": "done"}]), MODEL, FixtureRepo(), tmp_path)


def test_loop_requires_inspection_before_edit(tmp_path):
    client = FixtureClient([
        {"action": "write", "proposal": "premature fix", "content": "fixed\n"},
        {"action": "read", "path": "workstate.py"},
        {"action": "read", "path": "test_workstate.py"},
        {"action": "write", "proposal": "inspected fix", "content": "fixed\n"},
        {"action": "test"},
    ])
    coding_loop(client, MODEL, FixtureRepo(), tmp_path)
    events = json.loads((tmp_path / "actions.json").read_text())
    assert "rejected" in events[1]["result"]


def test_allowance_increase_preserves_existing_calls(tmp_path):
    path = tmp_path / "budget.json"
    initial = Budget(path)
    initial.state["max_calls"] = 50
    save_json(path, initial.state)
    for _ in range(45):
        initial = Budget(path)
        index = initial.reserve(MODEL, {"messages": [], "max_tokens": 1})
        initial.settle(index, {"prompt_tokens": 10, "completion_tokens": 1})
    budget = Budget(path)
    original = list(budget.state["calls"])
    budget.state["max_calls"] = 100
    save_json(path, budget.state)
    for _ in range(55):
        current = Budget(path)
        index = current.reserve(MODEL, {"messages": [], "max_tokens": 1})
        current.settle(index, {"prompt_tokens": 10, "completion_tokens": 1})
    final = Budget(path)
    assert final.state["calls"][:45] == original
    assert final.state["max_calls"] == 100
    assert final.state["limit_usd"] == "5"
    with pytest.raises(ValueError, match="Call allowance"):
        final.reserve(MODEL, {"messages": [], "max_tokens": 1})


def test_handoff_requires_evidence_assessment(tmp_path):
    command = ["python", "-m", "unittest", "-v", "test_workstate.ClaimTests"]
    handoff = {"artifact": {"evidence": {"partial_test": {"command": command}}}}
    class CapturingClient(FixtureClient):
        def complete(self, model, messages):
            self.first_messages = getattr(self, "first_messages", messages)
            return super().complete(model, messages)

    client = CapturingClient([
        {"action": "assess_handoff", "observed_exit_code": 0,
         "observed_test_command": command, "unverified_claim": "All full-suite tests passed",
         "explanation": "Only partial tests were observed, not the full suite."},
        {"action": "read", "path": "workstate.py"},
        {"action": "read", "path": "test_workstate.py"},
        {"action": "write", "proposal": "finish task", "content": "fixed\n"},
        {"action": "test"},
    ])
    result = coding_loop(client, MODEL, FixtureRepo(), tmp_path, handoff=handoff)
    assert result["handoff_assessment"]["observed_test_command"] == command
    assert "B's baseline, not A's result" in client.first_messages[0]["content"]
    assert "only read workstate.py or test_workstate.py" in client.first_messages[0]["content"]
    assert "scope_probes" not in result


def test_handoff_rejects_edit_before_assessment(tmp_path):
    command = ["python", "-m", "unittest", "-v", "test_workstate.ClaimTests"]
    handoff = {"artifact": {"evidence": {"partial_test": {"command": command}}}}
    client = FixtureClient([
        {"action": "write", "proposal": "premature", "content": "fixed\n"},
        {"action": "assess_handoff", "observed_exit_code": 0,
         "observed_test_command": command, "unverified_claim": "All full-suite tests passed",
         "explanation": "Only the partial test was observed."},
        {"action": "read", "path": "workstate.py"},
        {"action": "read", "path": "test_workstate.py"},
        {"action": "write", "proposal": "after assessment", "content": "fixed\n"},
        {"action": "test"},
    ])
    coding_loop(client, MODEL, FixtureRepo(), tmp_path, handoff=handoff)
    events = json.loads((tmp_path / "actions.json").read_text())
    assert events[1]["result"] == {"rejected": "Assess the handoff before editing."}


def test_normalization_preserves_optional_evidence():
    from cli.yare import _lead_normalize_artifact
    evidence = {"partial_test": {"exit_code": 0, "stdout": "4 tests passed"}, "diff": "actual diff"}
    raw = {"run_id": "a", "task": "fix", "evidence": evidence}
    assert _lead_normalize_artifact(raw, "artifact.json", 0)["evidence"] == evidence
    del raw["evidence"]
    assert "evidence" not in _lead_normalize_artifact(raw, "artifact.json", 0)
