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
