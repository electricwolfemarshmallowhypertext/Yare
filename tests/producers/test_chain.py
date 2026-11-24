import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from producers import chain

FIXTURE = Path(__file__).resolve().parents[2] / "examples/nemotron-chain"
SOLUTIONS = {
    "normalize_status": 'return value.strip().lower() or "unknown" if isinstance(value, str) else "unknown"',
    "classify_claim": 'return "contradicted" if status == "contradicted" else "verified" if status == "verified" and evidence_present is True else "unresolved"',
    "summarize_claims": 'counts = dict(verified=0, contradicted=0, unresolved=0)\nfor claim in claims:\n    counts[claim if claim in counts else "unresolved"] += 1\nreturn counts',
    "choose_next_action": 'return "review contradictions" if counts.get("contradicted", 0) > 0 else "verify unresolved claims" if counts.get("unresolved", 0) > 0 else "complete"',
}


def replace_function(source, name):
    tree = ast.parse(source)
    function = next(node for node in tree.body if node.name == name)
    function.body = ast.parse(SOLUTIONS[name]).body
    return ast.unparse(tree) + "\n"


class FixtureRepo:
    def __init__(self, tmp_path, source):
        self.root = tmp_path
        self.write(source)
        (self.root / "test_workstate.py").write_bytes((FIXTURE / "test_workstate.py").read_bytes())

    def read(self, name):
        return (self.root / name).read_text()

    def write(self, source):
        (self.root / "workstate.py").write_text(source)
        return {"exit_code": 0}

    def test(self, target="test_workstate"):
        result = subprocess.run([sys.executable, "-B", "-c", "TARGET=" + repr(target) + "\n" + chain.TEST_PROGRAM],
                                cwd=self.root, capture_output=True, text=True, timeout=10)
        return {"command": ["python", "test", target], "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, **json.loads(result.stdout)}


@pytest.mark.parametrize("answer", [
    '{"action":"test","stdout":"all passed"}',
    '{"action":"shell","command":"anything"}',
    '{"action":"read","path":"secret"}',
    '{"action":"select_work","function":"missing","reason":"x"}',
    '[]',
])
def test_protocol_rejects_output_and_unapproved_actions(answer):
    with pytest.raises((ValueError, chain.jsonschema.ValidationError)):
        chain.parse_action(answer)


def test_edit_guard_only_allows_selected_body():
    before = (FIXTURE / "workstate.py").read_text()
    one = replace_function(before, "normalize_status")
    chain.check_edit(before, one, "normalize_status")
    with pytest.raises(ValueError):
        chain.check_edit(before, replace_function(one, "classify_claim"), "normalize_status")
    with pytest.raises(ValueError):
        chain.check_edit(before, "import os\n" + one, "normalize_status")
    with pytest.raises(ValueError):
        chain.check_edit(before, one.replace("value):", "value, other):"), "normalize_status")


def test_four_fixture_turns_improve_without_repair_feedback(tmp_path):
    source = (FIXTURE / "workstate.py").read_text()
    parent = None
    for index, name in enumerate(chain.TARGETS):
        stage = tmp_path / str(index)
        stage.mkdir()
        repo = FixtureRepo(stage, source)
        after = replace_function(source, name)
        actions = [{"action": "read", "path": "workstate.py"},
                   {"action": "read", "path": "test_workstate.py"}]
        if parent:
            actions.append({"action": "assess_handoff", "state_hash": "state", "receipt_hash": "receipt",
                            "focused_exit_code": 0, "full_exit_code": 1, "explanation": "Focused pass; full suite failed."})
        actions.extend([{"action": "select_work", "function": name, "reason": "Chosen from failing tests"},
                        {"action": "write", "proposal": "Implement selected contract", "body_lines": SOLUTIONS[name].splitlines()},
                        {"action": "test"}, {"action": "handoff", "next_action": "Inspect remaining failures"}])

        class Client:
            def complete(self, model, messages, **kwargs):
                response_format = kwargs["extra_body"]["response_format"]
                assert response_format["type"] == "json_schema"
                action = actions.pop(0)
                chain.jsonschema.validate(action, response_format["json_schema"]["schema"])
                return json.dumps(action)

        result = chain.run_turn(Client(), "fixture", repo, stage / "evidence", "Fixed brief", parent)
        assert len(result["full_test"]["failed_tests"]) == 12 - index * 4
        artifact = chain.make_artifact("fixture-" + str(index), "fixture", result, "brief", "policy", parent)
        assert len(artifact["claims"]) == 1
        assert "All full-suite tests passed" not in json.dumps(artifact)
        if parent:
            assert artifact["evidence"]["parent_handoff"] == {key: parent[key]
                for key in ("run_id", "current_state_hash", "receipt_hash")}
        parent = {"run_id": artifact["run_id"], "current_state_hash": "state", "receipt_hash": "receipt",
                  "current_state": {"open_loops": artifact["open_loops"]}, "artifact": artifact}
        source = after
    (stage / "acceptance.py").write_bytes((FIXTURE / "acceptance.py").read_bytes())
    evaluated = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", "acceptance"],
                               cwd=stage, capture_output=True, text=True, timeout=10)
    assert evaluated.returncode == 0, evaluated.stderr
    assert "Ran 8 tests" in evaluated.stderr


