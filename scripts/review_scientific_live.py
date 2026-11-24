"""Read back the bounded scientific pilot; no inference, D, DDL, or DB writes."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from cli import storage
from cli.scientific import verify_continuity
from producers import scientific, scientific_local as local
from scripts.scientific_live import database_credential


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--configuration-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    url = database_credential(args.configuration_root / ".env.nebius")
    os.environ["YARE_DATABASE_URL"] = url
    os.environ.pop("YARE_S3_BUCKET", None)
    local.guard_database(root / "authorization-private.json")
    evidence = root / "readback-review"
    if evidence.exists():
        raise ValueError("Review evidence exists; do not overwrite")
    evidence.mkdir()
    summary = scientific.read_json(root / "verified-abc.json")
    rows, scientific_failures = [], []
    for repeat in range(1, 4):
        parent = None
        for stage in "ABC":
            run_id = f"public-science-local-20261124-{repeat}-{stage.lower()}"
            stored = storage.load_handoff(run_id=run_id)
            science = scientific.scientific_payload(stored)
            trace = stored["artifacts"][0]["evidence"]["local_model"]
            action = json.loads(json.loads(trace["calls"][1]["response_utf8"])["message"]["content"])
            local.verify_model_trace(trace, action["reasoning"], science)
            if parent:
                verify_continuity(science, parent)
            scientific.write_json(evidence / (str(repeat) + "-" + stage.lower() + ".json"), stored)
            if stage == "B":
                previous = scientific.scientific_payload(parent)
                old = {" ".join(item["statement"].lower().split()) for item in previous["hypotheses"]}
                duplicate = [item["id"] for item in action["reasoning"]["hypotheses"]
                             if " ".join(item["statement"].lower().split()) in old]
                if duplicate:
                    scientific_failures.append({"run_id": run_id, "code": "copied_hypothesis_not_competing_interpretation",
                                                "hypothesis_ids": duplicate})
            strings = json.dumps(action["reasoning"], ensure_ascii=False)
            if re.search(r"(?:ra_error|dec_error).{0,30}" + chr(176), strings):
                scientific_failures.append({"run_id": run_id, "code": "gaia_error_unit_mislabeled_degrees_instead_of_mas"})
            rows.append({"run_id": run_id, "state_hash": stored["current_state_hash"], "receipt_hash": stored["receipt_hash"],
                         "parent": science["parent"], "observations": len(science["observations"]),
                         "open_questions": len(science["questions"]), "model_asserted_disagreements": len(science["disagreements"]),
                         "interpretations_verified": False})
            parent = stored
    ids = [row["run_id"] for row in rows]
    tables = ["yare_runs", "yare_lead_artifacts", "yare_current_states", "yare_receipts", "yare_memory_vectors",
              "yare_run_snapshots", "yare_events"]
    sql = " UNION ALL ".join("SELECT '" + table + "', count(*) FROM " + table + " WHERE run_id=ANY(%s)" for table in tables)
    with storage._connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, tuple(ids for _ in tables))
            counts = dict(cursor.fetchall())
    if any(counts[table] != 9 for table in tables if table != "yare_memory_vectors"):
        raise ValueError("Unexpected scoped durable row count")
    task = scientific.TASK + ": public-science-local-20261124-3"
    cases = [("what needs human review?", "human approval items"), ("which files changed?", "what changed"),
             ("what remains unfinished?", "open loops"), ("what is unverified?", "what is unverified"),
             ("what contradictions exist?", "contradictions"), ("what is the next clean action?", "next clean action")]
    search = []
    for query, expected in cases:
        hits = storage.search_memory(query, 1, task=task)
        search.append({"query": query, "expected_section": expected,
                       "actual_section": hits[0]["section_name"] if hits else None,
                       "pass": bool(hits and hits[0]["section_name"] == expected)})
    responses = [scientific.read_json(path) for path in root.glob("*/acquisition/response-*.json")]
    successful = [scientific.read_json(path) for path in root.glob("*/record/result.json")]
    selected = ["cli/scientific.py", "cli/storage.py", "cli/yare.py", "producers/scientific.py", "producers/scientific_local.py",
                "scripts/scientific_live.py", "scripts/review_scientific_live.py", "schemas/scientific-evidence.schema.json",
                "schemas/lead-artifact.schema.json", "examples/scientific-handoff/analysis.py", "examples/scientific-handoff/brief.md",
                "examples/scientific-handoff/data/manifest.json", "examples/scientific-handoff/data/ztf.json", "examples/scientific-handoff/data/gaia.csv"]
    fingerprints = {name: hashlib.sha256((scientific.ROOT / name).read_bytes()).hexdigest() for name in selected}
    ledger = args.configuration_root / ".tmp/nebius-first-test/budget.json"
    ledger_hash = hashlib.sha256(ledger.read_bytes()).hexdigest()
    if ledger_hash != local.LEDGER_DIGEST:
        raise ValueError("Paid ledger changed")
    report = {"status": "continuity_verified_scientific_reasoning_acceptance_failed_D_not_run",
              "model": local.MODEL, "model_digest": local.MODEL_DIGEST, "records": rows, "scoped_database_counts": counts,
              "six_section_queries": search, "scientific_reasoning_failures": scientific_failures,
              "local_generations_including_failures": len(responses), "paid_model_calls": 0,
              "total_prompt_tokens": sum(item["prompt_eval_count"] for item in responses),
              "total_generated_tokens": sum(item["eval_count"] for item in responses),
              "model_duration_ms": sum(item["total_duration"] for item in responses) / 1e6,
              "compile_commit_local_write_ms": {"min": min(item["compile_ms"] for item in successful),
                                                  "max": max(item["compile_ms"] for item in successful)},
              "db_reload_and_verify_ms": {"min": min(item["cockroach_reload_ms"] for item in successful),
                                            "max": max(item["cockroach_reload_ms"] for item in successful)},
              "physical_database_growth_measured": False, "controller_fingerprints_final_revision_only": fingerprints,
              "ledger_sha256_unchanged": ledger_hash, "D_executions": 0, "human_decision_recorded": False,
              "limitations": ["Same cached model in independent fresh processes, not independent model families",
                              "Resumed first repetition after controller corrections, not a pristine first-attempt pass",
                              "Interpretation labels are model statements, not scientific truth or authenticated evidence",
                              "Six section queries do not establish broad semantic retrieval quality",
                              "No telescope follow-up, classification, affiliation, publication, or frontend changes"]}
    scientific.write_json(root / "review-result.json", report)
    print(json.dumps({key: report[key] for key in ("status", "scoped_database_counts", "six_section_queries",
                      "scientific_reasoning_failures", "local_generations_including_failures", "total_prompt_tokens",
                      "total_generated_tokens", "compile_commit_local_write_ms", "db_reload_and_verify_ms", "D_executions")}, indent=2))


if __name__ == "__main__":
    main()
