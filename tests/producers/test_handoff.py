import hashlib
import json
from types import SimpleNamespace

import pytest

from producers import handoff
from cli.storage import _hash_json


def handoff_row():
    source = "stored source"
    artifact = {"run_id": "test-a", "evidence": {
        "diff": "stored diff", "source_code": source,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest()}}
    state = {"what_is_true": []}
    packet = {"current_state": state, "artifacts": [artifact]}
    state_hash = _hash_json(packet)
    packet["deterministic_hash"] = state_hash
    receipt = {"run_id": "test-a", "current_state_hash": state_hash}
    receipt_hash = _hash_json(receipt)
    receipt["receipt_hash"] = receipt_hash
    return (state_hash, state, packet, receipt_hash, receipt)


def test_artifact_separates_observed_tests_from_seeded_claim():
    partial = {"command": ["python", "-m", "unittest", "test_workstate.ClaimTests"],
               "exit_code": 0, "stdout": "", "stderr": "Ran 4 tests; OK"}
    full = {"exit_code": 1, "stderr": "FAILED (failures=2)"}
    result = {"final_test": partial, "diff": "actual diff"}
    artifact = handoff.make_artifact("test-a", "A", result, "source", full, "policy-hash")
    assert artifact["claims"][0]["verification_status"] == "verified"
    assert artifact["claims"][1]["verification_status"] == "unverified"
    assert artifact["evidence"]["partial_test"] == partial
    assert artifact["evidence"]["full_test"] == full
    assert "scope_probes" not in artifact["evidence"]
    assert artifact["open_loops"]


def test_handoff_reads_exact_run_from_database(monkeypatch):
    queries = []

    class Cursor:
        def __enter__(self):
            self.rows = iter([handoff_row()])
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query, params):
            queries.append((query, params))

        def fetchone(self):
            return next(self.rows)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(handoff.psycopg, "connect", lambda *args, **kwargs: Connection())
    stored = handoff.load_handoff("stub-url", "test-a")
    assert stored["artifact"]["evidence"]["diff"] == "stored diff"
    assert stored["receipt_hash"] == handoff_row()[3]
    assert all(params[0] == "test-a" for _, params in queries)
    assert "cs.packet_json" in queries[0][0]
    assert queries[-1][1] == ("test-a",)


def test_b_artifact_binds_consumed_handoff_without_private_metadata():
    from cli import yare
    parent = {"run_id": "a-original", "current_state_hash": "consumed-state",
              "receipt_hash": "consumed-receipt", "private_metadata": "must not copy"}
    test = {"command": ["python", "-m", "unittest"], "exit_code": 0, "stdout": "6 passed", "stderr": ""}
    result = {"final_test": test, "diff": "B patch"}
    artifact = handoff.make_artifact("test-b", "B", result, "source", test, "policy", parent_handoff=parent)
    expected = {key: parent[key] for key in ("run_id", "current_state_hash", "receipt_hash")}
    assert artifact["evidence"]["parent_handoff"] == expected
    normalized = yare._lead_normalize_artifact(artifact, "artifact:b", 1)
    assert normalized["evidence"]["parent_handoff"] == expected
    parent["current_state_hash"] = "later-recompile"
    assert artifact["evidence"]["parent_handoff"]["current_state_hash"] == "consumed-state"


def test_a_artifact_does_not_invent_parent_provenance():
    test = {"command": ["python"], "exit_code": 0, "stdout": "passed"}
    artifact = handoff.make_artifact("test-a", "A", {"final_test": test, "diff": "patch"},
                                     "source", test, "policy")
    assert "parent_handoff" not in artifact["evidence"]


@pytest.mark.parametrize("corruption", ["state", "receipt", "source", "missing_packet"])
def test_handoff_rejects_corrupted_snapshot_before_code_use(monkeypatch, corruption):
    from unittest.mock import MagicMock
    row = list(handoff_row())
    if corruption == "state":
        row[2]["artifacts"][0]["evidence"]["source_code"] = "other revision"
    elif corruption == "receipt":
        row[4]["run_id"] = "other-run"
    elif corruption == "source":
        row[2]["artifacts"][0]["evidence"]["source_sha256"] = "wrong"
        material = {key: value for key, value in row[2].items() if key != "deterministic_hash"}
        row[0] = _hash_json(material)
        row[2]["deterministic_hash"] = row[0]
        row[4]["current_state_hash"] = row[0]
        row[3] = _hash_json({key: value for key, value in row[4].items() if key != "receipt_hash"})
        row[4]["receipt_hash"] = row[3]
    else:
        row[2] = None
    connection = MagicMock()
    connection.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = tuple(row)
    monkeypatch.setattr(handoff.psycopg, "connect", lambda *args, **kwargs: connection)
    with pytest.raises(ValueError, match="Stored handoff|Durable handoff"):
        handoff.load_handoff("stub-url", "test-a")


def test_original_source_access_requires_effective_policy_and_denial(tmp_path, monkeypatch):
    source = tmp_path / "workstate.py"
    source.write_text("existing task source\n")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    class Repo:
        cli = ["openshell"]
        sandbox = "test-sandbox"

        def __init__(self, result):
            self.result = result

        def execute(self, *command):
            assert command == ("sha256sum", handoff.ORIGINAL_SOURCE)
            return {"command": list(command), **self.result}

    def policy_for(read_only):
        payload = {"status": "effective", "hash": "effective-hash", "policy": {
            "filesystem_policy": {"read_only": read_only, "read_write": ["/tmp/yare-task"]}}}
        monkeypatch.setattr(handoff.subprocess, "run", lambda *args, **kwargs:
                            SimpleNamespace(returncode=0, stdout=json.dumps(payload)))

    policy_for(["/opt/yare-original-checkout"])
    a = handoff.capture_original_source_access(
        Repo({"exit_code": 0, "stdout": source_hash + "  " + handoff.ORIGINAL_SOURCE, "stderr": ""}),
        source, "a")
    assert a["policy_allows_read"] and a["source_sha256"] == source_hash

    policy_for(["/usr"])
    b = handoff.capture_original_source_access(
        Repo({"exit_code": 1, "stdout": "", "stderr": "Permission denied"}), source, "b")
    assert not b["policy_allows_read"] and b["exit_code"] == 1
    with pytest.raises(ValueError, match="enforced source-access denial"):
        handoff.capture_original_source_access(
            Repo({"exit_code": 1, "stdout": "", "stderr": "No such file or directory"}), source, "b")

    policy_for(["/opt/yare-original-checkout"])
    with pytest.raises(ValueError, match="policy does not match"):
        handoff.capture_original_source_access(
            Repo({"exit_code": 1, "stdout": "", "stderr": "Permission denied"}), source, "b")
