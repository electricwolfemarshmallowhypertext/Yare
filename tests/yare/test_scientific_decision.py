"""Offline human-decision tests; no models or live database are used."""

import copy
import hashlib
import json

import pytest

from cli import integrity, storage
from cli.scientific import ScientificEvidenceError, scientific_review_findings, verify_continuity
from producers import scientific
from scripts.record_scientific_decision import DECISION, record_decisions
from tests.yare.test_scientific import DriverFixture


@pytest.fixture
def environment(tmp_path, monkeypatch):
    driver = DriverFixture()
    monkeypatch.setenv("YARE_DATABASE_URL", "synthetic-db-only")
    monkeypatch.setattr(storage, "_connect", lambda _: driver)
    bundle = scientific.prepare_bundle(scientific.EXAMPLE / "data/manifest.json", tmp_path / "bundle.json")
    for repetition in range(1, 4):
        for stage in "ABC":
            prefix = f"public-science-local-20261124-{repetition}-"
            scientific.record_stage(bundle if stage == "A" else None, stage,
                f"public-science-local-20261124-{repetition}", prefix + stage.lower(),
                scientific.read_json(scientific.EXAMPLE / "requests" / (stage.lower() + ".json")),
                tmp_path / (str(repetition) + stage), storage_mode="cockroach",
                parent_run_id=prefix + chr(ord(stage.lower()) - 1) if stage != "A" else None)
    reference = scientific.read_json(scientific.EXAMPLE / "references/gaia-dr3-units/units.json")
    return driver, reference


def test_d_records_actual_decision_without_model_and_preserves_parents(environment, tmp_path, monkeypatch):
    driver, reference = environment
    # Any attempted model/provider access is a test failure, not an allowed fallback.
    from producers import scientific_local
    monkeypatch.setattr(scientific_local, "request_local", lambda *a, **k: pytest.fail("Human D attempted inference"))
    before = copy.deepcopy((driver.states, driver.receipts, driver.artifacts))
    results = record_decisions(tmp_path, tmp_path / "human", reference)
    assert len(results) == 3 and all(item["model_calls"] == 0 for item in results)
    for repetition in range(1, 4):
        prefix = f"public-science-local-20261124-{repetition}-"
        parent = storage.load_handoff(run_id=prefix + "c")
        child = storage.load_handoff(run_id=prefix + "d")
        old, new = scientific.scientific_payload(parent), scientific.scientific_payload(child)
        verify_continuity(new, parent)
        assert new["execution"] == "human_decision"
        assert new["human_review"]["note"] == DECISION
        for key in ("datasets", "observations", "analysis", "hypotheses", "disagreements", "questions"):
            assert new[key] == old[key]
        evidence = child["artifacts"][0]["evidence"]
        assert "local_model" not in evidence
        assert evidence["scientific_review"]["scientific_reasoning_acceptance"] == "FAILED"
        assert evidence["scientific_review"]["work_state_continuity"] == "PASSED"
        assert all(item["diagnostic_only"] for item in evidence["followup_recommendations"])
    for key, value in before[0].items():
        assert driver.states[key] == value
    for key, value in before[1].items():
        assert driver.receipts[key] == value
    assert driver.artifacts[:len(before[2])] == before[2]


def test_review_flags_duplicates_and_wrong_units_without_repair(environment, tmp_path):
    _, reference = environment
    parent = storage.load_handoff(run_id="public-science-local-20261124-1-c")
    science = copy.deepcopy(scientific.scientific_payload(parent))
    first = copy.deepcopy(science["hypotheses"][0])
    first["id"] = "synthetic-duplicate"
    science["hypotheses"].append(first)
    science["hypotheses"].append({"id": "synthetic-unit-error", "statement": "ra_error: 0.284" + chr(176),
                                  "status": "unverified", "evidence_refs": ["gaia"]})
    science["stage"], science["execution"] = "D", "human_decision"
    science["human_review"] = {"record_sha256": "a" * 64}
    original = copy.deepcopy(science)
    audit = scientific_review_findings(science, reference)
    assert any("synthetic-duplicate" in group for group in audit["duplicate_hypothesis_groups"])
    assert audit["unit_error_statement_ids"] == ["synthetic-unit-error"]
    assert science == original


