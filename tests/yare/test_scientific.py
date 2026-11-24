"""Offline contract tests; requests are scripted and no scientific approval is inferred."""

import copy
import json
import math

import pytest

from cli import integrity, storage, yare
from cli.scientific import ScientificEvidenceError, verify_continuity, verify_scientific_evidence
from producers import scientific

EXAMPLE = scientific.EXAMPLE


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    output = tmp_path_factory.mktemp("public-science") / "bundle.json"
    return scientific.prepare_bundle(EXAMPLE / "data/manifest.json", output)


@pytest.fixture
def initial(bundle):
    return scientific.build_science(bundle, "A", "offline-contract-test",
                                    scientific.read_json(EXAMPLE / "requests/a.json"))


def record(initial, run_id="fixture-a"):
    execution = {"command": ["python", "analysis.py"], "exit_code": 0, "stdout": "fixture calculation", "stderr": ""}
    raw = scientific.make_artifact(initial, run_id, execution)
    normalized = yare._lead_normalize_artifact(raw, "artifact:1", 1)
    packet = {"hash_version": "work-state.v2", "task": raw["task"], "current_state": {}, "artifacts": [normalized],
              "proof": {"run_id": run_id}}
    state_hash = integrity.state_hash(packet)
    packet["deterministic_hash"] = state_hash
    receipt = {"run_id": run_id, "current_state_hash": state_hash,
               "packet_hash": integrity.digest(packet), "packet_snapshot": packet}
    receipt_hash = integrity.digest(receipt)
    receipt["receipt_hash"] = receipt_hash
    return [run_id, state_hash, packet["current_state"], packet, receipt_hash, receipt]


@pytest.mark.parametrize("part,code", [
    ("dataset", "dataset_hash"), ("source", "analysis_hash"), ("rows", "selected_row"),
    ("value", "observation_value"), ("uncertainty", "observation_value"),
    ("result", "results_hash"), ("reference", "evidence_reference"),
    ("nan", "contract_invalid"), ("negative_error", "contract_invalid"),
    ("duplicate", "duplicate_id"), ("review", "review_stage_invalid"),
    ("scientific_certification", "contract_invalid"),
])
def test_scientific_contract_rejects_corruption(initial, part, code):
    changed = copy.deepcopy(initial)
    if part == "dataset":
        changed["datasets"][0]["content_utf8"] += " "
    elif part == "source":
        changed["analysis"]["source_code"] += "\n# changed"
    elif part == "rows":
        changed["datasets"][0]["selected_rows"][0]["sha256"] = "0" * 64
    elif part in ("value", "uncertainty"):
        changed["observations"][0][part] += 1
    elif part == "result":
        changed["analysis"]["results"]["weighted_mean_mag"] += 1
    elif part == "reference":
        changed["hypotheses"][0]["evidence_refs"] = ["missing"]
    elif part == "nan":
        changed["observations"][0]["value"] = math.nan
    elif part == "negative_error":
        changed["observations"][0]["uncertainty"] = -1
    elif part == "duplicate":
        changed["observations"].append(copy.deepcopy(changed["observations"][0]))
    elif part == "review":
        # A valid-shaped synthetic defer record must still be rejected outside D.
        changed["human_review"] = {"source": "operator_supplied", "reviewer": "synthetic-test-only",
                                   "recorded_at": "2026-11-24T00:00:00Z", "decision": "defer",
                                   "note": "Synthetic contract test, not human authorization",
                                   "parent_receipt_hash": "0" * 64, "record_sha256": "0" * 64}
    else:
        changed["hypotheses"][0]["status"] = "verified"
    with pytest.raises(ScientificEvidenceError, match=code):
        verify_scientific_evidence(changed)


def test_science_is_optional_and_compilation_preserves_all_fields(initial):
    assert "scientific" not in yare._lead_normalize_artifact({"evidence": {"other": 1}}, "old", 1)["evidence"]
    raw = scientific.make_artifact(initial, "fixture-a", {"command": ["python"], "exit_code": 0, "stdout": "ok"})
    assert yare._lead_normalize_artifact(raw, "science", 1)["evidence"]["scientific"] == initial
    raw["evidence"]["scientific"]["analysis"]["sha256"] = "0" * 64
    with pytest.raises(ScientificEvidenceError):
        yare._lead_normalize_artifact(raw, "science", 1)


