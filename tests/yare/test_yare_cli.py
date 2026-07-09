from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cli import archive as archive_backend
from cli import storage as storage_backend
from cli.yare import app


runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def ws() -> Path:
    base = REPO_ROOT / ".tmp" / "yare-tests"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="case-", dir=base))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def scaffold_workspace(root: Path) -> None:
    (root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (root / "yare.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "limits:",
                "  max_file_bytes: 131072",
                "  max_total_bytes: 524288",
                "resolve:",
                "  max_skills: 4",
                "  max_memory: 4",
                "  max_policies: 4",
                "  max_evals: 4",
                "skills:",
                "  required_metadata: [id, name, description, version, permissions]",
                "  forbidden_permissions: [filesystem:write_outside_workspace]",
            ]
        ),
        encoding="utf-8",
    )
    (root / "skills" / "s1").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "s1" / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "id: skill.s1",
                "name: Repo Drift Scan",
                "description: scan for context drift",
                "version: 1.0.0",
                "permissions:",
                "  - filesystem:read",
                "---",
                "",
                "# Skill",
                "Use for context drift checks.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "memory").mkdir(parents=True, exist_ok=True)
    (root / "memory" / "state.md").write_text("Current repo context state.\n", encoding="utf-8")
    (root / "policies").mkdir(parents=True, exist_ok=True)
    (root / "policies" / "p1.yaml").write_text("id: p1\nrules: []\n", encoding="utf-8")
    (root / "evals").mkdir(parents=True, exist_ok=True)
    (root / "evals" / "e1.jsonl").write_text('{"id":"e1","task":"drift"}\n', encoding="utf-8")
    (root / "receipts").mkdir(parents=True, exist_ok=True)


def test_doctor_passes_with_valid_scaffold(ws: Path) -> None:
    scaffold_workspace(ws)
    result = runner.invoke(app, ["doctor", "--root", str(ws)])
    assert result.exit_code == 0
    assert "doctor: PASS" in result.stdout


def test_doctor_fails_missing_agents_md(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "AGENTS.md").unlink()
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(check["name"] == "agents_exists" and check["ok"] is False for check in payload["checks"])


