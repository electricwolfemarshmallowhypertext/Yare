"""Bounded local research run; stops before D and never imports a paid model client."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cli import storage
from cli.scientific import verify_continuity
from producers import scientific, scientific_local as local


def database_credential(path):
    # Reuse the project's simple dotenv assignment format; load only the DB value.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            if name.strip() == "YARE_DATABASE_URL":
                return value.strip().strip("\"'")
    raise ValueError("Existing database credential unavailable")


def preflight(root, source_root):
    ledger = source_root / ".tmp/nebius-first-test/budget.json"
    if hashlib.sha256(ledger.read_bytes()).hexdigest() != local.LEDGER_DIGEST:
        raise ValueError("Paid ledger differs from preserved baseline")
    if root.exists():
        raise ValueError("Live evidence directory already exists; do not overwrite")
    model = local.verify_cached_model(Path.home() / ".ollama/models")
    # Check every frozen source before intentional adapter changes separately.
    checkpoint = scientific.read_json(scientific.EXAMPLE / "evaluation-checkpoint.json")
    root.mkdir(parents=True)
    scientific.write_json(root / "model-integrity.json", model)
    run_ids = [f"public-science-local-20261124-{repeat}-{stage}" for repeat in range(1, 4) for stage in "abc"]
    authorization = {"provider": "ollama-local", "paid_calls": False, "stop_before": "D", "max_calls": 24,
                     "run_ids": run_ids, "ledger_path": str(ledger), "ledger_sha256": local.LEDGER_DIGEST,
                     "billing_observed": {"period": "2026-11-01 through 2026-11-24", "net_usd": "0.00",
                         "ru_used": 13096, "ru_configured_limit": 4000000,
                         "storage_used_mib": 22.37, "storage_configured_limit_mib": 409},
                     "approval": "Owner approved local-only execution, no paid calls/cap changes, stop before D"}
    scientific.write_json(root / "authorization-private.json", authorization)
    url = database_credential(source_root / ".env.nebius")
    local.guard_database(root / "authorization-private.json")
    tables = ["yare_runs", "yare_current_states", "yare_lead_artifacts", "yare_receipts", "yare_memory_vectors",
              "yare_run_snapshots", "yare_events"]
    with storage._connect(url) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, has_table_privilege(current_user, name, 'SELECT'), "
                           "has_table_privilege(current_user, name, 'INSERT') FROM unnest(%s::STRING[]) AS t(name)", (tables,))
            permissions = cursor.fetchall()
    if len(permissions) != 7 or any(not row[1] or not row[2] for row in permissions):
        raise ValueError("Existing runtime role lacks required table access; no grants performed")
    scientific.write_json(root / "preflight.json", {"ledger_sha256": local.LEDGER_DIGEST,
        "model_integrity": model, "table_access": [{"table": row[0], "select": row[1], "insert": row[2]} for row in permissions],
        "billing": authorization["billing_observed"], "checkpoint_version": checkpoint.get("version"),
        "local_inference_started": False, "schema_changes": False})
    scientific.prepare_bundle(scientific.EXAMPLE / "data/manifest.json", root / "bundle.json")
    return url, authorization


def validate_saved(root, url):
    records = []
    os.environ["YARE_DATABASE_URL"] = url
    for repeat in range(1, 4):
        parent = None
        for stage in "ABC":
            run_id = f"public-science-local-20261124-{repeat}-{stage.lower()}"
            stored = storage.load_handoff(run_id=run_id)
            science = scientific.scientific_payload(stored)
            evidence = stored["artifacts"][0]["evidence"]
            trace = evidence["local_model"]
            action = json.loads(json.loads(trace["calls"][1]["response_utf8"])["message"]["content"])
            local.verify_model_trace(trace, action["reasoning"], science)
            if science["execution"] != "live_model" or science["stage"] != stage or science["human_review"] is not None:
                raise ValueError("Wrong live record stage or unexpected human decision")
            if parent:
                verify_continuity(science, parent)
            matches = [path.parent for path in root.glob(str(repeat) + "-" + stage.lower() + "*/record/result.json")]
            if len(matches) != 1:
                raise ValueError("Successful record directory ambiguous")
            directory = matches[0]
            reproduction = scientific.reproduce(science, directory)
            result = {"run_id": run_id, "state_hash": stored["current_state_hash"], "receipt_hash": stored["receipt_hash"],
                      "parent": science["parent"], "hypotheses": science["hypotheses"], "questions": science["questions"],
                      "disagreements": science["disagreements"], "observations": len(science["observations"]),
                      "analysis_reproduced": reproduction["exit_code"] == 0,
                      "prompt_tokens": sum(json.loads(call["response_utf8"])["prompt_eval_count"] for call in trace["calls"]),
                      "generated_tokens": sum(json.loads(call["response_utf8"])["eval_count"] for call in trace["calls"]),
                      "session_id": trace["session_id"], "pid": trace["pid"]}
            records.append(result)
            parent = stored
    if len({row["session_id"] for row in records}) != 9 or len({row["pid"] for row in records}) != 9:
        raise ValueError("Fresh process/session separation not established")
    result = {"status": "ABC_completed_D_pending_human_review", "provider": "ollama-local", "model": local.MODEL,
              "records": records, "local_generations": len(list(root.glob("*/acquisition/request-*.json"))), "paid_model_calls": 0,
              "parent_links_verified": 6, "scientific_classification_verified": False}
    scientific.write_json(root / "verified-abc.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Retain every failed attempt and all usage counters")
    parser.add_argument("--approved-controller-resume", action="store_true", help="Owner approved resumption after the two structural failures")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.source_root = args.source_root.resolve()
    server = None
    try:
        if args.resume:
            authorization_path = args.output / "authorization-private.json"
            authorization = scientific.read_json(authorization_path)
            if hashlib.sha256((args.source_root / ".tmp/nebius-first-test/budget.json").read_bytes()).hexdigest() != local.LEDGER_DIGEST:
                raise ValueError("Paid ledger differs")
            authorization["max_calls"] = 24
            authorization["resume_note"] = "Original 24-generation plan retained; failed controller-schema attempt preserved"
            if args.approved_controller_resume:
                authorization["controller_resume_approval"] = "Owner: Resume after the controller fix; original 24 local generations, no paid calls, stop before D"
            scientific.write_json(authorization_path, authorization)
            url = database_credential(args.source_root / ".env.nebius")
            local.guard_database(authorization_path)
            model = local.verify_cached_model(Path.home() / ".ollama/models")
            scientific.write_json(args.output / "resume-model-integrity.json", model)
        else:
            url, authorization = preflight(args.output, args.source_root)
        # A private, loopback-only instance; do not reuse or stop another user's server.
        import socket
        with socket.socket() as check:
            if check.connect_ex(("127.0.0.1", 11435)) == 0:
                raise ValueError("Dedicated local inference port already in use")
        env = os.environ.copy()
        for name in list(env):
            if any(word in name.upper() for word in ("API_KEY", "TOKEN", "SECRET", "DATABASE_URL")):
                env.pop(name)
        env.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_NO_CLOUD="1", OLLAMA_CONTEXT_LENGTH="8192",
                   OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_NUM_PARALLEL="1")
        exe = Path.home() / "AppData/Local/Programs/Ollama/ollama.exe"
        server_attempt = str(len(list(args.output.glob("server-*-config.json"))) + 1)
        with (args.output / ("server-" + server_attempt + ".stdout.log")).open("wb") as stdout, (args.output / ("server-" + server_attempt + ".stderr.log")).open("wb") as stderr:
            server = subprocess.Popen([str(exe), "serve"], env=env, stdout=stdout, stderr=stderr,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            for _ in range(40):
                if server.poll() is not None:
                    raise ValueError("Dedicated local Ollama server exited")
                try:
                    local.request_local("/api/tags", timeout=2)
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise ValueError("Dedicated loopback Ollama did not start")
            scientific.write_json(args.output / ("server-" + server_attempt + "-config.json"), {"pid": server.pid, "endpoint": local.ENDPOINT,
                "OLLAMA_NO_CLOUD": "1", "model_downloads": 0, "paid_provider_clients": False})
            child_env = os.environ.copy()
            child_env["YARE_DATABASE_URL"] = url
            child_env.pop("YARE_S3_BUCKET", None)
            for repeat in range(1, 4):
                for stage in "ABC":
                    base = str(repeat) + "-" + stage.lower()
                    prior = list(args.output.glob(base + "*/record/result.json"))
                    if prior:
                        print("Keeping already persisted " + base, flush=True)
                        continue
                    failed = list(args.output.glob(base + "*/failure.json"))
                    if len(failed) >= (3 if args.approved_controller_resume else 2):
                        raise ValueError("Two failed responses for " + base + "; stopping")
                    stage_output = args.output / (base if not failed else base + "-attempt" + str(len(failed) + 1))
                    print(f"Starting independent session {repeat}-{stage}", flush=True)
                    run_id = f"public-science-local-20261124-{repeat}-{stage.lower()}"
                    command = [sys.executable, "-m", "producers.scientific_local", "--stage", stage,
                               "--investigation-id", f"public-science-local-20261124-{repeat}", "--run-id", run_id,
                               "--output", str(stage_output),
                               "--authorization", str(args.output / "authorization-private.json")]
                    if stage == "A":
                        command += ["--bundle", str(args.output / "bundle.json")]
                    else:
                        command += ["--parent-run-id", f"public-science-local-20261124-{repeat}-{chr(ord(stage.lower()) - 1)}"]
                    run = subprocess.run(command, env=child_env, cwd=scientific.ROOT, capture_output=True, text=True, timeout=420)
                    scientific.write_json(args.output / (stage_output.name + "-process.json"),
                                          {"exit_code": run.returncode, "stdout": run.stdout,
                                           "stderr": run.stderr.replace(url, "[DATABASE_URL_REDACTED]")})
                    if run.returncode:
                        raise ValueError(f"Local stage {repeat}-{stage} failed; inspect retained evidence before any retry")
                    print(run.stdout.strip(), flush=True)
            summary = validate_saved(args.output, url)
            print(json.dumps({"status": summary["status"], "records": len(summary["records"]), "paid_model_calls": 0}), flush=True)
    except Exception as exc:
        if args.output.exists():
            scientific.write_json(args.output / "stopped.json", {"status": "stopped_not_proven", "reason": str(exc)})
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        ledger = args.source_root / ".tmp/nebius-first-test/budget.json"
        if hashlib.sha256(ledger.read_bytes()).hexdigest() != local.LEDGER_DIGEST:
            raise ValueError("Shared ledger changed")


if __name__ == "__main__":
    main()