def test_loader_checks_scientific_hashes_even_after_outer_rehash(initial):
    row = record(initial)
    assert storage.verify_handoff_record(row)["artifacts"][0]["evidence"]["scientific"] == initial
    changed = copy.deepcopy(initial)
    changed["datasets"][0]["sha256"] = "0" * 64
    # Bypass compiler validation only to simulate an internally rehashed invalid stored record.
    row[3]["artifacts"][0]["evidence"]["scientific"] = changed
    row[1] = integrity.state_hash(row[3])
    row[3]["deterministic_hash"] = row[1]
    row[5]["current_state_hash"] = row[1]
    row[5]["packet_hash"] = integrity.digest(row[3])
    row[4] = integrity.digest({key: value for key, value in row[5].items() if key != "receipt_hash"})
    row[5]["receipt_hash"] = row[4]
    with pytest.raises(storage.StorageError, match="science_dataset_hash_mismatch"):
        storage.verify_handoff_record(row)


@pytest.mark.parametrize("part", ["parent", "observation", "question", "disagreement", "stage"])
def test_parent_boundary_retains_evidence_and_open_questions(initial, bundle, part):
    parent_a = storage.verify_handoff_record(record(initial))
    b = scientific.build_science(bundle, "B", initial["investigation_id"],
                                scientific.read_json(EXAMPLE / "requests/b.json"), parent_a)
    parent_b = storage.verify_handoff_record(record(b, "fixture-b"))
    child = scientific.build_science(bundle, "C", initial["investigation_id"], {}, parent_b)
    if part == "parent":
        child["parent"]["receipt_hash"] = "0" * 64
    elif part == "observation":
        child["observations"].pop()
    elif part == "question":
        child["questions"].pop()
    elif part == "disagreement":
        child["disagreements"] = []
    else:
        child["stage"] = "B"
    with pytest.raises(ScientificEvidenceError):
        verify_continuity(child, parent_b)


def test_d_stops_before_any_output_without_human_review(initial, bundle, tmp_path):
    a = storage.verify_handoff_record(record(initial))
    b = scientific.build_science(bundle, "B", initial["investigation_id"], scientific.read_json(EXAMPLE / "requests/b.json"), a)
    c = scientific.build_science(bundle, "C", initial["investigation_id"], {}, storage.verify_handoff_record(record(b, "fixture-b")))
    with pytest.raises(ScientificEvidenceError, match="human_review_required"):
        scientific.build_science(bundle, "D", initial["investigation_id"], {}, storage.verify_handoff_record(record(c, "fixture-c")))


def test_reproduction_rejects_wrong_calculation_and_excessive_tolerance(initial, tmp_path):
    scientific.reproduce(initial, tmp_path)
    changed = copy.deepcopy(initial)
    changed["analysis"]["results"]["weighted_mean_mag"] += 1
    with pytest.raises(ScientificEvidenceError, match="reproduction_mismatch"):
        scientific.reproduce(changed, tmp_path)
    changed["analysis"]["parameters"]["reproduction_absolute_tolerance"] = 100
    with pytest.raises(ScientificEvidenceError, match="tolerance_invalid"):
        scientific.reproduce(changed, tmp_path)


class DriverFixture:
    """In-memory DB-API substitute; this is not a CockroachDB server."""
    def __init__(self):
        self.states, self.receipts, self.vectors = {}, {}, []
        self.artifacts, self.events, self.selected, self.commits = [], [], None, 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def cursor(self):
        return self

    def commit(self):
        self.commits += 1

    def execute(self, sql, args=()):
        if "INSERT INTO yare_current_states" in sql:
            state_hash, run_id, state, packet = args
            self.states[state_hash] = [run_id, state_hash, json.loads(state), json.loads(packet)]
        elif "INSERT INTO yare_lead_artifacts" in sql:
            self.artifacts.append(json.loads(args[3]))
        elif "INSERT INTO yare_receipts" in sql:
            self.receipts[args[0]] = json.loads(args[3])
        elif "INSERT INTO yare_memory_vectors" in sql:
            self.vectors.append((args[2], 0.5, args[1], args[3]))
        elif "INSERT INTO yare_events" in sql:
            self.events.append(args)
        elif "FROM yare_current_states cs JOIN yare_runs" in sql:
            rows = [row for row in self.states.values() if row[0] == args[0]]
            assert len(rows) == 1
            row = rows[0]
            receipt_hash, receipt = next((key, value) for key, value in self.receipts.items() if value["run_id"] == row[0])
            self.selected = [*row, receipt_hash, receipt]
        else:
            assert ("INSERT INTO yare_runs" in sql or "INSERT INTO yare_run_snapshots" in sql
                    or "FROM yare_memory_vectors" in sql), sql

    def fetchone(self):
        return self.selected

    def fetchall(self):
        return self.vectors