def test_doctor_fails_invalid_yaml_policy(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "policies" / "p1.yaml").write_text("rules: [good, bad\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("policy_yaml_invalid:" in err for err in payload["errors"])


def test_doctor_fails_invalid_jsonl_eval(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "evals" / "e1.jsonl").write_text('{"id":"ok"}\n{"id":\n', encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("eval_jsonl_invalid:" in err for err in payload["errors"])


def test_doctor_fails_duplicate_skill_ids(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "skills" / "s2").mkdir(parents=True, exist_ok=True)
    (ws / "skills" / "s2" / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "id: skill.s1",
                "name: Duplicate Skill",
                "description: duplicate ID should fail",
                "version: 1.0.0",
                "permissions:",
                "  - filesystem:read",
                "---",
                "",
                "# Duplicate",
            ]
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["doctor", "--root", str(ws), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any("duplicate_skill_id:" in err for err in payload["errors"])


def test_resolve_includes_selected_and_excluded_reasons(ws: Path) -> None:
    scaffold_workspace(ws)
    (ws / "yare.yaml").write_text(
        "\n".join(
            [
                "version: 1",
                "resolve:",
                "  max_skills: 1",
                "  max_memory: 4",
                "  max_policies: 4",
                "  max_evals: 4",
                "skills:",
                "  required_metadata: [id, name, description, version, permissions]",
                "  forbidden_permissions: [filesystem:write_outside_workspace]",
            ]
        ),
        encoding="utf-8",
    )
    (ws / "skills" / "s2").mkdir(parents=True, exist_ok=True)
    (ws / "skills" / "s2" / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "id: skill.s2",
                "name: Drift Skill Two",
                "description: also mentions context drift",
                "version: 1.0.0",
                "permissions:",
                "  - filesystem:read",
                "---",
                "",
                "# Skill",
                "Also checks context drift.",
            ]
        ),
        encoding="utf-8",
    )
    output_path = ws / "custom-output" / "resolved.json"
    result = runner.invoke(
        app,
        [
            "resolve",
            "--root",
            str(ws),
            "--task",
            "review this repo for context drift",
            "--output",
            str(output_path),
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert output_path.exists()
    data = json.loads(result.stdout)
    assert data["task"] == "review this repo for context drift"
    assert data["selected"]
    assert data["excluded"]
    assert all("reason" in item for item in data["selected"])
    assert all("reason" in item for item in data["excluded"])
    assert data["context_bundle_hash"]


def test_receipt_includes_git_or_non_git_metadata(ws: Path) -> None:
    scaffold_workspace(ws)
    resolve_result = runner.invoke(
        app,
        ["resolve", "--root", str(ws), "--task", "generate an auditable receipt"],
    )
    assert resolve_result.exit_code == 0

    receipt_result = runner.invoke(app, ["receipt", "--root", str(ws)])
    assert receipt_result.exit_code == 0

    receipt_files = sorted((ws / "receipts").glob("*.jsonl"))
    assert receipt_files
    payload = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    assert payload["task"] == "generate an auditable receipt"
    assert "adapter" in payload
    assert isinstance(payload["selected_context_files"], list)
    assert isinstance(payload["file_hashes"], dict)
    assert payload["context_bundle_hash"]
    assert payload["receipt_hash"]
    assert "git_commit" in payload
    assert "git_dirty" in payload
    assert "changed_files" in payload
    assert "untracked_files" in payload
    if payload["git_available"]:
        assert payload["git_reason"] is None
        assert isinstance(payload["git_commit"], str) and payload["git_commit"]
    else:
        assert payload["git_reason"] == "not_a_git_repository"
        assert payload["git_commit"] is None


def test_receipt_uses_last_custom_resolved_output(ws: Path) -> None:
    scaffold_workspace(ws)
    custom_output = ws / "custom" / "resolved.json"
    resolve_result = runner.invoke(
        app,
        [
            "resolve",
            "--root",
            str(ws),
            "--task",
            "review this repo for context drift",
            "--output",
            str(custom_output),
        ],
    )
    assert resolve_result.exit_code == 0
    assert custom_output.exists()

    receipt_result = runner.invoke(app, ["receipt", "--root", str(ws)])
    assert receipt_result.exit_code == 0

    receipt_files = sorted((ws / "receipts").glob("*.jsonl"))
    payload = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    assert payload["resolved_context_file"] == "custom/resolved.json"
    assert payload["selected_context_files"], "receipt should include selected context from last custom resolved output"
    assert payload["context_bundle_hash"]



def test_lead_compile_ingests_artifact_and_writes_outputs(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "artifacts.jsonl"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "run-1",
                "timestamp": "2026-05-20T00:00:00Z",
                "agent": "codex",
                "task": "compile current state",
                "files_touched": ["memory/state.md"],
                "claims_made": [{"claim": "AGENTS.md exists", "verification_status": "verified"}],
                "decisions_made": [{"decision": "Defer deployment", "requires_human_approval": True}],
                "open_loops": ["Confirm policy owner"],
                "verification_status": "partial",
                "context_bundle_hash": "bundle-abc",
                "receipt_hash": "receipt-abc",
                "changed_files": ["AGENTS.md"],
                "untracked_files": ["notes/tmp.md"],
                "git_available": False,
                "git_reason": "not_a_git_repository",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)],
    )
    assert result.exit_code == 0

    state_json = ws / ".sticky" / "current-state.json"
    state_md = ws / ".sticky" / "current-state.md"
    assert state_json.exists()
    assert state_md.exists()

    payload = json.loads(state_json.read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 1
    assert payload["task"] == "compile current state"
    assert payload["proof"]["run_id"] == "run-1"
    assert payload["proof"]["context_bundle_hash"] == "bundle-abc"
    assert "AGENTS.md" in payload["current_state"]["what_changed"]
    loop_texts = {loop["text"] for loop in payload["current_state"]["open_loops"]}
    assert "Confirm policy owner" in loop_texts

    receipt_files = sorted((ws / ".sticky" / "receipts").glob("*.jsonl"))
    assert receipt_files


def test_lead_compile_is_deterministic_for_same_artifact_input(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "lead-input.jsonl"
    artifact = {
        "schema_version": "lead-artifact.v1",
        "run_id": "stable-run",
        "tool": "codex",
        "timestamp": "2026-05-20T01:02:03Z",
        "task": "deterministic packet",
        "files_touched": ["memory/state.md", "policies/p1.yaml"],
        "claims_made": [{"claim": "policy loaded", "verification_status": "verified"}],
        "open_loops": ["confirm reviewer"],
        "context_bundle_hash": "bundle-stable",
        "receipt_hash": "receipt-stable",
        "git_available": False,
        "git_reason": "not_a_git_repository",
    }
    artifact_path.write_text(json.dumps(artifact) + "\n", encoding="utf-8")

    first = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert first.exit_code == 0
    first_payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))

    second = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert second.exit_code == 0
    second_payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))

    assert first_payload == second_payload
    assert first_payload["deterministic_hash"] == second_payload["deterministic_hash"]


