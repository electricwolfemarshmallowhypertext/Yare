"""Record the owner's diagnostic-only review; never imports or invokes a model client."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests

from cli import storage
from producers import scientific

SOURCE = "https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_main_source_catalogue/ssec_dm_gaia_source.html"
DECISION = ("Defer source classification. Retain the duplicated hypotheses, disputed unit statements, "
            "unresolved Gaia associations and unsupported trend claim. Request diagnostic follow-up only.")


def freeze_unit_reference(directory):
    if directory.exists():
        raise ValueError("Unit reference already exists; do not overwrite")
    response = requests.get(SOURCE, timeout=30)
    response.raise_for_status()
    if response.url != SOURCE or len(response.content) > 1048576:
        raise ValueError("Unexpected unit-reference source or size")
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
    parser = Text()
    parser.feed(response.content.decode("utf-8"))
    text = " ".join(" ".join(parser.parts).split())
    import re
    excerpts = []
    for key in ("ra_error", "dec_error"):
        match = re.search(key + r"\s*:\s*Standard error[^:]{0,150}?Angle\[mas\]\)", text)
        if not match:
            raise ValueError("Gaia unit definition not found in official source")
        excerpts.append(match.group())
    excerpt = "\n".join(excerpts)
    reference = {"source_url": SOURCE, "acquired_at": datetime.now(timezone.utc).isoformat(),
                 "document_sha256": hashlib.sha256(response.content).hexdigest(),
                 "excerpt": excerpt, "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                 "units": {"ra_error": "mas", "dec_error": "mas"}}
    directory.mkdir(parents=True)
    (directory / "gaia-source.html").write_bytes(response.content)
    scientific.write_json(directory / "units.json", reference)
    return reference


def record_decisions(root, output, unit_reference):
    """Uses existing storage/compiler APIs; each human decision binds one C receipt."""
    if output.exists():
        raise ValueError("Human decision output exists; do not overwrite")
    output.mkdir(parents=True)
    results = []
    for repetition in range(1, 4):
        directory = output / str(repetition)
        parent_id = f"public-science-local-20261124-{repetition}-c"
        review = scientific.record_review(None, "owner-via-chat", "request_followup", DECISION,
                                          directory / "review.json", parent_run_id=parent_id)
        result = scientific.record_stage(None, "D", f"public-science-local-20261124-{repetition}",
                    f"public-science-local-20261124-{repetition}-d", {}, directory / "d", review=review,
                    storage_mode="cockroach", parent_run_id=parent_id, deterministic_review=True,
                    unit_reference=unit_reference)
        results.append(result)
    scientific.write_json(output / "result.json", {"work_state_continuity": "PASSED",
        "scientific_reasoning_acceptance": "FAILED", "execution": "human_decision",
        "new_model_generations": 0, "decision": DECISION, "records": results})
    return results


def snapshot_originals(root):
    output = root / "pre-human-review-originals.json"
    if output.exists():
        raise ValueError("Original-evidence checkpoint exists; do not overwrite")
    files = {}
    for pattern in ("*/acquisition/request-*.json", "*/acquisition/response-*.json", "*/acquisition/trace.json",
                    "*/acquisition/analysis-tool.json", "*/failure.json", "*/record/handoff.json"):
        for path in sorted(root.glob(pattern)):
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    scientific.write_json(output, {"files": files, "response_count": len(list(root.glob("*/acquisition/response-*.json"))),
                                   "original_receipt_count": len(list(root.glob("*/record/handoff.json")))})


def verify_recorded_decisions(root, output):
    snapshot = scientific.read_json(root / "pre-human-review-originals.json")
    if any(hashlib.sha256((root / name).read_bytes()).hexdigest() != value for name, value in snapshot["files"].items()):
        raise ValueError("Original evidence changed")
    before = scientific.read_json(root / "review-result.json")
    # Nine original read-backs plus one scoped count keep the original SELECT envelope intact.
    for old in before["records"]:
        saved = storage.load_handoff(run_id=old["run_id"])
        if saved["current_state_hash"] != old["state_hash"] or saved["receipt_hash"] != old["receipt_hash"]:
            raise ValueError("Original database identity changed")
    results = scientific.read_json(output / "result.json")
    run_ids = [row["run_id"] for row in before["records"]] + [row["run_id"] for row in results["records"]]
    tables = ["yare_runs", "yare_lead_artifacts", "yare_current_states", "yare_receipts", "yare_memory_vectors",
              "yare_run_snapshots", "yare_events"]
    query = " UNION ALL ".join("SELECT '" + table + "', count(*) FROM " + table + " WHERE run_id=ANY(%s)" for table in tables)
    with storage._connect(__import__("os").environ["YARE_DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, tuple(run_ids for _ in tables))
            counts = dict(cursor.fetchall())
    if any(counts[name] != 12 for name in tables if name != "yare_memory_vectors"):
        raise ValueError("Incomplete live/human durable records")
    results.update(original_database_identities_unchanged=True, original_evidence_bytes_unchanged=True,
                   original_local_generations=snapshot["response_count"], scoped_database_counts=counts,
                   parent_links_verified=9, D_records_read_back=3)
    scientific.write_json(output / "verified-result.json", results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-reference", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--unit-reference", type=Path)
    parser.add_argument("--configuration-root", type=Path)
    args = parser.parse_args()
    if args.freeze_reference:
        result = freeze_unit_reference(args.freeze_reference)
        print(json.dumps({"reference_sha256": result["document_sha256"], "units": result["units"]}))
        return
    if not all((args.root, args.output, args.unit_reference, args.configuration_root)):
        parser.error("Record mode requires root, output, unit-reference and configuration-root")
    # Reuse only the local statement guard and credential parser. Neither makes a model call.
    import os
    from producers.scientific_local import guard_database, LEDGER_DIGEST
    from scripts.scientific_live import database_credential
    ledger = args.configuration_root / ".tmp/nebius-first-test/budget.json"
    before = ledger.read_bytes()
    if hashlib.sha256(before).hexdigest() != LEDGER_DIGEST:
        raise ValueError("Paid ledger differs")
    os.environ["YARE_DATABASE_URL"] = database_credential(args.configuration_root / ".env.nebius")
    os.environ.pop("YARE_S3_BUCKET", None)
    guard_database(args.root / "authorization-private.json")
    try:
        snapshot_originals(args.root)
        results = record_decisions(args.root, args.output, scientific.read_json(args.unit_reference))
        verified = verify_recorded_decisions(args.root, args.output)
        print(json.dumps({"D_records": len(results), "new_model_generations": 0, "decision": DECISION}))
    finally:
        if ledger.read_bytes() != before:
            raise ValueError("Paid ledger changed")


if __name__ == "__main__":
    main()
