import json

import pytest

from producers.nemotron import Budget, coding_loop

MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


def test_budget_survives_restart_and_stops_before_thirteenth_call(tmp_path):
    path = tmp_path / "budget.json"
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
