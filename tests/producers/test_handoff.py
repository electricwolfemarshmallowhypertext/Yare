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
