import json
from pathlib import Path

import pytest

from cli import storage, yare


@pytest.fixture
def compile_packet(monkeypatch, tmp_path):
    monkeypatch.setattr(yare, "validate_workspace", lambda root: {"ok": True, "errors": [], "warnings": []})
    monkeypatch.setattr(yare, "_git_state", lambda root: {"available": False})

    def compile_records(records):
        artifacts = [yare._lead_normalize_artifact(record, f"artifact:{index}", index)
                     for index, record in enumerate(records)]
        return yare._lead_compile_packet(tmp_path, artifacts, "integrity test")

    return compile_records


def supported_claim(text, exit_code=0):
    return {"claim": text, "verification_status": "verified", "evidence": {
        "kind": "test", "claim": text, "command": ["python", "-m", "pytest"],
        "exit_code": exit_code, "expected_exit_code": 0, "stdout": "6 passed", "stderr": ""}}


def test_unsupported_verified_claim_remains_unverified(compile_packet):
    state = compile_packet([{"claims": [{"claim": "CI passed", "verification_status": "verified"}]}])["current_state"]
    assert state["what_is_true"] == []
    assert state["what_is_unverified"] == ["CI passed"]


@pytest.mark.parametrize("change", ["failure", "wrong_claim", "missing_output", "missing_command"])
def test_invalid_test_evidence_cannot_verify_a_claim(compile_packet, change):
    claim = supported_claim("CI passed")
    if change == "failure":
        claim["evidence"]["exit_code"] = 1
    elif change == "wrong_claim":
        claim["evidence"]["claim"] = "Another test passed"
    elif change == "missing_output":
        claim["evidence"]["stdout"] = ""
    else:
        claim["evidence"]["command"] = []
    state = compile_packet([{"claims": [claim]}])["current_state"]
    assert state["what_is_true"] == []


def test_disputed_supported_claim_is_not_a_confirmed_fact(compile_packet):
    state = compile_packet([
        {"claims": [supported_claim("CI passed")]},
        {"claims": [{"claim": "CI passed", "verification_status": "contradicted"}]},
    ])["current_state"]
    assert state["what_is_true"] == []
    assert state["what_contradicts_prior_state"] == ["CI passed"]


def test_evidence_ref_and_human_resolution_survive_compile(compile_packet):
    proof = supported_claim("CI passed")["evidence"]
    decision = {"kind": "human_review", "claim": "Release approved", "reviewer": "reviewer-1",
                "decision": "approved"}
    state = compile_packet([{
        "claims": [{"claim": "CI passed", "verification_status": "verified", "evidence_ref": "test"}],
        "evidence": {"test": proof, "claim_resolutions": [decision, {**decision, "reviewer": ""}]},
    }])["current_state"]
    assert state["what_is_true"] == ["CI passed"]
    assert state["claim_resolutions"] == [decision]


def test_removed_claim_requires_positive_evidence_to_be_resolved():
    previous = {"state_hash": "previous", "state": {"what_is_unverified": ["CI passed", "Release approved"]}}
    latest = {"state_hash": "latest", "state": {"what_is_true": []}}
    diff = storage.diff_states(previous, latest)
    assert diff["resolved_claims"] == []
    assert diff["removed_claims"] == ["CI passed", "Release approved"]
    latest["state"]["what_is_true"] = ["CI passed"]
    latest["state"]["claim_resolutions"] = [{"kind": "human_review", "claim": "Release approved",
                                             "decision": "approved", "reviewer": "reviewer-1"}]
    diff = storage.diff_states(previous, latest)
    assert diff["resolved_claims"] == ["CI passed", "Release approved"]
    assert diff["removed_claims"] == []


class Cursor:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return next(self.batches)


class Connection:
    def __init__(self, cursor):
        self.cur = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self):
        return self.cur

    def commit(self):
        pass


def state_row(state_hash, task="task", state=None):
    return (state_hash, "2026-10-08", task, "run-" + state_hash, "receipt-" + state_hash, state or {})


def test_timeline_selects_newest_then_displays_in_order_with_task_filter():
    cursor = Cursor([[state_row("latest"), state_row("previous")]])
    rows = storage.memory_timeline(limit=2, task="task", database_url="stub",
                                   connect_func=lambda url: Connection(cursor))
    assert [row["state_hash"] for row in rows] == ["previous", "latest"]
    sql, params = cursor.calls[0]
    assert "ORDER BY cs.created_at DESC" in sql
    assert params == ("task", "task", 2)


def test_latest_diff_selects_only_states_of_the_same_task():
    cursor = Cursor([[state_row("latest"), state_row("previous")]])
    diff = storage.latest_memory_diff(task="task", database_url="stub",
                                     connect_func=lambda url: Connection(cursor))
    assert diff["latest_state_hash"] == "latest"
    assert "WHERE COALESCE(cs.packet_json->>'task', r.task) = COALESCE" in cursor.calls[0][0]
    assert cursor.calls[0][1] == ("task",)


@pytest.mark.parametrize("query,section,text", [
    ("what still needs human review?", "human approval items", "Approve endpoint release"),
    ("what remains unresolved?", "what is unverified", "CI result is not confirmed"),
    ("which files changed?", "what changed", "cli/storage.py"),
])
def test_search_known_questions_overrides_vector_collisions_and_deduplicates(query, section, text):
    irrelevant = ("what is true", 0.01, "state-1", "Endpoint returns latest receipt")
    relevant = (section, 0.8, "state-2", text)
    duplicate = (section, 0.9, "state-3", text)
    cursor = Cursor([[irrelevant], [relevant, duplicate]])
    rows = storage.search_memory(query, 3, database_url="stub", connect_func=lambda url: Connection(cursor))
    assert rows[0]["section_name"] == section
    assert len(rows) == 1
    assert "embedding <=>" in cursor.calls[0][0]
    assert "LIKE %s" in cursor.calls[1][0]


def test_search_rejects_empty_meaningful_query():
    with pytest.raises(storage.StorageError, match="meaningful query"):
        storage.search_memory("what is the", 3, database_url="stub")


def test_persistence_saves_the_full_packet_as_an_immutable_source_snapshot():
    cursor = Cursor([])
    packet = {"task": "task", "deterministic_hash": "hash", "proof": {"run_id": "run"},
              "current_state": {}, "artifacts": [{"run_id": "run", "evidence": {"source_code": "source"}}]}
    storage.persist_lead_compile(packet, [], {}, database_url="stub", connect_func=lambda url: Connection(cursor))
    statement, params = next(call for call in cursor.calls if "INSERT INTO yare_current_states" in call[0])
    assert json.loads(params[3]) == packet
    assert "packet_json = COALESCE" in statement
    assert "state_json = excluded" not in statement