def test_assessment_checks_exact_parent_and_both_test_results():
    parent = {"current_state_hash": "state", "receipt_hash": "receipt", "artifact": {
        "evidence": {"partial_test": {"exit_code": 0}, "full_test": {"exit_code": 1}}}}
    action = {"state_hash": "state", "receipt_hash": "receipt", "focused_exit_code": 0, "full_exit_code": 1}
    assert chain.assess_matches(action, parent)
    assert not chain.assess_matches({**action, "full_exit_code": 0}, parent)
    assert not chain.assess_matches({**action, "receipt_hash": "other"}, parent)


def test_ledger_cannot_drop_entries_or_change_limits():
    before = {"max_calls": 500, "max_tokens": 2000000, "limit_usd": "5", "calls": [{"status": "observed"}]}
    chain.check_ledger(before, {**before, "calls": before["calls"] + [{"status": "observed"}]})
    with pytest.raises(ValueError, match="entries"):
        chain.check_ledger(before, {**before, "calls": []})
    with pytest.raises(ValueError, match="limits"):
        chain.check_ledger(before, {**before, "max_calls": 501})


def test_repeated_invalid_response_stops_before_edit(tmp_path):
    repo = FixtureRepo(tmp_path, (FIXTURE / "workstate.py").read_text())
    before = repo.read("workstate.py")

    class Client:
        def complete(self, *args, **kwargs):
            return '{"action":"test","stdout":"forged"}'

    with pytest.raises(ValueError, match="Repeated invalid"):
        chain.run_turn(Client(), "fixture", repo, tmp_path / "evidence", "Fixed brief")
    assert repo.read("workstate.py") == before


def test_sandbox_identifiers_fit_openshell_limit():
    names = [chain.sandbox_name("nebius-chain-20261017", suffix) for suffix in [*"abcd", "verify"]]
    assert len(set(names)) == 5
    assert all(len(name) <= 19 for name in names)


def test_protocol_schema_preserves_assessment_gate_and_agent_work_selection():
    files = {"workstate.py", "test_workstate.py"}
    schema = chain.next_action_schema(set(), True, None, False, None)
    assert schema["properties"]["action"]["enum"] == ["read"]
    schema = chain.next_action_schema(files, True, None, False, None)
    assert schema["properties"]["action"]["enum"] == ["assess_handoff"]
    schema = chain.next_action_schema(files, False, None, False, None)
    assert schema["properties"]["action"]["enum"] == ["select_work"]
    assert set(schema["properties"]["function"]["enum"]) == set(chain.TARGETS)
    schema = chain.next_action_schema(files, False, {"function": "normalize_status"}, True, None)
    assert schema["properties"]["action"]["enum"] == ["test"]


def test_line_edit_preserves_other_functions_and_rejects_embedded_newlines():
    before = (FIXTURE / "workstate.py").read_text()
    after = chain.apply_body(before, "normalize_status", SOLUTIONS["normalize_status"].splitlines())
    chain.check_edit(before, after, "normalize_status")
    with pytest.raises(ValueError, match="one source line"):
        chain.apply_body(before, "normalize_status", ["return None\nreturn True"])


def test_final_readback_must_match_stage_identity():
    stage = {"run_id": "run", "current_state_hash": "state", "receipt_hash": "receipt"}
    chain.check_record_identity(stage, stage)
    with pytest.raises(ValueError, match="differs"):
        chain.check_record_identity({**stage, "receipt_hash": "other"}, stage)