def test_existing_persistence_and_loader_roundtrip_all_science_fields(initial):
    row = record(initial)
    driver = DriverFixture()
    storage.persist_lead_compile(packet=row[3], artifacts=row[3]["artifacts"], receipt=row[5],
                                database_url="fixture-only", connect_func=lambda _: driver)
    stored = storage.load_handoff(run_id=row[0], database_url="fixture-only", connect_func=lambda _: driver)
    assert stored["artifacts"][0]["evidence"]["scientific"] == initial
    assert driver.artifacts[0]["evidence"]["scientific"] == initial
    assert len(driver.events) == driver.commits == 1


def test_local_export_preserves_fields_and_cannot_use_configured_db(bundle, tmp_path, monkeypatch):
    monkeypatch.setenv("YARE_DATABASE_URL", "must-not-connect")
    monkeypatch.setenv("YARE_S3_BUCKET", "must-not-upload")
    monkeypatch.setattr(storage, "_connect", lambda _: pytest.fail("Offline producer attempted DB access"))
    output = tmp_path / "a"
    scientific.record_stage(bundle, "A", "offline-export", "export-a",
                              scientific.read_json(EXAMPLE / "requests/a.json"), output)
    loaded = scientific.verified_export(output / "handoff.json")
    assert scientific.scientific_payload(loaded)["datasets"] == bundle["datasets"]
    assert loaded["receipt"]["validation_ok"] is True
    with pytest.raises(ValueError, match="exists"):
        scientific.record_stage(bundle, "A", "offline-export", "export-a", {}, output)


def test_data_manifest_freezes_actual_public_bytes(bundle):
    assert {item["id"] for item in bundle["datasets"]} == {"ztf", "gaia"}
    assert len(bundle["observations"]) == 100
    assert bundle["analysis"]["results"]["n"] == 100
    assert all(item["time_scale"] == "unverified" for item in bundle["observations"])
    assert len(scientific.dataset_rows(bundle["datasets"][1])) == 3


def test_six_predefined_questions_route_real_export_sections_offline(bundle, tmp_path):
    scientific.record_stage(bundle, "A", "offline-ranking", "rank-a",
                              scientific.read_json(EXAMPLE / "requests/a.json"), tmp_path / "a")
    scientific.record_stage(None, "B", "offline-ranking", "rank-b",
                              scientific.read_json(EXAMPLE / "requests/b.json"), tmp_path / "b", tmp_path / "a/handoff.json")
    export = scientific.read_json(tmp_path / "b/handoff.json")
    driver = DriverFixture()
    storage.persist_lead_compile(packet=export["packet"], artifacts=export["packet"]["artifacts"],
                                receipt=export["receipt"], database_url="fixture-only", connect_func=lambda _: driver)
    questions = [("what needs human review?", "human approval items"),
                 ("which files changed?", "what changed"), ("what remains unfinished?", "open loops"),
                 ("what is unverified?", "what is unverified"), ("what contradictions exist?", "contradictions"),
                 ("what is the next clean action?", "next clean action")]
    for query, section in questions:
        results = storage.search_memory(query, 1, database_url="fixture-only", task=export["packet"]["task"],
                                        connect_func=lambda _: driver)
        assert results and results[0]["section_name"] == section