def test_lead_compile_preserves_contradictions_and_open_loops(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "contradictions.jsonl"
    artifact_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "lead-artifact.v1",
                        "run_id": "r1",
                        "tool": "codex",
                        "timestamp": "2026-05-20T00:00:00Z",
                        "task": "check contradiction handling",
                        "claims_made": [{"claim": "service door was sealed", "verification_status": "verified"}],
                        "open_loops": ["Find Mara"],
                    }
                ),
                json.dumps(
                    {
                        "schema_version": "lead-artifact.v1",
                        "run_id": "r2",
                        "tool": "claude",
                        "timestamp": "2026-05-20T00:01:00Z",
                        "task": "check contradiction handling",
                        "claims_made": [{"claim": "service door was sealed", "verification_status": "contradicted"}],
                        "open_loops": ["Inspect pantry"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 0

    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    contradictions = payload["current_state"]["what_contradicts_prior_state"]
    assert any("service door was sealed" in item for item in contradictions)

    open_loop_texts = {loop["text"] for loop in payload["current_state"]["open_loops"]}
    assert open_loop_texts == {"Find Mara", "Inspect pantry"}
    approvals = payload["current_state"]["what_needs_human_approval"]
    assert any(item.startswith("Resolve contradiction: service door was sealed") for item in approvals)



def test_lead_compile_rejects_invalid_artifact_schema(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "invalid-artifact.jsonl"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "bad-run",
                "task": "missing required schema fields",
                "timestamp": "2026-05-20T11:00:00Z",
                "claims": "should-be-array",
                "decisions": [],
                "files_touched": [],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "verified",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 1
    assert "lead_artifact_schema_invalid" in result.stdout


def test_lead_compile_rejects_missing_schema_version(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "missing-schema-version.json"
    artifact_path.write_text(
        json.dumps(
            {
                "run_id": "missing-version",
                "tool": "codex",
                "task": "missing schema version",
                "timestamp": "2026-05-20T11:30:00Z",
                "claims": [],
                "decisions": [],
                "files_touched": [],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "unverified",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 1
    assert "schema_version" in result.stdout


def test_lead_compile_accepts_valid_artifact_schema(ws: Path) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "valid-artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "valid-run",
                "tool": "codex",
                "task": "validate schema",
                "timestamp": "2026-05-20T12:00:00Z",
                "claims": [{"claim": "schema exists", "verification_status": "verified"}],
                "decisions": [{"decision": "accept artifact", "status": "verified"}],
                "files_touched": ["README.md"],
                "open_loops": ["confirm rollout"],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "verified",
                "context_bundle_hash": "bundle-valid",
                "receipt_hash": "receipt-valid",
                "source_artifacts": ["tool-output/123"],
                "git_state": {
                    "available": False,
                    "commit": None,
                    "dirty": None,
                    "changed_files": [],
                    "untracked_files": [],
                    "reason": "external",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])
    assert result.exit_code == 0
    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 1


def test_lead_compile_demo_artifacts_still_compile(ws: Path) -> None:
    scaffold_workspace(ws)
    demo_dir = REPO_ROOT / "examples" / "lead-artifacts"
    result = runner.invoke(
        app,
        [
            "lead",
            "compile",
            "--root",
            str(ws),
            "--artifact",
            str(demo_dir / "run-codex.jsonl"),
            "--artifact",
            str(demo_dir / "run-claude.json"),
            "--artifact",
            str(demo_dir / "run-gemini.jsonl"),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 3
    assert payload["proof"]["run_id"] == "demo-run-003"


def test_lead_compile_template_artifact_compiles(ws: Path) -> None:
    scaffold_workspace(ws)
    template_path = REPO_ROOT / "examples" / "lead-artifacts" / "template.lead-artifact.json"
    result = runner.invoke(
        app,
        [
            "lead",
            "compile",
            "--root",
            str(ws),
            "--artifact",
            str(template_path),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads((ws / ".sticky" / "current-state.json").read_text(encoding="utf-8"))
    assert payload["artifacts_ingested"] == 1
    assert payload["proof"]["run_id"] == "template-run-001"


def test_skill_apply_edit_accepts_and_writes_receipt(ws: Path) -> None:
    scaffold_workspace(ws)
    edit_path = ws / "accepted-edit.json"
    edit_path.write_text(
        json.dumps(
            {
                "schema_version": "skill-edit.v1",
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-accept-1",
                "edit_type": "replace",
                "target": "Use for context drift checks.",
                "replacement": "Use for context drift checks with validation gates.",
                "reason": "Improve held-out validation performance.",
                "baseline_score": 0.61,
                "validation_score": 0.74,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:00:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)])
    assert result.exit_code == 0
    assert "decision: accepted" in result.stdout

    skill_body = (ws / "skills" / "s1" / "SKILL.md").read_text(encoding="utf-8")
    assert "validation gates." in skill_body

    receipt_files = sorted((ws / ".sticky" / "skill-receipts").glob("*.jsonl"))
    assert receipt_files
    receipt = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    assert receipt["decision"] == "accepted"
    assert receipt["score_delta"] > 0
    assert receipt["old_hash"] != receipt["new_hash"]


def test_skill_apply_edit_rejects_and_writes_rejection_record(ws: Path) -> None:
    scaffold_workspace(ws)
    skill_path = ws / "skills" / "s1" / "SKILL.md"
    original = skill_path.read_text(encoding="utf-8")

    edit_path = ws / "rejected-edit.json"
    edit_path.write_text(
        json.dumps(
            {
                "schema_version": "skill-edit.v1",
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-reject-1",
                "edit_type": "replace",
                "target": "Use for context drift checks.",
                "replacement": "Use for context drift checks quickly.",
                "reason": "Try a shorter wording.",
                "baseline_score": 0.72,
                "validation_score": 0.58,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:10:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)])
    assert result.exit_code == 0
    assert "decision: rejected" in result.stdout
    assert skill_path.read_text(encoding="utf-8") == original

    rejection_files = sorted((ws / ".sticky" / "rejected-skill-edits").glob("*.jsonl"))
    assert rejection_files
    rejection = json.loads(rejection_files[-1].read_text(encoding="utf-8").strip())
    assert rejection["decision"] == "rejected"
    assert rejection["old_hash"] == rejection["new_hash"]
    assert rejection["score_delta"] < 0


def test_skill_apply_edit_fails_invalid_schema(ws: Path) -> None:
    scaffold_workspace(ws)
    edit_path = ws / "invalid-skill-edit.json"
    edit_path.write_text(
        json.dumps(
            {
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-invalid-1",
                "edit_type": "replace",
                "target": "Use for context drift checks.",
                "replacement": "Use for context drift checks with validation gates.",
                "reason": "Invalid payload should fail schema.",
                "baseline_score": 0.61,
                "validation_score": 0.74,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:20:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(edit_path)])
    assert result.exit_code == 1
    assert "skill_edit_schema_invalid" in result.stdout


def test_skill_apply_edit_fails_for_ambiguous_or_missing_target(ws: Path) -> None:
    scaffold_workspace(ws)
    skill_path = ws / "skills" / "s1" / "SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8") + "\nUse for context drift checks.\n",
        encoding="utf-8",
    )

    ambiguous_edit = ws / "ambiguous-skill-edit.json"
    ambiguous_edit.write_text(
        json.dumps(
            {
                "schema_version": "skill-edit.v1",
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-ambiguous-1",
                "edit_type": "replace",
                "target": "Use for context drift checks.",
                "replacement": "Use for context drift checks with validation gates.",
                "reason": "Ambiguous target should fail.",
                "baseline_score": 0.61,
                "validation_score": 0.74,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:30:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    ambiguous_result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(ambiguous_edit)])
    assert ambiguous_result.exit_code == 1
    assert "skill_edit_target_ambiguous" in ambiguous_result.stdout

    missing_edit = ws / "missing-target-skill-edit.json"
    missing_edit.write_text(
        json.dumps(
            {
                "schema_version": "skill-edit.v1",
                "skill_id": "skill.s1",
                "skill_path": "skills/s1/SKILL.md",
                "edit_id": "edit-missing-1",
                "edit_type": "replace",
                "target": "This target does not exist.",
                "replacement": "Replacement text.",
                "reason": "Missing target should fail.",
                "baseline_score": 0.61,
                "validation_score": 0.74,
                "validation_task": "repo context drift review",
                "evidence": ["eval:heldout-1"],
                "proposed_by": "test-suite",
                "timestamp": "2026-05-27T00:31:00Z",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    missing_result = runner.invoke(app, ["skill", "apply-edit", "--root", str(ws), "--edit", str(missing_edit)])
    assert missing_result.exit_code == 1
    assert "skill_edit_target_not_found" in missing_result.stdout


def test_storage_init_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YARE_DATABASE_URL", raising=False)

    result = runner.invoke(app, ["storage", "init"])

    assert result.exit_code == 1
    assert "YARE_DATABASE_URL" in result.stdout


def test_storage_init_command_initializes_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_init_schema() -> None:
        called["ok"] = True

    monkeypatch.setattr(storage_backend, "init_schema", fake_init_schema)

    result = runner.invoke(app, ["storage", "init"])

    assert result.exit_code == 0
    assert called["ok"] is True
    assert "yare_runs" in result.stdout
    assert "yare_receipts" in result.stdout


def test_lead_compile_persists_when_database_url_is_set(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scaffold_workspace(ws)
    artifact_path = ws / "artifact.jsonl"
    artifact_path.write_text(
        json.dumps(
            {
                "schema_version": "lead-artifact.v1",
                "run_id": "run-db-1",
                "tool": "codex",
                "timestamp": "2026-05-20T00:00:00Z",
                "task": "persist durable memory",
                "claims": [{"claim": "state compiled", "verification_status": "verified"}],
                "decisions": [],
                "files_touched": ["AGENTS.md"],
                "open_loops": [],
                "contradictions": [],
                "human_approval_items": [],
                "verification_status": "verified",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_persist_lead_compile(
        *,
        packet: dict[str, object],
        artifacts: list[dict[str, object]],
        receipt: dict[str, object],
    ) -> bool:
        captured["packet"] = packet
        captured["artifacts"] = artifacts
        captured["receipt"] = receipt
        return True

    monkeypatch.setenv("YARE_DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(storage_backend, "persist_lead_compile", fake_persist_lead_compile)

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--artifact", str(artifact_path)])

    assert result.exit_code == 0
    packet = captured["packet"]
    artifacts = captured["artifacts"]
    receipt = captured["receipt"]
    assert isinstance(packet, dict)
    assert isinstance(artifacts, list)
    assert isinstance(receipt, dict)
    assert packet["task"] == "persist durable memory"
    assert packet["deterministic_hash"]
    assert artifacts[0]["run_id"] == "run-db-1"
    assert receipt["receipt_hash"]
    assert (ws / ".sticky" / "current-state.json").exists()


def test_storage_persist_skips_when_database_url_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YARE_DATABASE_URL", raising=False)

    persisted = storage_backend.persist_lead_compile(packet={}, artifacts=[], receipt={})

    assert persisted is False


class FakeCursor:
    def __init__(self, calls: list[tuple[str, object]]) -> None:
        self.calls = calls

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def execute(self, sql: str, params: object = None) -> None:
        self.calls.append((sql, params))


class FakeConnection:
    def __init__(self, calls: list[tuple[str, object]]) -> None:
        self.calls = calls
        self.commits = 0

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.calls)

    def commit(self) -> None:
        self.commits += 1


def test_storage_persist_executes_schema_and_inserts_with_stubbed_connection() -> None:
    calls: list[tuple[str, object]] = []
    connections: list[FakeConnection] = []

    def fake_connect(database_url: str) -> FakeConnection:
        assert database_url == "postgresql://example"
        conn = FakeConnection(calls)
        connections.append(conn)
        return conn

    packet = {
        "task": "persist durable memory",
        "deterministic_hash": "state-hash",
        "current_state": {"next_clean_action": "ship it"},
        "proof": {"run_id": "run-db-1"},
    }
    artifacts = [{"run_id": "run-db-1", "source_artifact": "artifact.jsonl:1"}]
    receipt = {"receipt_hash": "receipt-hash", "current_state_hash": "state-hash"}

    persisted = storage_backend.persist_lead_compile(
        packet=packet,
        artifacts=artifacts,
        receipt=receipt,
        database_url="postgresql://example",
        connect_func=fake_connect,
    )

    sql = "\n".join(call[0] for call in calls)
    assert persisted is True
    assert connections[0].commits == 1
    assert "CREATE TABLE IF NOT EXISTS yare_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS yare_lead_artifacts" in sql
    assert "CREATE TABLE IF NOT EXISTS yare_current_states" in sql
    assert "CREATE TABLE IF NOT EXISTS yare_receipts" in sql
    assert "INSERT INTO yare_runs" in sql
    assert "INSERT INTO yare_lead_artifacts" in sql
    assert "INSERT INTO yare_current_states" in sql
    assert "INSERT INTO yare_receipts" in sql


def test_s3_archive_skips_when_bucket_unset(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YARE_S3_BUCKET", raising=False)
    state_json = ws / "current-state.json"
    state_md = ws / "current-state.md"
    receipt = ws / "receipt.jsonl"
    state_json.write_text("{}", encoding="utf-8")
    state_md.write_text("# state\n", encoding="utf-8")
    receipt.write_text("{}\n", encoding="utf-8")

    uris = archive_backend.archive_lead_compile(
        packet={"deterministic_hash": "hash-1"},
        json_path=state_json,
        md_path=state_md,
        receipt_path=receipt,
    )

    assert uris == []


class FakeS3Client:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, str]] = []

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.uploads.append((filename, bucket, key))


def test_s3_archive_uploads_expected_keys(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARE_S3_BUCKET", "example-bucket")
    monkeypatch.delenv("YARE_S3_PREFIX", raising=False)
    state_json = ws / "current-state.json"
    state_md = ws / "current-state.md"
    receipt = ws / "receipt.jsonl"
    state_json.write_text("{}", encoding="utf-8")
    state_md.write_text("# state\n", encoding="utf-8")
    receipt.write_text("{}\n", encoding="utf-8")
    client = FakeS3Client()

    uris = archive_backend.archive_lead_compile(
        packet={"deterministic_hash": "hash-1"},
        json_path=state_json,
        md_path=state_md,
        receipt_path=receipt,
        client=client,
    )

    keys = [upload[2] for upload in client.uploads]
    assert keys == [
        "yare/current-states/hash-1/current-state.json",
        "yare/current-states/hash-1/current-state.md",
        "yare/current-states/hash-1/receipt.jsonl",
    ]
    assert uris == [
        "s3://example-bucket/yare/current-states/hash-1/current-state.json",
        "s3://example-bucket/yare/current-states/hash-1/current-state.md",
        "s3://example-bucket/yare/current-states/hash-1/receipt.jsonl",
    ]


def test_s3_archive_honors_custom_prefix(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARE_S3_BUCKET", "example-bucket")
    monkeypatch.setenv("YARE_S3_PREFIX", "demo/prefix")
    state_json = ws / "current-state.json"
    state_md = ws / "current-state.md"
    receipt = ws / "receipt.jsonl"
    state_json.write_text("{}", encoding="utf-8")
    state_md.write_text("# state\n", encoding="utf-8")
    receipt.write_text("{}\n", encoding="utf-8")
    client = FakeS3Client()

    archive_backend.archive_lead_compile(
        packet={"deterministic_hash": "hash-1"},
        json_path=state_json,
        md_path=state_md,
        receipt_path=receipt,
        client=client,
    )

    assert client.uploads[0][2] == "demo/prefix/current-states/hash-1/current-state.json"


def test_lead_compile_prints_s3_uris(ws: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scaffold_workspace(ws)

    def fake_archive_lead_compile(**kwargs: object) -> list[str]:
        return ["s3://example-bucket/yare/current-states/hash/current-state.json"]

    monkeypatch.setattr(archive_backend, "archive_lead_compile", fake_archive_lead_compile)

    result = runner.invoke(app, ["lead", "compile", "--root", str(ws), "--task", "archive state"])

    assert result.exit_code == 0
    assert "s3_uri: s3://example-bucket/yare/current-states/hash/current-state.json" in result.stdout
