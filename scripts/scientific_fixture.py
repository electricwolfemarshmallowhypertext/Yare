"""Three offline scripted A/B/C repetitions; D requires a real operator record."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from cli.scientific import ScientificEvidenceError, verify_continuity
from producers import scientific


def evaluate(output):
    if output.exists():
        raise ValueError("Evaluation directory exists; use a fresh directory")
    output.mkdir(parents=True)
    bundle_path = output / "bundle.json"
    bundle = scientific.prepare_bundle(scientific.EXAMPLE / "data/manifest.json", bundle_path)
    report = {"mode": "scripted_fixture", "model_calls": 0, "cockroach_verified": False,
              "live_agent_reasoning_verified": False, "repetitions": [],
              "measurements": bundle["analysis"]["results"],
              "persistence_latency_ms": None, "live_retrieval_accuracy": None,
              "limitations": ["No live agents or CockroachDB in this offline evaluation",
                              "Fixture interpretations are scripted, not model-generated reasoning",
                              "No scientific correctness, discovery or throughput claim"]}
    environment = dict(os.environ)
    for name in ("YARE_DATABASE_URL", "YARE_S3_BUCKET", "NEBIUS_API_KEY", "OPENAI_API_KEY"):
        environment.pop(name, None)
    for repetition in range(1, 4):
        investigation = "public-science-offline-" + str(repetition)
        result = {"repetition": repetition, "stages": [], "verified_parent_links": 0}
        parent_path = None
        for stage in "ABC":
            directory = output / str(repetition) / stage.lower()
            command = [sys.executable, "-m", "producers.scientific", "stage", "--stage", stage,
                       "--investigation-id", investigation, "--run-id", investigation + "-" + stage.lower(),
                       "--reasoning", str(scientific.EXAMPLE / "requests" / (stage.lower() + ".json")),
                       "--output", str(directory)]
            if parent_path:
                command += ["--parent", str(parent_path)]
            else:
                command += ["--bundle", str(bundle_path)]
            completed = subprocess.run(command, cwd=scientific.ROOT, env=environment,
                                       capture_output=True, text=True, timeout=60)
            if completed.returncode:
                scientific.write_json(output / "failure.json", {"stage": stage, "repetition": repetition,
                                       "exit_code": completed.returncode, "stderr": completed.stderr[-2000:]})
                raise ValueError("Offline stage failed; retained failure.json")
            stored = scientific.verified_export(directory / "handoff.json")
            science = scientific.scientific_payload(stored)
            if parent_path:
                verify_continuity(science, scientific.verified_export(parent_path))
                result["verified_parent_links"] += 1
            if science["observations"] != bundle["observations"]:
                raise ValueError("Observation loss")
            if stage in "BC" and (len(science["hypotheses"]) != 2 or len(science["disagreements"]) != 1 or
                                  len(science["questions"]) != 3):
                raise ValueError("Disagreement or question loss")
            result["stages"].append(scientific.read_json(directory / "result.json"))
            parent_path = directory / "handoff.json"
        try:
            scientific.record_stage(None, "D", investigation, investigation + "-d", {},
                                      output / str(repetition) / "d", parent_path)
        except ScientificEvidenceError as exc:
            if str(exc) != "science_human_review_required":
                raise
            result["D"] = "PENDING actual operator review; no D receipt created"
        else:
            raise ValueError("D ran without human review")
        report["repetitions"].append(result)
        scientific.write_json(output / "result.json", report)
    print(json.dumps({"mode": report["mode"], "ABC_repetitions_passed": 3,
                      "verified_parent_links": 6, "D": "pending_human_review", "model_calls": 0}))
    return report


def finish_reviews(output, reviewer, decision, note):
    report = scientific.read_json(output / "result.json")
    if report["mode"] != "scripted_fixture" or len(report["repetitions"]) != 3:
        raise ValueError("Expected the three existing offline repetitions")
    if any(len(item["stages"]) != 3 for item in report["repetitions"]):
        raise ValueError("D has already been recorded or the fixture is incomplete")
    scientific.write_json(output / "result-before-review.json", report)
    for item in report["repetitions"]:
        directory = output / str(item["repetition"])
        parent_path = directory / "c/handoff.json"
        review = scientific.record_review(parent_path, reviewer, decision, note, directory / "human-review.json")
        investigation = "public-science-offline-" + str(item["repetition"])
        command = [sys.executable, "-m", "producers.scientific", "stage", "--stage", "D",
                   "--investigation-id", investigation, "--run-id", investigation + "-d",
                   "--reasoning", str(scientific.EXAMPLE / "requests/d.json"), "--parent", str(parent_path),
                   "--human-review", str(directory / "human-review.json"), "--output", str(directory / "d")]
        completed = subprocess.run(command, cwd=scientific.ROOT, capture_output=True, text=True, timeout=60)
        if completed.returncode:
            raise ValueError("D fixture failed: " + completed.stderr[-1000:])
        result = scientific.read_json(directory / "d/result.json")
        stored = scientific.verified_export(directory / "d/handoff.json")
        science = scientific.scientific_payload(stored)
        if (len(science["disagreements"]) != 1 or len(science["questions"]) != 3 or
                any(hypothesis["status"] != "disputed" for hypothesis in science["hypotheses"])):
            raise ValueError("Human review must not silently settle the investigation")
        verify_continuity(science, scientific.verified_export(parent_path))
        item["stages"].append(result)
        item["verified_parent_links"] += 1
        item["D"] = "Scripted fixture complete with actual operator decision; scientific questions remain open"
        scientific.write_json(output / "result.json", report)
    print(json.dumps({"mode": "scripted_fixture", "ABCD_repetitions_passed": 3,
                      "verified_parent_links": 9, "model_calls": 0, "live_cockroach_verified": False}))
    return report


def verify_existing(output):
    report = scientific.read_json(output / "result.json")
    records, links = 0, 0
    for repetition in report["repetitions"]:
        parent = None
        for expected in repetition["stages"]:
            directory = output / str(repetition["repetition"]) / expected["stage"].lower()
            stored = scientific.verified_export(directory / "handoff.json")
            if (stored["run_id"] != expected["run_id"] or stored["current_state_hash"] != expected["state_hash"] or
                    stored["receipt_hash"] != expected["receipt_hash"]):
                raise ValueError("Stored record differs from the saved evaluation checkpoint")
            science = scientific.scientific_payload(stored)
            scientific.reproduce(science, directory)
            if parent:
                verify_continuity(science, parent)
                links += 1
            parent = stored
            records += 1
    print(json.dumps({"mode": "offline_export_reverification", "verified_records": records,
                      "verified_parent_links": links, "model_calls": 0, "live_cockroach_verified": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-note", help="Only supply an actual operator decision, never an invented approval")
    parser.add_argument("--reviewer")
    parser.add_argument("--decision", choices=["defer", "request_followup"])
    parser.add_argument("--verify-only", action="store_true", help="Recheck exports and recompute analysis; no new receipts")
    args = parser.parse_args()
    if args.verify_only:
        if args.review_note:
            parser.error("Verification cannot record a new review")
        verify_existing(args.output.resolve())
    elif args.review_note:
        if not args.reviewer or not args.decision:
            parser.error("Review requires --reviewer and --decision")
        finish_reviews(args.output.resolve(), args.reviewer, args.decision, args.review_note)
    else:
        evaluate(args.output.resolve())