def test_review_is_bound_to_c_and_missing_or_altered_review_cannot_run_d(bundle, tmp_path):
    for stage in "ABC":
        parent = tmp_path / chr(ord(stage.lower()) - 1) / "handoff.json" if stage != "A" else None
        scientific.record_stage(bundle if stage == "A" else None, stage, "review-gate", "review-" + stage.lower(),
                                  scientific.read_json(EXAMPLE / "requests" / (stage.lower() + ".json")),
                                  tmp_path / stage.lower(), parent)
    with pytest.raises(ScientificEvidenceError, match="human_review_required"):
        scientific.record_stage(None, "D", "review-gate", "review-d", {}, tmp_path / "d", tmp_path / "c/handoff.json")
    assert not (tmp_path / "d").exists()
    # This synthetic defer record tests structure only; it is not used in the research evaluation.
    review = scientific.record_review(tmp_path / "c/handoff.json", "synthetic-unit-test-only", "defer",
                                      "Synthetic contract check; not an operator decision", tmp_path / "synthetic-review.json")
    changed = copy.deepcopy(review)
    changed["parent_receipt_hash"] = "0" * 64
    with pytest.raises(ScientificEvidenceError, match="human_review_mismatch"):
        scientific.record_stage(None, "D", "review-gate", "review-d", {}, tmp_path / "d",
                                  tmp_path / "c/handoff.json", changed)
    assert not (tmp_path / "d").exists()
    scientific.record_stage(None, "D", "review-gate", "review-d", {}, tmp_path / "d",
                              tmp_path / "c/handoff.json", review)
    d = scientific.verified_export(tmp_path / "d/handoff.json")
    assert d["artifacts"][0]["evidence"]["followup_recommendations"] == []
    assert len(scientific.scientific_payload(d)["questions"]) == 3


def test_explicit_cockroach_adapter_with_fake_driver_only(bundle, tmp_path, monkeypatch):
    driver = DriverFixture()
    monkeypatch.setenv("YARE_DATABASE_URL", "fixture-only-not-a-real-database")
    monkeypatch.setenv("YARE_S3_BUCKET", "must-not-upload")
    monkeypatch.setattr(storage, "_connect", lambda _: driver)
    for stage in "ABC":
        result = scientific.record_stage(bundle if stage == "A" else None, stage, "fake-driver-chain", "db-" + stage.lower(),
                                         scientific.read_json(EXAMPLE / "requests" / (stage.lower() + ".json")),
                                         tmp_path / stage.lower(), storage_mode="cockroach",
                                         parent_run_id="db-" + chr(ord(stage.lower()) - 1) if stage != "A" else None)
        assert result["storage"] == "cockroach"  # Adapter mode; driver is explicitly synthetic.
        assert result["model_calls"] == 0
    review = scientific.record_review(None, "synthetic-test-only", "defer", "Synthetic review gate test",
                                      tmp_path / "review.json", parent_run_id="db-c")
    scientific.record_stage(None, "D", "fake-driver-chain", "db-d", {}, tmp_path / "d", review=review,
                            storage_mode="cockroach", parent_run_id="db-c")
    stored = storage.load_handoff(run_id="db-d")
    assert scientific.scientific_payload(stored)["observations"] == bundle["observations"]
    assert len(driver.states) == len(driver.events) == driver.commits == 4


def test_offline_mode_refuses_database_parent_and_missing_live_config(bundle, tmp_path, monkeypatch):
    monkeypatch.delenv("YARE_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="Offline mode"):
        scientific.record_stage(bundle, "A", "scope", "scope-a", {}, tmp_path / "a", parent_run_id="run")
    with pytest.raises(ValueError, match="Cockroach mode"):
        scientific.record_stage(bundle, "A", "scope", "scope-a", {}, tmp_path / "a", storage_mode="cockroach")
    assert not (tmp_path / "a").exists()


@pytest.mark.parametrize("part", ["rows", "unit", "band", "time_scale"])
def test_analysis_cannot_silently_switch_observations_or_units(initial, tmp_path, part):
    changed = copy.deepcopy(initial)
    if part == "rows":
        changed["analysis"]["parameters"]["ztf_rows"][-1] = 700
    else:
        changed["observations"][0][part] = "wrong"
    with pytest.raises(ScientificEvidenceError, match="analysis_selection_mismatch"):
        scientific.reproduce(changed, tmp_path)
