from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cli.agentmd import app


runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def ws() -> Path:
    base = REPO_ROOT / ".tmp" / "agentmd-tests"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="case-", dir=base))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def scaffold_workspace(root: Path) -> None:
    (root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (root / "agentmd.yaml").write_text(
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
    (ws / "agentmd.yaml").write_text(
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
