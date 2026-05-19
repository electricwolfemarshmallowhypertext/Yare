from __future__ import annotations

import json
from pathlib import Path
import sys

from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cli.agentmd import app


runner = CliRunner()


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


def test_doctor_passes_with_valid_scaffold(tmp_path: Path) -> None:
    scaffold_workspace(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "doctor: PASS" in result.stdout


def test_resolve_writes_explainable_context_file(tmp_path: Path) -> None:
    scaffold_workspace(tmp_path)
    result = runner.invoke(
        app,
        ["resolve", "--root", str(tmp_path), "--task", "review this repo for context drift"],
    )
    assert result.exit_code == 0
    output_path = tmp_path / ".agentmd" / "resolved-context.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["task"] == "review this repo for context drift"
    assert data["selected"]
    assert any(item["path"] == "AGENTS.md" for item in data["selected"])
    assert all("reason" in item for item in data["selected"])
    assert "excluded" in data


def test_receipt_writes_jsonl_with_hashes(tmp_path: Path) -> None:
    scaffold_workspace(tmp_path)
    resolve_result = runner.invoke(
        app,
        ["resolve", "--root", str(tmp_path), "--task", "generate an auditable receipt"],
    )
    assert resolve_result.exit_code == 0

    receipt_result = runner.invoke(app, ["receipt", "--root", str(tmp_path)])
    assert receipt_result.exit_code == 0

    receipt_files = sorted((tmp_path / "receipts").glob("*.jsonl"))
    assert receipt_files
    payload = json.loads(receipt_files[-1].read_text(encoding="utf-8").strip())
    assert payload["receipt_hash"]
    assert payload["validation"]["ok"] is True
    assert isinstance(payload["selected_context_files"], list)
