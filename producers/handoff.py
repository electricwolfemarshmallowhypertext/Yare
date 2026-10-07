"""Separate A and B processes, joined only by stored Yare memory."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg

from cli.yare import compile_lead_state
from producers.nemotron import Budget, OpenShellRepo, TokenFactory, coding_loop, read_settings, save_json

TASK = "Evidence-based claim classification with case and whitespace normalization"


def load_handoff(database_url, run_id):
    with psycopg.connect(database_url, connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_state_hash, state_json FROM yare_current_states "
                           "WHERE run_id = %s ORDER BY created_at DESC LIMIT 1", (run_id,))
            state = cursor.fetchone()
            cursor.execute("SELECT artifact_json FROM yare_lead_artifacts WHERE run_id = %s "
                           "ORDER BY created_at DESC LIMIT 1", (run_id,))
            artifact = cursor.fetchone()
            cursor.execute("SELECT receipt_hash FROM yare_receipts WHERE run_id = %s "
                           "AND current_state_hash = %s ORDER BY created_at DESC LIMIT 1",
                           (run_id, state[0] if state else ""))
            receipt = cursor.fetchone()
    if not state or not artifact or not receipt:
        raise ValueError("Durable handoff rows missing")
    return {"run_id": run_id, "current_state_hash": state[0], "current_state": state[1],
            "artifact": artifact[0], "receipt_hash": receipt[0]}


def make_artifact(run_id, phase, result, source, full_test, policy_hash):
    evidence = {"partial_test": result["final_test"], "full_test": full_test,
                "diff": result["diff"], "source_code": source,
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "policy_sha256": policy_hash,
                "handoff_assessment": result.get("handoff_assessment")}
    claims = [{"claim": f"Agent {phase} observed test command {json.dumps(result['final_test']['command'])} "
               "passed with exit code 0", "verification_status": "verified"}]
    if phase == "A":
        claims.append({"claim": "All full-suite tests passed", "verification_status": "unverified"})
        evidence["challenge_note"] = "Deliberately seeded unsupported claim for the handoff integrity test."
    return {"schema_version": "lead-artifact.v1", "run_id": run_id, "tool": "Nemotron-" + phase,
            "task": TASK, "timestamp": datetime.now(timezone.utc).isoformat(), "claims": claims,
            "decisions": ["Tests are evidence; agent statements alone are not verification."],
            "files_touched": ["workstate.py"], "open_loops":
            ["Normalize status case and whitespace, then run full suite"] if phase == "A" else [],
            "contradictions": [], "human_approval_items": [], "verification_status": "partial" if phase == "A" else "verified",
            "source_artifacts": ["sha256:" + evidence["source_sha256"], "policy-sha256:" + policy_hash],
            "evidence": evidence}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["a", "b"], required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sandbox", required=True)
    parser.add_argument("--routed", action="store_true", help="Call Token Factory through OpenShell provider access")
    parser.add_argument("--stop-on-refresh", action="store_true", help="Stop routed inference if OpenShell refreshes again")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    settings = read_settings(root / ".env.nebius")
    os.environ["YARE_DATABASE_URL"] = settings["YARE_DATABASE_URL"]
    # This test uses the existing database path, without invoking unrelated archives.
    os.environ.pop("YARE_S3_BUCKET", None)
    budget = Budget(root / ".tmp/nebius-first-test/budget.json")
    evidence_dir = root / ".tmp/handoff" / args.run_id / args.phase
    target = "test_workstate.ClaimTests" if args.phase == "a" else "test_workstate"
    repo = OpenShellRepo(root, args.sandbox, target)
    if args.routed:
        from producers.routing import RoutedTokenFactory
        client = RoutedTokenFactory(repo, budget, evidence_dir, stop_on_refresh=args.stop_on_refresh)
    else:
        client = TokenFactory(settings["NEBIUS_API_KEY"], budget, evidence_dir)
    models = client.models([settings["NEBIUS_MODEL_ID"], settings["NEBIUS_EXPLAIN_MODEL_ID"]])
    loaded = None
    if args.phase == "b":
        loaded = load_handoff(settings["YARE_DATABASE_URL"], args.run_id + "-a")
        save_json(evidence_dir / "loaded-handoff.json", loaded)
        repo.write(loaded["artifact"]["evidence"]["source_code"])
    prompt = (
        "You are agent A. Fix only the missing evidence check for verified claims. "
        "Preserve contradictions. Leave case/whitespace normalization for agent B. "
        "Your passing target is test_workstate.ClaimTests. Do not modify tests. "
        if args.phase == "a" else
        "You are agent B in a fresh process and sandbox. Read the stored handoff; "
        "distinguish A's passing partial tests from its seeded unverified full-suite claim. "
        "Complete case/whitespace normalization for string statuses while preserving evidence checks "
        "and contradictions. Run the full test_workstate suite. Do not modify tests. "
    )
    result = coding_loop(client, models[0], repo, evidence_dir, prompt, loaded)
    full_test = repo.execute("python", "-m", "unittest", "-v", "test_workstate")
    if args.phase == "a" and full_test["exit_code"] == 0:
        raise ValueError("A unexpectedly finished the whole task; partial handoff not demonstrated")
    if args.phase == "b" and full_test["exit_code"] != 0:
        raise ValueError("B full suite did not pass")
    source = repo.read("workstate.py")
    phase = args.phase.upper()
    policy_suffix = "-routed" if args.routed else ""
    policy = root / "examples/nemotron-handoff" / f"agent-{args.phase}{policy_suffix}.yaml"
    artifact = make_artifact(args.run_id + "-" + args.phase, phase, result, source, full_test,
                             hashlib.sha256(policy.read_bytes()).hexdigest())
    artifact["evidence"]["inference_transport"] = "OpenShell endpoint-bound provider" if args.routed else "host controller"
    artifact_path = evidence_dir / "lead-artifact.json"
    save_json(artifact_path, artifact)
    packet, _, _, receipt_path, receipt, _ = compile_lead_state(root, TASK, [artifact_path], validate_artifacts=True)
    stored = load_handoff(settings["YARE_DATABASE_URL"], artifact["run_id"])
    if stored["artifact"].get("evidence") != artifact["evidence"]:
        raise ValueError("Stored artifact lost handoff evidence")
    summary = {"phase": phase, "run_id": artifact["run_id"], "current_state_hash": packet["deterministic_hash"],
               "receipt_hash": receipt["receipt_hash"], "receipt_path": str(receipt_path.relative_to(root)),
               "test_result": full_test, "coding_model": models[0],
               "calls_total": len(budget.state["calls"]),
               "estimated_usd_total": str(sum(Decimal(c["charged_usd"]) for c in budget.state["calls"])),
               "handoff_assessment": result.get("handoff_assessment"), "diff": result["diff"]}
    if args.phase == "b":
        explanation = client.complete(models[1], [
            {"role": "system", "content": "Explain observed A-to-B continuity, test evidence, scope denial, "
             "and final tests. Do not invent success. Keep it concise."},
            {"role": "user", "content": json.dumps(summary)},
        ])
        summary["explanation"] = explanation
        summary["explanation_status"] = "unverified model commentary; not execution evidence"
        summary["calls_total"] = len(budget.state["calls"])
        summary["estimated_usd_total"] = str(sum(Decimal(c["charged_usd"]) for c in budget.state["calls"]))
    save_json(evidence_dir / "result.json", summary)
    print(f"phase {phase}: PASS")
    print("run_id:", summary["run_id"])
    print("current_state_hash:", summary["current_state_hash"])
    print("receipt_hash:", summary["receipt_hash"])
    print("full_suite_exit_code:", full_test["exit_code"])
    print("calls_total:", summary["calls_total"])
    print("estimated_usd_total:", summary["estimated_usd_total"])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("handoff phase FAIL:", type(error).__name__)
        raise SystemExit(1)
