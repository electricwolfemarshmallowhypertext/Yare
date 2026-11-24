import json
from pathlib import Path

import pytest

from cli import skill_evaluation, yare


@pytest.fixture
def gate(tmp_path):
    root = tmp_path.resolve()
    skill = root / "skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Use evidence.\n", encoding="utf-8")
    schemas = root / "schemas"
    schemas.mkdir()
    source = Path(__file__).resolve().parents[2] / "schemas/skill-edit.schema.json"
    (schemas / source.name).write_bytes(source.read_bytes())
    program = root / "scripts/evaluator.py"
    program.parent.mkdir()
    program.write_text(
        "import hashlib, json, sys\nfrom pathlib import Path\n"
        "data = Path(sys.argv[1]).read_bytes()\n"
        "text = data.decode('utf-8')\n"
        "print(json.dumps({'skill_sha256': hashlib.sha256(data).hexdigest(), 'cases': [\n"
        " {'id': 'evidence', 'passed': 'Use evidence.' in text},\n"
        " {'id': 'check', 'passed': 'Check results.' in text}]}))\n", encoding="utf-8")
    config = root / ".yare/skill-evaluator.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"program": "scripts/evaluator.py",
                                 "program_sha256": skill_evaluation.digest(program)}))
    payload = {
        "schema_version": "skill-edit.v1", "skill_id": "example", "skill_path": "skills/example/SKILL.md",
        "edit_id": "fixture", "edit_type": "replace", "target": "Use evidence.",
        "replacement": "Use evidence. Check results.", "reason": "Fixture evaluation",
        "baseline_score": 0.99, "validation_score": 0.01, "validation_task": "Fixture checks",
        "evidence": [], "proposed_by": "fixture", "timestamp": "2026-10-12T00:00:00Z",
        "old_hash": skill_evaluation.digest(skill),
    }
    return root, skill, program, config, payload


def apply(gate):
    root, _, _, _, payload = gate
    edit = root / "edit.json"
    edit.write_text(json.dumps(payload), encoding="utf-8")
    return yare.apply_skill_edit(root, edit)


def test_acceptance_uses_actual_evaluation_not_proposal_scores(gate):
    decision, path, record = apply(gate)
    assert decision == "accepted"
    assert record["baseline_score"] == 0.5
    assert record["validation_score"] == 1.0
    assert record["scores_verified"] is True
    assert record["new_hash"] == skill_evaluation.digest(gate[1])
    assert record["evaluation"]["configuration_sha256"] == skill_evaluation.digest(gate[3])
    assert "Check results." in gate[1].read_text()
    assert json.loads(path.read_text())["decision"] == "accepted"


def test_forged_improvement_does_not_replace_skill(gate):
    original = gate[1].read_bytes()
    gate[4].update(baseline_score=0.01, validation_score=0.99,
                   replacement="Use evidence. Skip results.")
    decision, _, record = apply(gate)
    assert decision == "rejected"
    assert record["baseline_score"] == record["validation_score"] == 0.5
    assert record["reason_code"] == "skill_edit_not_improved"
    assert gate[1].read_bytes() == original


def test_missing_evaluator_does_not_trust_proposal_scores(gate):
    original = gate[1].read_bytes()
    gate[3].unlink()
    gate[4].update(baseline_score=0.01, validation_score=0.99)
    decision, _, record = apply(gate)
    assert decision == "rejected"
    assert record["scores_verified"] is False
    assert gate[1].read_bytes() == original


def test_original_drift_rejected_before_evaluator_runs(gate, monkeypatch):
    gate[1].write_text("External change\n")
    def unexpected(*args):
        pytest.fail("evaluator must not run after original drift")
    monkeypatch.setattr(skill_evaluation, "evaluate", unexpected)
    with pytest.raises(ValueError, match="skill_edit_source_changed"):
        apply(gate)
    assert gate[1].read_text() == "External change\n"


def test_original_drift_after_evaluation_rejected_before_replacement(gate, monkeypatch):
    evaluate = skill_evaluation.evaluate
    def concurrent_change(*args):
        result = evaluate(*args)
        gate[1].write_text("Concurrent change\n")
        return result
    monkeypatch.setattr(skill_evaluation, "evaluate", concurrent_change)
    with pytest.raises(ValueError, match="skill_edit_source_changed"):
        apply(gate)
    assert gate[1].read_text() == "Concurrent change\n"


@pytest.mark.parametrize("target", ["AGENTS.md", "../outside.md", "skills/../outside.md", "absolute"])
def test_protected_paths_are_not_written(gate, target):
    protected = gate[0] / "AGENTS.md"
    protected.write_text("Protected\n")
    gate[4]["skill_path"] = str(protected) if target == "absolute" else target
    with pytest.raises(ValueError, match="skill_edit_invalid_skill_path"):
        apply(gate)
    assert protected.read_text() == "Protected\n"


def test_changed_evaluator_is_rejected(gate):
    original = gate[1].read_bytes()
    gate[2].write_text("raise RuntimeError('not the approved program')\n")
    with pytest.raises(ValueError, match="skill_edit_evaluation_failed"):
        apply(gate)
    assert gate[1].read_bytes() == original


def test_missing_original_hash_never_invokes_evaluator(gate, monkeypatch):
    del gate[4]["old_hash"]
    def unexpected(*args):
        pytest.fail("evaluator must not run without the original hash")
    monkeypatch.setattr(skill_evaluation, "evaluate", unexpected)
    decision, _, _ = apply(gate)
    assert decision == "rejected"
