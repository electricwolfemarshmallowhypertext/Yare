from copy import deepcopy

from cli import integrity
from cli import storage, yare
from cli.yare import _lead_collect_artifact_paths, _lead_load_artifacts_from_file


def packet():
    return {"hash_version": "work-state.v2", "task": "task", "current_state": {"what_changed": ["task.py"]},
            "artifacts": [{"run_id": "run-a", "claims_made": [], "source_artifact": "source.json",
                           "git_state": {"commit": "first"}}], "proof": {"git_state": {"dirty": False}},
            "validation": {"ok": True}}


def test_content_identity_ignores_compile_metadata_and_paths():
    before = packet()
    after = deepcopy(before)
    after["proof"] = {"git_state": {"dirty": True, "commit": "unrelated"}}
    after["validation"] = {"ok": False, "errors": ["unrelated local change"]}
    after["artifacts"][0]["source_artifact"] = "another-name.json"
    after["artifacts"][0]["git_state"] = {"commit": "other"}
    assert integrity.state_hash(before) == integrity.state_hash(after)
    assert integrity.digest(before) != integrity.digest(after)


def test_content_change_changes_identity():
    before = packet()
    after = deepcopy(before)
    after["current_state"]["what_changed"] = ["other.py"]
    assert integrity.state_hash(before) != integrity.state_hash(after)


def test_legacy_packet_hash_stays_compatible():
    original = {"task": "legacy", "current_state": {}}
    original["deterministic_hash"] = integrity.digest(original)
    assert integrity.state_hash(original) == original["deterministic_hash"]


def test_discovery_does_not_ingest_receipts(tmp_path):
    for directory in ("receipts", ".sticky/receipts"):
        path = tmp_path / directory
        path.mkdir(parents=True)
        (path / "old.jsonl").write_text('{}\n')
    assert _lead_collect_artifact_paths(tmp_path, []) == []


def test_external_artifact_identifier_has_no_host_path(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text('{"run_id":"a"}')
    records, warnings = _lead_load_artifacts_from_file(tmp_path / "other-root", path)
    assert not warnings
    assert records[0][1].startswith("artifact.json@sha256:")
    assert str(tmp_path) not in records[0][1]


def test_unverified_restatement_does_not_dispute_supported_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(yare, "validate_workspace", lambda root: {"ok": True, "errors": [], "warnings": []})
    monkeypatch.setattr(yare, "_git_state", lambda root: {})
    claim = "The targeted test passed"
    first = yare._lead_normalize_artifact({"run_id": "a", "claims": [{"claim": claim,
        "verification_status": "verified", "evidence": {"kind": "test", "claim": claim,
        "command": ["python", "-m", "unittest"], "exit_code": 0, "expected_exit_code": 0,
        "stdout": "OK"}}]}, "first", 1)
    second = yare._lead_normalize_artifact({"run_id": "b", "claims": [{"claim": claim,
        "verification_status": "unverified"}]}, "second", 1)
    state = yare._lead_compile_packet(tmp_path, [first, second], "task")["current_state"]
    assert state["what_is_true"] == [claim]
    assert state["what_is_unverified"] == []
    assert state["what_contradicts_prior_state"] == []


def test_diff_reports_files_and_open_loops():
    result = storage.diff_states({"what_changed": ["old.py"], "open_loops": ["old work"]},
                                 {"what_changed": ["new.py"], "open_loops": ["new work"]})
    assert result["new_files"] == ["new.py"]
    assert result["removed_files"] == ["old.py"]
    assert result["new_open_loops"] == ["new work"]
    assert result["removed_open_loops"] == ["old work"]
