import json

import pytest
from typer.testing import CliRunner

from cli import yare


def artifact(task="task", run_id="fixture"):
    return {"schema_version": "lead-artifact.v1", "run_id": run_id, "tool": "fixture", "task": task,
            "timestamp": "2026-11-25T00:00:00Z", "claims": [], "decisions": [], "files_touched": [],
            "open_loops": [], "contradictions": [], "human_approval_items": [], "verification_status": "unverified"}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(yare, "validate_workspace", lambda root: {"ok": True, "errors": [], "warnings": []})
    monkeypatch.setattr(yare, "_git_state", lambda root: {"available": False})
    monkeypatch.setattr(yare.storage_backend, "persist_lead_compile", lambda **kwargs: pytest.fail("Invalid input reached persistence"))
    monkeypatch.setattr(yare.archive_backend, "archive_lead_compile", lambda **kwargs: pytest.fail("Invalid input reached archive"))
    directory = tmp_path / ".yare/captures"
    directory.mkdir(parents=True)
    previous = tmp_path / ".sticky/current-state.json"
    previous.parent.mkdir()
    previous.write_text("previous state")
    return tmp_path


@pytest.mark.parametrize("name,raw", [
    ("bad.json", "{"),
    ("bad.jsonl", json.dumps(artifact()) + "\n{\n"),
    ("bad.json", json.dumps({**artifact(), "schema_version": "unsupported"})),
    ("bad.json", json.dumps({**artifact(), "claims": "invalid"})),
    ("bad.json", "[]"),
    ("bad.jsonl", "\n"),
])
def test_invalid_discovered_input_fails_before_any_sink(workspace, name, raw):
    (workspace / ".yare/captures" / name).write_text(raw)
    with pytest.raises(ValueError, match="artifact_.*invalid|input_empty"):
        yare.compile_lead_state(workspace, None, [])
    assert (workspace / ".sticky/current-state.json").read_text() == "previous state"
    assert not (workspace / ".sticky/receipts").exists()


def test_no_discovered_artifacts_cannot_create_synthetic_state(workspace):
    with pytest.raises(ValueError, match="input_empty"):
        yare.compile_lead_state(workspace, "task", [])


def test_validation_cannot_be_disabled(workspace):
    with pytest.raises(ValueError, match="validation_required"):
        yare.compile_lead_state(workspace, "task", [], validate_artifacts=False)


def test_cli_discovery_uses_validation(workspace):
    (workspace / ".yare/captures/bad.json").write_text('{"claims": "invalid"}')
    result = CliRunner().invoke(yare.app, ["lead", "compile", "--root", str(workspace)])
    assert result.exit_code == 1
    assert "lead_artifact_schema_invalid" in result.stdout


def test_named_test_evidence_is_included_in_schema_validation(workspace):
    record = artifact()
    record["evidence"] = {"test_run": {"kind": "test", "claim": "Tests passed", "command": ["test"],
                                        "exit_code": "not an integer", "expected_exit_code": 0, "stdout": "OK"}}
    (workspace / ".yare/captures/bad.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="lead_artifact_schema_invalid"):
        yare.compile_lead_state(workspace, None, [])


def test_valid_discovered_artifact_compiles_with_stubbed_sinks(workspace, monkeypatch):
    (workspace / ".yare/captures/valid.json").write_text(json.dumps(artifact()))
    saved = []
    monkeypatch.setattr(yare.storage_backend, "persist_lead_compile", lambda **kwargs: saved.append(kwargs))
    monkeypatch.setattr(yare.archive_backend, "archive_lead_compile", lambda **kwargs: [])
    packet, *_ = yare.compile_lead_state(workspace, None, [])
    assert packet["task"] == "task"
    assert len(saved) == 1
    assert len(packet["artifacts"]) == 1


@pytest.mark.parametrize("override", [None, "task B", "combined task"])
def test_mixed_tasks_are_rejected_before_persistence(workspace, override):
    for task, run_id in (("task A", "a"), ("task B", "b")):
        (workspace / ".yare/captures" / (run_id + ".json")).write_text(json.dumps(artifact(task, run_id)))
    with pytest.raises(ValueError, match="task_mismatch"):
        yare.compile_lead_state(workspace, override, [])
    assert (workspace / ".sticky/current-state.json").read_text() == "previous state"


def test_task_aggregation_requires_an_explicit_name(workspace):
    (workspace / ".yare/captures/a.json").write_text(json.dumps(artifact("task A", "a")))
    with pytest.raises(ValueError, match="aggregate_task_required"):
        yare.compile_lead_state(workspace, None, [], aggregate_tasks=True)


def test_explicit_named_aggregation_preserves_each_source_task(workspace, monkeypatch):
    for task, run_id in (("task A", "a"), ("task B", "b")):
        (workspace / ".yare/captures" / (run_id + ".json")).write_text(json.dumps(artifact(task, run_id)))
    monkeypatch.setattr(yare.storage_backend, "persist_lead_compile", lambda **kwargs: False)
    monkeypatch.setattr(yare.archive_backend, "archive_lead_compile", lambda **kwargs: [])
    result = CliRunner().invoke(yare.app, ["lead", "compile", "--root", str(workspace),
                                         "--aggregate-tasks", "--task", "combined task"])
    assert result.exit_code == 0, result.stdout
    packet = json.loads((workspace / ".sticky/current-state.json").read_text())
    assert packet["task"] == "combined task"
    assert {item["task"] for item in packet["artifacts"]} == {"task A", "task B"}
