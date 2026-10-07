import hashlib
import json
from types import SimpleNamespace

import pytest

from producers import handoff


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
            self.rows = iter([("state-hash", {"task": "fix"}),
                              ({"evidence": {"diff": "stored diff"}},), ("receipt-hash",)])
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
    assert stored["receipt_hash"] == "receipt-hash"
    assert all(params[0] == "test-a" for _, params in queries)
    assert queries[-1][1] == ("test-a", "state-hash")


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
