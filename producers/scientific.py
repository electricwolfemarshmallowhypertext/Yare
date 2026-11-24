"""Explicitly scripted scientific fixtures using Yare's existing artifact path."""

import argparse
import copy
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from cli import integrity, storage
from cli.scientific import (ScientificEvidenceError, dataset_rows, text_hash,
                            verify_continuity, verify_scientific_evidence)
from cli.yare import compile_lead_state

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/scientific-handoff"
TASK = "Public astronomical work continuity, not source classification"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path):
    def reject_constant(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def prepare_bundle(manifest_path, output):
    if output.exists():
        raise ValueError("Bundle already exists; refusing to overwrite frozen evidence")
    manifest = read_json(manifest_path)
    if manifest.get("version") != "public-astronomy-data.v1":
        raise ValueError("Unsupported public data manifest")
    datasets = []
    for item in manifest["datasets"]:
        path = (manifest_path.parent / item["path"]).resolve()
        if not path.is_relative_to(manifest_path.parent.resolve()):
            raise ValueError("Dataset path outside manifest directory")
        raw = path.read_bytes()
        if len(raw) > 262144:
            raise ValueError("Dataset exceeds example byte bound")
        content = raw.decode("utf-8")
        if text_hash(content) != item["sha256"]:
            raise ValueError("Frozen dataset differs from manifest")
        dataset = {key: item[key] for key in ("id", "source_url", "query", "release", "acquired_at", "sha256", "media_type")}
        dataset["content_utf8"] = content
        if "row_selector" in item:
            dataset["row_selector"] = item["row_selector"]
        rows = dataset_rows(dataset)
        if item["rows"] != len(rows):
            raise ValueError("Manifest row count differs")
        indices = list(range(min(len(rows), 100)))
        dataset["selected_rows"] = [{"index": index, "sha256": integrity.digest(rows[index])} for index in indices]
        datasets.append(dataset)
    indexed = {item["id"]: item for item in datasets}
    if set(indexed) != {"ztf", "gaia"} or len(datasets) != 2:
        raise ValueError("Example requires exactly the public ZTF and Gaia datasets")
    rows = dataset_rows(indexed["ztf"])
    is_json = indexed["ztf"]["media_type"] == "application/json"
    band_column = None if is_json else ("filtercode" if "filtercode" in rows[0] else "fid")
    band = (json.loads(indexed["ztf"]["content_utf8"])[indexed["ztf"]["row_selector"][0]]["meta"]["filter"]
            if is_json else rows[0][band_column])
    selected = [entry["index"] for entry in indexed["ztf"]["selected_rows"]
                if band_column is None or rows[entry["index"]][band_column] == band]
    parameters = {"ztf_rows": selected, "band": band, "time_scale": "unverified",
                  "ztf_media_type": indexed["ztf"]["media_type"],
                  "ztf_row_selector": indexed["ztf"].get("row_selector"),
                  "columns": {"time": "mjd", "value": "mag", "uncertainty": "magerr", "band": band_column},
                  "reproduction_relative_tolerance": 1e-12, "reproduction_absolute_tolerance": 1e-12}
    analysis_input = output.parent / "analysis-input.json"
    write_json(analysis_input, {"datasets": {item["id"]: item["content_utf8"] for item in datasets},
                                "parameters": parameters})
    source = (EXAMPLE / "analysis.py").read_bytes().decode("utf-8")
    run = subprocess.run([sys.executable, str(EXAMPLE / "analysis.py"), "--input", str(analysis_input)],
                         capture_output=True, text=True, timeout=30)
    if run.returncode != 0:
        raise ValueError("Public data analysis failed: " + run.stderr[-1000:])
    results = json.loads(run.stdout)
    observations = [{"id": "ztf-observation-" + str(index), "dataset_id": "ztf", "row_index": index,
                     "value_column": "mag", "uncertainty_column": "magerr", "value": float(rows[index]["mag"]),
                     "uncertainty": float(rows[index]["magerr"]), "unit": "mag", "time_column": "mjd",
                     "time_value": float(rows[index]["mjd"]), "time_format": "MJD", "time_scale": "unverified",
                     "band": band} for index in selected]
    bundle = {"version": "scientific-bundle.v1", "datasets": datasets, "observations": observations,
              "brief_sha256": text_hash((EXAMPLE / "brief.md").read_bytes().decode("utf-8")),
              "analysis": {"source_code": source, "sha256": text_hash(source), "parameters": parameters,
                           "results": results, "results_sha256": integrity.digest(results),
                           "environment": {"python": platform.python_version(), "dependencies": "Python standard library"}},
              "analysis_execution": {"kind": "scripted_fixture", "command": ["python", "analysis.py", "--input", "analysis-input.json"],
                                     "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr}}
    write_json(output, bundle)
    return bundle


def verified_export(path):
    export = read_json(path)
    if export.get("mode") != "offline_export":
        raise ValueError("Expected an explicitly labeled offline export")
    packet, receipt = export["packet"], export["receipt"]
    return storage.verify_handoff_record([receipt["run_id"], packet["deterministic_hash"], packet["current_state"],
                                          packet, receipt["receipt_hash"], receipt])


def scientific_payload(stored):
    candidates = [artifact["evidence"]["scientific"] for artifact in stored["artifacts"]
                  if isinstance(artifact.get("evidence"), dict) and "scientific" in artifact["evidence"]]
    if len(candidates) != 1:
        raise ScientificEvidenceError("science_parent_artifact_ambiguous")
    return candidates[0]


def build_science(bundle, stage, investigation_id, reasoning, parent=None, review=None, execution_mode="scripted_fixture"):
    if execution_mode == "human_decision" and (stage != "D" or not review or any(reasoning.values())):
        raise ScientificEvidenceError("science_human_decision_requires_review_only")
    if stage == "A":
        science = {"version": "scientific-evidence.v1", "investigation_id": investigation_id,
                   "stage": stage, "execution": execution_mode, "brief_sha256": bundle["brief_sha256"],
                   "datasets": copy.deepcopy(bundle["datasets"]), "analysis": copy.deepcopy(bundle["analysis"]),
                   "observations": copy.deepcopy(bundle["observations"]), "hypotheses": [], "disagreements": [],
                   "questions": [], "parent": None, "human_review": None}
        if parent is not None:
            raise ScientificEvidenceError("science_initial_parent_forbidden")
    else:
        if parent is None:
            raise ScientificEvidenceError("science_parent_required")
        science = copy.deepcopy(scientific_payload(parent))
        if (science["investigation_id"] != investigation_id or science["datasets"] != bundle["datasets"] or
                science["analysis"] != bundle["analysis"] or science["brief_sha256"] != bundle["brief_sha256"]):
            raise ScientificEvidenceError("science_bundle_changed")
        science.update(stage=stage, parent={key: parent[key] for key in ("run_id", "current_state_hash", "receipt_hash")})
        if execution_mode == "human_decision":
            science["execution"] = execution_mode
    if not isinstance(reasoning, dict) or set(reasoning) - {"hypotheses", "disagreements", "questions"}:
        raise ScientificEvidenceError("science_scripted_request_invalid")
    for key in ("hypotheses", "disagreements", "questions"):
        science[key].extend(copy.deepcopy(reasoning.get(key, [])))
    if stage == "B":
        if not science["disagreements"]:
            raise ScientificEvidenceError("science_disagreement_required")
    if science["disagreements"]:
        disputed = {identifier for item in science["disagreements"] for identifier in item["hypothesis_ids"]}
        for hypothesis in science["hypotheses"]:
            if hypothesis["id"] in disputed:
                hypothesis["status"] = "disputed"
    if stage == "D":
        if review is None:
            raise ScientificEvidenceError("science_human_review_required")
        science["human_review"] = copy.deepcopy(review)
    verify_scientific_evidence(science)
    if parent:
        verify_continuity(science, parent)
    return science


def reproduce(science, directory):
    """Run only the pinned repository program, never source embedded in a record."""
    import math
    source = (EXAMPLE / "analysis.py").read_bytes().decode("utf-8")
    if text_hash(source) != science["analysis"]["sha256"]:
        raise ScientificEvidenceError("science_local_analysis_changed")
    parameters = science["analysis"]["parameters"]
    for name in ("reproduction_relative_tolerance", "reproduction_absolute_tolerance"):
        tolerance = parameters[name]
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not 0 <= tolerance <= 1e-9:
            raise ScientificEvidenceError("science_reproduction_tolerance_invalid")
    observations = science["observations"]
    indices = parameters["ztf_rows"]
    if (any(type(index) is not int or index < 0 for index in indices) or len(set(indices)) != len(indices) or
            sorted(indices) != sorted(item["row_index"] for item in observations) or
            any(item["dataset_id"] != "ztf" or item["band"] != parameters["band"] or item["unit"] != "mag" or
                item["time_format"] != "MJD" or item["time_scale"] != parameters["time_scale"] or
                item["value_column"] != parameters["columns"]["value"] or
                item["uncertainty_column"] != parameters["columns"]["uncertainty"] or
                item["time_column"] != parameters["columns"]["time"] for item in observations)):
        raise ScientificEvidenceError("science_analysis_selection_mismatch")
    path = directory / "reproduction-input.json"
    write_json(path, {"datasets": {item["id"]: item["content_utf8"] for item in science["datasets"]},
                      "parameters": science["analysis"]["parameters"]})
    run = subprocess.run([sys.executable, str(EXAMPLE / "analysis.py"), "--input", str(path)],
                         capture_output=True, text=True, timeout=30)
    if run.returncode:
        raise ScientificEvidenceError("science_reproduction_failed")
    actual, expected = json.loads(run.stdout), science["analysis"]["results"]
    if actual.keys() != expected.keys():
        raise ScientificEvidenceError("science_reproduction_mismatch")
    for key, value in expected.items():
        matches = (math.isclose(actual[key], value, rel_tol=parameters["reproduction_relative_tolerance"],
                                abs_tol=parameters["reproduction_absolute_tolerance"])
                   if isinstance(value, (int, float)) else actual[key] == value)
        if not matches:
            raise ScientificEvidenceError("science_reproduction_mismatch")
    return {"command": ["python", "analysis.py", "--input", "reproduction-input.json"],
            "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr}


def make_artifact(science, run_id, execution):
    claim = "Pinned descriptive analysis reproduced from frozen public data; interpretation remains unverified"
    evidence = {"scientific": science, "calculation": {**execution, "kind": "test", "claim": claim, "expected_exit_code": 0}}
    recommendations = []
    if science["human_review"]:
        recommendations.append("Operator decision (not authenticated by Yare): " + science["human_review"]["decision"] +
                               "; " + science["human_review"]["note"])
        evidence["followup_recommendations"] = [
            {"question_id": item["id"], "diagnostic_only": True, "action": item["text"],
             "review_sha256": science["human_review"]["record_sha256"]} for item in science["questions"]
        ] if science["human_review"]["decision"] == "request_followup" else []
    return {"schema_version": "lead-artifact.v1", "run_id": run_id, "tool": "scientific-scripted-fixture",
            "task": TASK + ": " + science["investigation_id"], "timestamp": datetime.now(timezone.utc).isoformat(),
            "claims": [{"claim": claim, "verification_status": "verified", "evidence_ref": "calculation"},
                       *[{"claim": item["statement"], "verification_status": "unverified"} for item in science["hypotheses"]]],
            "decisions": recommendations, "files_touched": ["scientific-state.json"],
            "open_loops": [item["text"] for item in science["questions"]],
            "contradictions": [item["reason"] for item in science["disagreements"]],
            "human_approval_items": ["Review interpretations before any follow-up; no observing action is authorized"]
                                     if science["human_review"] is None else [],
            "verification_status": "partial", "evidence": evidence}


def record_stage(bundle, stage, investigation_id, run_id, reasoning, output, parent_path=None, review=None,
                 storage_mode="offline", parent_run_id=None, model_trace=None, deterministic_review=False,
                 unit_reference=None):
    output = output.resolve()
    if storage_mode not in ("offline", "cockroach"):
        raise ValueError("Unknown scientific storage mode")
    if storage_mode == "offline" and parent_run_id:
        raise ValueError("Offline mode cannot load a database parent")
    if storage_mode == "cockroach" and (parent_path or not os.environ.get("YARE_DATABASE_URL")):
        raise ValueError("Cockroach mode needs YARE_DATABASE_URL and --parent-run-id, not a local parent")
    if output.exists():
        raise ValueError("Stage output exists; refusing to overwrite evidence")
    parent = (storage.load_handoff(run_id=parent_run_id) if parent_run_id else
              verified_export(parent_path) if parent_path else None)
    if bundle is None:
        if parent is None:
            raise ScientificEvidenceError("science_initial_bundle_required")
        previous = scientific_payload(parent)
        bundle = {key: previous[key] for key in ("brief_sha256", "datasets", "observations", "analysis")}
    if bundle["brief_sha256"] != text_hash((EXAMPLE / "brief.md").read_bytes().decode("utf-8")):
        raise ScientificEvidenceError("science_fixed_brief_changed")
    if deterministic_review and (model_trace is not None or unit_reference is None):
        raise ScientificEvidenceError("science_human_decision_origin_invalid")
    mode = "human_decision" if deterministic_review else "live_model" if model_trace is not None else "scripted_fixture"
    science = build_science(bundle, stage, investigation_id, reasoning, parent, review, mode)
    if science["execution"] != mode:
        raise ScientificEvidenceError("science_execution_origin_changed")
    if model_trace is not None:
        from producers.scientific_local import verify_model_trace
        verify_model_trace(model_trace, reasoning, science)
    review_findings = None
    if deterministic_review:
        from cli.scientific import scientific_review_findings
        review_findings = scientific_review_findings(science, unit_reference)
    output.mkdir(parents=True)
    execution = reproduce(science, output)
    artifact = make_artifact(science, run_id, execution)
    if deterministic_review:
        artifact["tool"] = "scientific-human-decision"
        artifact["evidence"]["scientific_review"] = review_findings
    if model_trace is not None:
        artifact["tool"] = "scientific-local-model"
        artifact["evidence"]["local_model"] = copy.deepcopy(model_trace)
    write_json(output / "scientific-state.json", science)
    artifact_path = output / "lead-artifact.json"
    write_json(artifact_path, artifact)
    project = output / "workspace"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Isolated scientific evidence compilation\n", encoding="utf-8")
    (project / "yare.yaml").write_text("version: 1\n", encoding="utf-8")
    for name in ("skills", "memory", "policies", "evals", "receipts"):
        (project / name).mkdir()
    skill = project / "skills/scientific-fixture"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nid: scientific-fixture\nname: Scientific fixture\ndescription: Preserve recorded evidence\n"
        "version: 1\npermissions: []\n---\nKeep observations separate from interpretations.\n", encoding="utf-8")
    # Offline mode cannot accidentally use a configured live database or archive.
    names = ("YARE_DATABASE_URL", "YARE_S3_BUCKET") if storage_mode == "offline" else ("YARE_S3_BUCKET",)
    previous = {name: os.environ.pop(name, None) for name in names}
    started = time.perf_counter()
    try:
        packet, _, _, _, receipt, _ = compile_lead_state(project, artifact["task"], [artifact_path], validate_artifacts=True)
    finally:
        for name, value in previous.items():
            if value is not None:
                os.environ[name] = value
    compile_ms = (time.perf_counter() - started) * 1000
    export_path = output / "handoff.json"
    write_json(export_path, {"mode": "offline_export" if storage_mode == "offline" else "cockroach_record",
                             "packet": packet, "receipt": receipt})
    started = time.perf_counter()
    stored = verified_export(export_path) if storage_mode == "offline" else storage.load_handoff(run_id=run_id)
    reload_ms = (time.perf_counter() - started) * 1000
    expected = {"run_id": run_id, "current_state_hash": packet["deterministic_hash"], "receipt_hash": receipt["receipt_hash"]}
    if any(stored[key] != value for key, value in expected.items()):
        raise ScientificEvidenceError("science_readback_identity_mismatch")
    if scientific_payload(stored) != science:
        raise ScientificEvidenceError("science_roundtrip_mismatch")
    if parent:
        verify_continuity(scientific_payload(stored), parent)
    result = {"mode": mode, "storage": "local_export_not_cockroach" if storage_mode == "offline" else "cockroach",
              "stage": stage,
              "run_id": run_id, "state_hash": packet["deterministic_hash"], "receipt_hash": receipt["receipt_hash"],
              "compile_ms": compile_ms, "local_reload_ms" if storage_mode == "offline" else "cockroach_reload_ms": reload_ms,
              "export_bytes": export_path.stat().st_size,
              "parent": science["parent"], "model_calls": len(model_trace["calls"]) if model_trace else 0}
    write_json(output / "result.json", result)
    return result


def record_review(parent_path, reviewer, decision, note, output, parent_run_id=None):
    if output.exists():
        raise ValueError("Review exists; refusing to overwrite a recorded decision")
    if bool(parent_path) == bool(parent_run_id):
        raise ValueError("Choose exactly one review parent source")
    parent = storage.load_handoff(run_id=parent_run_id) if parent_run_id else verified_export(parent_path)
    if scientific_payload(parent)["stage"] != "C":
        raise ScientificEvidenceError("science_review_requires_stage_c")
    if not reviewer.strip() or not note.strip() or decision not in ("defer", "request_followup"):
        raise ScientificEvidenceError("science_human_review_invalid")
    review = {"source": "operator_supplied", "reviewer": reviewer.strip(),
              "recorded_at": datetime.now(timezone.utc).isoformat(), "decision": decision,
              "note": note.strip(), "parent_receipt_hash": parent["receipt_hash"]}
    review["record_sha256"] = integrity.digest(review)
    write_json(output, review)
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    stage = commands.add_parser("stage", help="Scripted fixture only; Cockroach writes require explicit --storage cockroach")
    stage.add_argument("--bundle", type=Path, help="Required only for A; replacements can restore frozen data from the parent")
    stage.add_argument("--stage", choices=list("ABCD"), required=True)
    stage.add_argument("--investigation-id", required=True)
    stage.add_argument("--run-id", required=True)
    stage.add_argument("--reasoning", type=Path, required=True, help="Explicitly scripted request JSON")
    stage.add_argument("--parent", type=Path)
    stage.add_argument("--parent-run-id", help="Database parent, only with --storage cockroach")
    stage.add_argument("--storage", choices=["offline", "cockroach"], default="offline")
    stage.add_argument("--human-review", type=Path)
    stage.add_argument("--output", type=Path, required=True)
    review = commands.add_parser("review", help="Record an actual operator decision; does not authenticate identity")
    review_parent = review.add_mutually_exclusive_group(required=True)
    review_parent.add_argument("--parent", type=Path)
    review_parent.add_argument("--parent-run-id")
    review.add_argument("--reviewer", required=True)
    review.add_argument("--decision", choices=["defer", "request_followup"], required=True)
    review.add_argument("--note", required=True)
    review.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        bundle = prepare_bundle(args.manifest, args.output)
        print(json.dumps({"mode": "scripted_analysis", "datasets": len(bundle["datasets"]),
                          "observations": len(bundle["observations"])}))
    elif args.command == "review":
        print(json.dumps(record_review(args.parent, args.reviewer, args.decision, args.note, args.output, args.parent_run_id)))
    else:
        print(json.dumps(record_stage(read_json(args.bundle) if args.bundle else None, args.stage, args.investigation_id, args.run_id,
                                        read_json(args.reasoning), args.output, args.parent,
                                        read_json(args.human_review) if args.human_review else None,
                                        args.storage, args.parent_run_id)))


if __name__ == "__main__":
    main()