@pytest.mark.parametrize("part", ["units", "excerpt", "digest", "missing"])
def test_unit_reference_is_checked(environment, part):
    _, reference = environment
    parent = storage.load_handoff(run_id="public-science-local-20261124-1-c")
    science = copy.deepcopy(scientific.scientific_payload(parent))
    science.update(stage="D", execution="human_decision", human_review={"record_sha256": "a" * 64})
    reference = copy.deepcopy(reference)
    if part == "units":
        reference["units"]["ra_error"] = "deg"
    elif part == "excerpt":
        reference["excerpt"] += "changed"
    elif part == "digest":
        reference["document_sha256"] = "invalid"
    else:
        reference = None
    with pytest.raises(ScientificEvidenceError, match="unit_reference_invalid"):
        scientific_review_findings(science, reference)


def test_no_human_mode_before_d_or_with_new_reasoning(environment, tmp_path):
    _, reference = environment
    parent = storage.load_handoff(run_id="public-science-local-20261124-1-c")
    bundle = {key: scientific.scientific_payload(parent)[key] for key in ("datasets", "analysis", "observations", "brief_sha256")}
    with pytest.raises(ScientificEvidenceError, match="human_decision_requires_review_only"):
        scientific.build_science(bundle, "D", "public-science-local-20261124-1", {"questions": [1]}, parent,
                                  {"note": DECISION}, execution_mode="human_decision")
    with pytest.raises(ScientificEvidenceError, match="human_decision_requires_review_only"):
        scientific.build_science(bundle, "C", "public-science-local-20261124-1", {}, parent,
                                  {"note": DECISION}, execution_mode="human_decision")


def test_loader_rejects_review_tamper_even_after_outer_rehash(environment, tmp_path):
    driver, reference = environment
    record_decisions(tmp_path, tmp_path / "human", reference)
    stored = storage.load_handoff(run_id="public-science-local-20261124-1-d")
    packet = copy.deepcopy(stored["receipt"]["packet_snapshot"])
    packet["artifacts"][0]["evidence"]["scientific_review"]["scientific_reasoning_acceptance"] = "PASSED"
    state_hash = integrity.state_hash(packet)
    packet["deterministic_hash"] = state_hash
    receipt = copy.deepcopy(stored["receipt"])
    receipt.update(packet_snapshot=packet, packet_hash=integrity.digest(packet), current_state_hash=state_hash)
    receipt["receipt_hash"] = integrity.digest({key: value for key, value in receipt.items() if key != "receipt_hash"})
    row = [stored["run_id"], state_hash, packet["current_state"], packet, receipt["receipt_hash"], receipt]
    with pytest.raises(storage.StorageError, match="review_findings_mismatch"):
        storage.verify_handoff_record(row)


def test_bundle_screen_parses_nested_json_newlines_without_modifying_bytes():
    from scripts.package_scientific_review import screen_member
    raw = json.dumps({"request": json.dumps({"content": "public result\nnext line"})}).encode()
    before = bytes(raw)
    screen_member("public-request.json", raw)
    assert raw == before


@pytest.mark.parametrize("path", ["C:/private/secret.py", "file:///private/secret.py", "/home/private/secret.py",
                                  "\\\\server\\private\\secret.py"])
def test_bundle_screen_rejects_real_paths_inside_nested_provider_json(path):
    from scripts.package_scientific_review import screen_member
    raw = json.dumps({"response": json.dumps({"content": path})}).encode()
    with pytest.raises(ValueError, match="Privacy screening"):
        screen_member("private-request.json", raw)
