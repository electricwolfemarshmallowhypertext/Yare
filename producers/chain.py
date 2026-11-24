"""Four fresh coding processes connected only by verified CockroachDB handoffs."""

import argparse
import ast
import base64
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import jsonschema
import psycopg

from cli.yare import compile_lead_state
from producers.handoff import load_handoff
from producers.nemotron import Budget, OpenShellRepo, TokenFactory, read_settings, save_json

TASK = "Four-agent work-state utility handoff"
TARGETS = {
    "normalize_status": "NormalizationTests",
    "classify_claim": "ClassificationTests",
    "summarize_claims": "SummaryTests",
    "choose_next_action": "ActionTests",
}
ACTION_FIELDS = {
    "read": {"path": {"enum": ["workstate.py", "test_workstate.py"]}},
    "assess_handoff": {
        "state_hash": {"type": "string"}, "receipt_hash": {"type": "string"},
        "focused_exit_code": {"type": "integer"}, "full_exit_code": {"type": "integer"},
        "explanation": {"type": "string", "minLength": 1},
    },
    "select_work": {"function": {"enum": list(TARGETS)}, "reason": {"type": "string", "minLength": 1}},
    "write": {"proposal": {"type": "string", "minLength": 1},
              "body_lines": {"type": "array", "minItems": 1, "maxItems": 100,
                             "items": {"type": "string", "maxLength": 400}}},
    "test": {},
    "handoff": {"next_action": {"type": "string", "minLength": 1}},
}
PROTOCOL = """Return exactly one JSON action, without markdown or tool output:
{"action":"read","path":"workstate.py"} or test_workstate.py;
{"action":"assess_handoff","state_hash":"...","receipt_hash":"...","focused_exit_code":0,"full_exit_code":1,"explanation":"..."};
{"action":"select_work","function":"one function name","reason":"why this is next"};
{"action":"write","proposal":"your change","body_lines":["first body line","    nested body line"]};
{"action":"test"};
{"action":"handoff","next_action":"remaining work, or complete"}.
Read both files before selecting or editing. If a stored handoff is supplied,
assess its exact hashes and both observed test exit codes before selecting work.
Choose one currently failing function. Only that function's body may change.
Write its complete body as an array of lines, with indentation relative to the
function body. Do not include a def line or other functions. Do not embed newline
characters in a line; the controller joins and indents the lines before execution.
The controller executes tests; never supply stdout, test results, or shell commands.
The controller closes your turn after a passing focused test; do not fix another function.
"""
TEST_PROGRAM = """import json,sys,unittest
suite=unittest.defaultTestLoader.loadTestsFromName(TARGET)
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'tests_run':result.testsRun,'failed_tests':sorted(t.id() for t,_ in result.failures+result.errors),'skipped':len(result.skipped)}))
sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
"""


def digest(value):
    return hashlib.sha256(value).hexdigest()


def parse_action(answer):
    value = json.loads(answer)
    if not isinstance(value, dict) or value.get("action") not in ACTION_FIELDS:
        raise ValueError("Unknown action")
    fields = ACTION_FIELDS[value["action"]]
    jsonschema.validate(value, {"type": "object", "additionalProperties": False,
                               "properties": {"action": {"const": value["action"]}, **fields},
                               "required": ["action", *fields]})
    return value


def next_action_schema(inspected, needs_assessment, selected, wrote, focused):
    missing = {"workstate.py", "test_workstate.py"} - inspected
    if missing:
        kind = "read"
    elif needs_assessment:
        kind = "assess_handoff"
    elif selected is None:
        kind = "select_work"
    elif not wrote or focused is not None:
        kind = "write"
    else:
        kind = "test"
    fields = dict(ACTION_FIELDS[kind])
    if kind == "read":
        fields["path"] = {"type": "string", "enum": sorted(missing)}
    return {"type": "object", "additionalProperties": False,
            "properties": {"action": {"type": "string", "enum": [kind]}, **fields},
            "required": ["action", *fields]}


def check_edit(before, after, selected):
    old, new = ast.parse(before), ast.parse(after)
    if any(not isinstance(node, ast.FunctionDef) for node in old.body + new.body):
        raise ValueError("Only the four existing function definitions are allowed")
    if [node.name for node in new.body] != list(TARGETS):
        raise ValueError("Function names/order must not change")
    changed = []
    for left, right in zip(old.body, new.body):
        if ast.dump(left.args) != ast.dump(right.args) or right.decorator_list or right.returns:
            raise ValueError("Function signatures must not change")
        if ast.dump(left) != ast.dump(right):
            changed.append(left.name)
    if changed != [selected]:
        raise ValueError("Edit must change only the selected function")


def apply_body(before, selected, body_lines):
    if any("\n" in line or "\r" in line for line in body_lines):
        raise ValueError("Each body_lines item must be one source line")
    node = next(node for node in ast.parse(before).body if node.name == selected)
    lines = before.splitlines(True)
    after = "".join(lines[:node.body[0].lineno - 1] +
                    ["    " + line + "\n" for line in body_lines] + lines[node.end_lineno:])
    check_edit(before, after, selected)
    return after


class ChainRepo(OpenShellRepo):
    def test(self, target="test_workstate"):
        if target not in ["test_workstate", *["test_workstate." + value for value in TARGETS.values()]]:
            raise ValueError("Test target is not approved")
        code = "TARGET=" + repr(target) + "\n" + TEST_PROGRAM
        result = self.execute("python", "-c", code)
        summary = json.loads(result["stdout"])
        expected = 16 if target == "test_workstate" else 4
        failed = summary["failed_tests"]
        if (summary["tests_run"] != expected or summary["skipped"] != 0 or
                not isinstance(failed, list) or any(not isinstance(item, str) for item in failed) or
                result["exit_code"] != (1 if failed else 0)):
            raise ValueError("Incomplete or inconsistent test execution")
        return {**result, **summary}


def assess_matches(action, parent):
    evidence = parent["artifact"]["evidence"]
    return (action["state_hash"] == parent["current_state_hash"] and
            action["receipt_hash"] == parent["receipt_hash"] and
            action["focused_exit_code"] == evidence["partial_test"]["exit_code"] and
            action["full_exit_code"] == evidence["full_test"]["exit_code"])


def test_view(result):
    # Keep complete logs in receipts; avoid repeating large tracebacks in every model call.
    return {key: result[key] for key in ("exit_code", "tests_run", "failed_tests", "skipped")}


def run_turn(client, model, repo, evidence_dir, brief, parent=None):
    before = repo.read("workstate.py")
    tests_before = repo.read("test_workstate.py")
    baseline = repo.test()
    if not baseline["failed_tests"]:
        raise ValueError("Task already complete; four-agent chain not demonstrated")
    parent_view = None
    if parent:
        evidence = parent["artifact"]["evidence"]
        parent_view = {**{key: parent[key] for key in ("run_id", "current_state_hash", "receipt_hash", "current_state")},
                       "evidence": {key: evidence[key] for key in
                                    ("partial_test", "full_test", "selection", "controller_next_action")}}
        parent_view["evidence"]["full_test"] = test_view(evidence["full_test"])
        parent_view["evidence"]["partial_test"] = test_view(evidence["partial_test"])
    messages = [{"role": "system", "content": brief + "\n" + PROTOCOL},
                {"role": "user", "content": json.dumps({"baseline": test_view(baseline), "stored_handoff": parent_view})}]
    inspected, selected, assessment = set(), None, None
    focused, wrote, next_action = None, False, None
    events, invalid, edit_rejections = [], 0, []
    for _ in range(16):
        schema = next_action_schema(inspected, parent is not None and assessment is None, selected, wrote, focused)
        request_messages = messages + [{"role": "user", "content":
            "Return the next protocol action matching this schema. Choose the work and implementation yourself.\n" + json.dumps(schema)}]
        answer = client.complete(model, request_messages, extra_body={"response_format": {
            "type": "json_schema", "json_schema": {"name": "yare_chain_action", "strict": True, "schema": schema}}})
        try:
            action = parse_action(answer)
            jsonschema.validate(action, schema)
        except (ValueError, jsonschema.ValidationError):
            invalid += 1
            save_json(evidence_dir / "invalid-action.json", {"raw_response": answer})
            if invalid >= 2:
                raise ValueError("Repeated invalid actions; raw responses retained")
            messages.extend([{"role": "assistant", "content": answer},
                             {"role": "user", "content": "Action rejected: return one object matching the action schema; no output fields."}])
            continue
        invalid = 0
        kind = action["action"]
        result = None
        if kind == "read":
            result = repo.read(action["path"])
            inspected.add(action["path"])
        elif kind == "assess_handoff" and parent is not None:
            accepted = assess_matches(action, parent)
            if accepted:
                assessment = action
            result = {"accepted": accepted}
        elif kind == "select_work":
            group = TARGETS[action["function"]]
            failing = any("." + group + "." in item for item in baseline["failed_tests"])
            if inspected != {"workstate.py", "test_workstate.py"} or (parent and not assessment):
                result = {"rejected": "Read both files and assess the stored evidence first."}
            elif selected or not failing:
                result = {"rejected": "Choose exactly one currently failing function."}
            else:
                selected = action
                result = {"accepted": True}
        elif kind == "write" and selected:
            try:
                after = apply_body(before, selected["function"], action["body_lines"])
            except (ValueError, SyntaxError) as error:
                result = {"rejected": str(error)}
                edit_rejections.append(str(error))
                if len(edit_rejections) >= 2 and edit_rejections[-1] == edit_rejections[-2]:
                    events.append({"action": action, "result": result})
                    save_json(evidence_dir / "actions.json", events)
                    raise ValueError("Repeated identical edit rejection; inspect retained response before more calls")
            else:
                result = repo.write(after)
                focused, wrote = None, True
        elif kind == "test" and selected:
            focused = repo.test("test_workstate." + TARGETS[selected["function"]])
            result = focused
            if wrote and focused["exit_code"] == 0:
                next_action = "Inspect the remaining full-suite failures and select the next behavior."
        elif kind == "handoff" and wrote and focused and focused["exit_code"] == 0:
            next_action = action["next_action"]
            events.append({"action": action, "result": {"accepted": True}})
            break
        else:
            result = {"rejected": "Follow the schema: inspect, assess if needed, select, edit, test, handoff."}
        events.append({"action": action, "result": result})
        save_json(evidence_dir / "actions.json", events)
        if next_action is not None:
            break
        state = {"files_read": sorted(inspected), "parent_assessed": parent is None or assessment is not None,
                 "selected_function": selected["function"] if selected else None, "edit_applied": wrote}
        feedback = test_view(result) if kind == "test" and focused else result
        messages.extend([{"role": "assistant", "content": answer},
                         {"role": "user", "content": json.dumps({"result": feedback, "controller_state": state})}])
    if next_action is None:
        raise ValueError("Turn ended without a tested handoff")
    after = repo.read("workstate.py")
    check_edit(before, after, selected["function"])
    if repo.read("test_workstate.py") != tests_before:
        raise ValueError("Tests changed")
    focused = repo.test("test_workstate." + TARGETS[selected["function"]])
    full = repo.test()
    old_failures, new_failures = set(baseline["failed_tests"]), set(full["failed_tests"])
    if focused["exit_code"] != 0 or not new_failures < old_failures or len(old_failures - new_failures) != 4:
        raise ValueError("Independent checks did not confirm one improvement without regressions")
    if not new_failures:
        next_action = "Complete; all visible checks passed. Independent acceptance remains a controller check."
    result = {"selection": selected, "handoff_assessment": assessment, "next_action": next_action,
              "baseline_test": baseline, "final_test": focused, "full_test": full,
              "source_code": after, "diff": "".join(difflib.unified_diff(
                  before.splitlines(True), after.splitlines(True), fromfile="before/workstate.py", tofile="after/workstate.py"))}
    save_json(evidence_dir / "actions.json", events)
    save_json(evidence_dir / "coding-result.json", result)
    return result


def make_artifact(run_id, model, result, brief_hash, policy_hash, parent):
    claim = "Selected behavior passed all four focused tests"
    evidence = {"source_code": result["source_code"],
                "source_sha256": digest(result["source_code"].encode()), "diff": result["diff"],
                "partial_test": result["final_test"], "full_test": result["full_test"],
                "baseline_test": result["baseline_test"], "selection": result["selection"],
                "handoff_assessment": result["handoff_assessment"], "controller_next_action": result["next_action"],
                "brief_sha256": brief_hash, "policy_sha256": policy_hash, "coding_model": model,
                "test_claim": {**result["final_test"], "kind": "test", "claim": claim, "expected_exit_code": 0}}
    if parent:
        evidence["parent_handoff"] = {key: parent[key] for key in ("run_id", "current_state_hash", "receipt_hash")}
    failures = result["full_test"]["failed_tests"]
    return {"schema_version": "lead-artifact.v1", "run_id": run_id, "tool": "Nemotron-chain",
            "task": TASK, "timestamp": datetime.now(timezone.utc).isoformat(),
            "claims": [{"claim": claim, "verification_status": "verified", "evidence_ref": "test_claim"}],
            "decisions": [result["selection"]["reason"]], "files_touched": ["workstate.py"],
            "open_loops": ["Failing test: " + item for item in failures],
            "contradictions": [], "human_approval_items": [],
            "verification_status": "partial" if failures else "verified", "evidence": evidence}


def phase(root, run_id, letter, sandbox, parent_run_id=None):
    settings = read_settings(root / ".env.nebius")
    os.environ["YARE_DATABASE_URL"] = settings["YARE_DATABASE_URL"]
    os.environ.pop("YARE_S3_BUCKET", None)
    ledger = root / ".tmp/nebius-first-test/budget.json"
    if not ledger.exists():
        raise ValueError("Existing ledger required; refusing to create a new one")
    evidence_dir = root / ".tmp/chain" / run_id / letter
    repo = ChainRepo(root, sandbox)
    parent = None
    if letter != "a":
        parent = load_handoff(settings["YARE_DATABASE_URL"], parent_run_id or run_id + "-" + chr(ord(letter) - 1))
        if parent["artifact"]["task"] != TASK:
            raise ValueError("Wrong parent task")
        repo.write(parent["artifact"]["evidence"]["source_code"])
    fixture = root / "examples/nemotron-chain"
    if repo.read("test_workstate.py").strip() != (fixture / "test_workstate.py").read_text().strip():
        raise ValueError("Sandbox tests do not match fixed task")
    brief = (fixture / "brief.md").read_text()
    brief_hash = digest(brief.encode())
    if parent and parent["artifact"]["evidence"]["brief_sha256"] != brief_hash:
        raise ValueError("Brief changed between agents")
    budget = Budget(ledger)
    client = TokenFactory(settings["NEBIUS_API_KEY"], budget, evidence_dir)
    model = client.models([settings["NEBIUS_MODEL_ID"]])[0]
    result = run_turn(client, model, repo, evidence_dir, brief, parent)
    artifact = make_artifact(run_id + "-" + letter, model, result, brief_hash,
                             digest((fixture / "policy.yaml").read_bytes()), parent)
    path = evidence_dir / "lead-artifact.json"
    save_json(path, artifact)
    packet, _, _, _, receipt, _ = compile_lead_state(root, TASK, [path], validate_artifacts=True)
    stored = load_handoff(settings["YARE_DATABASE_URL"], artifact["run_id"])
    if stored["artifact"]["evidence"] != artifact["evidence"]:
        raise ValueError("Read-back differs from recorded evidence")
    save_json(evidence_dir / "stored-handoff.json", stored)
    summary = {"agent": letter.upper(), "sandbox": sandbox, "status": "recorded",
               "run_id": artifact["run_id"], "current_state_hash": packet["deterministic_hash"],
               "receipt_hash": receipt["receipt_hash"], "brief_sha256": brief_hash,
               "selected_function": result["selection"]["function"],
               "tests_passed": 16 - len(result["full_test"]["failed_tests"]),
               "tests_total": 16, "parent_handoff": artifact["evidence"].get("parent_handoff")}
    save_json(evidence_dir / "summary.json", summary)
    print(json.dumps(summary))


def check_ledger(before, after):
    for key in ("limit_usd", "max_calls", "max_tokens"):
        if after[key] != before[key]:
            raise ValueError("Shared ledger limits changed")
    if after["calls"][:len(before["calls"])] != before["calls"]:
        raise ValueError("Existing ledger entries changed")


def check_record_identity(stored, stage):
    if any(stored[key] != stage[key] for key in ("run_id", "current_state_hash", "receipt_hash")):
        raise ValueError("Read-back record differs from the recorded stage")


def sandbox_command(root, *args):
    result = subprocess.run(OpenShellRepo(root, "unused").cli + list(args),
                            capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        save_json(root / ".tmp/chain-lifecycle-failure.json",
                  {"command": list(args), "exit_code": result.returncode,
                   "stdout": result.stdout, "stderr": result.stderr})
        raise ValueError("OpenShell lifecycle command failed: " + " ".join(args[:2]))
    return result


def sandbox_name(run_id, suffix):
    return "yc-" + digest(run_id.encode())[:8] + "-" + suffix


def with_sandbox(root, name, operation):
    linux_root = "/mnt/" + root.drive[0].lower() + root.as_posix()[2:]
    created = False
    try:
        sandbox_command(root, "sandbox", "create", "--name", name, "--from", "yare-nemotron-chain:local",
                        "--policy", linux_root + "/examples/nemotron-chain/policy.yaml", "--detach",
                        "--no-auto-providers", "--", "python", "-c", "import time; time.sleep(3600)")
        created = True
        policy = json.loads(sandbox_command(root, "policy", "get", name, "--full", "-o", "json").stdout)
        if policy.get("status") != "effective":
            raise ValueError("Sandbox policy is not effective")
        paths = policy["policy"]["filesystem_policy"]
        if (paths.get("include_workdir") or
                set(paths["read_only"]) != {"/usr", "/lib", "/lib64", "/etc", "/proc", "/sandbox"} or
                set(paths["read_write"]) != {"/dev", "/tmp/yare-task"}):
            raise ValueError("Sandbox filesystem scope differs from fixed policy")
        return operation(policy)
    finally:
        # This runner only cleans its unique run-owned sandboxes.
        if created:
            sandbox_command(root, "sandbox", "stop", name)
            sandbox_command(root, "sandbox", "delete", name)


def orchestrate(root, run_id, seed_a=None):
    evidence_dir = root / ".tmp/chain" / run_id
    if evidence_dir.exists():
        raise ValueError("Run ID already has evidence; choose a new ID")
    ledger = root / ".tmp/nebius-first-test/budget.json"
    if not ledger.exists():
        raise ValueError("Existing ledger required")
    before = json.loads(ledger.read_text())
    if before.get("blocked"):
        raise ValueError("Shared ledger is blocked; not changing it")
    settings = read_settings(root / ".env.nebius")
    with psycopg.connect(settings["YARE_DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM yare_runs WHERE run_id = ANY(%s)",
                           ([run_id + "-" + letter for letter in "abcd"],))
            if cursor.fetchone()[0]:
                raise ValueError("Run ID already exists in CockroachDB")
    fixture = root / "examples/nemotron-chain"
    inputs = {name: digest((fixture / name).read_bytes())
              for name in ("brief.md", "workstate.py", "test_workstate.py", "policy.yaml", "acceptance.py")}
    manifest = {"status": "pending", "run_id": run_id, "input_sha256": inputs,
                "budget_before": {key: before[key] for key in ("max_calls", "max_tokens", "limit_usd")},
                "old_calls": len(before["calls"]), "old_calls_sha256": digest(json.dumps(before["calls"], sort_keys=True).encode()),
                "stages": []}
    if seed_a:
        stored = load_handoff(settings["YARE_DATABASE_URL"], seed_a)
        evidence = stored["artifact"]["evidence"]
        if (stored["artifact"]["task"] != TASK or evidence["brief_sha256"] != digest((fixture / "brief.md").read_text().encode()) or
                evidence["full_test"]["tests_run"] != 16 or len(evidence["full_test"]["failed_tests"]) != 12 or
                evidence["partial_test"]["exit_code"] != 0 or evidence.get("parent_handoff")):
            raise ValueError("Seed is not a verified A result for this fixed task")
        manifest["stages"].append({"agent": "A", "run_id": seed_a, "current_state_hash": stored["current_state_hash"],
                                   "receipt_hash": stored["receipt_hash"], "brief_sha256": evidence["brief_sha256"],
                                   "selected_function": evidence["selection"]["function"], "tests_passed": 4,
                                   "tests_total": 16, "status": "reused verified stored A"})
        manifest["resumed_from_a"] = seed_a
    save_json(evidence_dir / "budget-before.json", before)
    save_json(evidence_dir / "result.json", manifest)
    try:
        for letter in "bcd" if seed_a else "abcd":
            if any(digest((fixture / name).read_bytes()) != value for name, value in inputs.items()):
                raise ValueError("Fixed task inputs changed")
            check_ledger(before, json.loads(ledger.read_text()))
            name = sandbox_name(run_id, letter)

            def run_phase(policy):
                stage_dir = evidence_dir / letter
                save_json(stage_dir / "effective-policy.json", policy)
                command = [sys.executable, "-m", "producers.chain", "--run-id", run_id,
                           "--phase", letter, "--sandbox", name]
                if seed_a and letter == "b":
                    command.extend(["--parent-run-id", seed_a])
                result = subprocess.run(command, cwd=root,
                                        capture_output=True, text=True, timeout=2400)
                save_json(stage_dir / "process-result.json", {"exit_code": result.returncode,
                                                              "stdout": result.stdout, "stderr": result.stderr})
                if result.returncode != 0:
                    raise ValueError("Agent phase failed; evidence retained")
                return json.loads((stage_dir / "summary.json").read_text())

            stage = with_sandbox(root, name, run_phase)
            expected = (ord(letter) - ord("a") + 1) * 4
            if stage["tests_passed"] != expected:
                raise ValueError("Chain progress does not match observed test totals")
            manifest["stages"].append(stage)
            save_json(evidence_dir / "result.json", manifest)
            print(f"Agent {letter.upper()}: {stage['tests_passed']}/16; CockroachDB read-back verified", flush=True)

        def independent_check(policy):
            stored = load_handoff(settings["YARE_DATABASE_URL"], run_id + "-d")
            check_record_identity(stored, manifest["stages"][-1])
            repo = ChainRepo(root, sandbox_name(run_id, "verify"))
            repo.write(stored["artifact"]["evidence"]["source_code"])
            full = repo.test()
            program = (fixture / "acceptance.py").read_text()
            program += "\n" + TEST_PROGRAM.replace("loadTestsFromName(TARGET)", "loadTestsFromTestCase(AcceptanceTests)")
            encoded = base64.b64encode(program.encode()).decode()
            observed = repo.execute("python", "-c", "import base64; exec(base64.b64decode('" + encoded + "'))")
            summary = json.loads(observed["stdout"])
            if observed["exit_code"] != 0 or summary != {"tests_run": 8, "failed_tests": [], "skipped": 0} or full["exit_code"] != 0:
                raise ValueError("Independent final acceptance did not pass")
            return {"full_suite": full, "acceptance": observed, "policy_hash": policy["hash"],
                    "state_hash": stored["current_state_hash"], "receipt_hash": stored["receipt_hash"]}

        manifest["independent_final"] = with_sandbox(root, sandbox_name(run_id, "verify"), independent_check)
        for index, stage in enumerate(manifest["stages"]):
            stored = load_handoff(settings["YARE_DATABASE_URL"], stage["run_id"])
            check_record_identity(stored, stage)
            evidence = stored["artifact"]["evidence"]
            parent = evidence.get("parent_handoff")
            if index and parent != {key: manifest["stages"][index - 1][key]
                                    for key in ("run_id", "current_state_hash", "receipt_hash")}:
                raise ValueError("Broken durable parent chain")
            if evidence["brief_sha256"] != manifest["stages"][0]["brief_sha256"]:
                raise ValueError("Agent briefs differ")
        manifest["status"] = "PASS"
    except Exception as error:
        manifest.update(status="FAIL", failure_type=type(error).__name__, failure_reason=str(error)
                        if isinstance(error, ValueError) else "Infrastructure error; inspect private evidence")
        raise
    finally:
        after = json.loads(ledger.read_text())
        check_ledger(before, after)
        manifest["ledger_preserved"] = True
        manifest["calls_total"] = len(after["calls"])
        manifest["new_calls"] = len(after["calls"]) - len(before["calls"])
        manifest["estimated_usd_total"] = str(sum(Decimal(call["charged_usd"]) for call in after["calls"]))
        manifest["charged_tokens_total"] = sum(call["charged_tokens"] for call in after["calls"])
        save_json(evidence_dir / "result.json", manifest)
    print("chain: PASS; four fresh agents, three verified parent links, final acceptance passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=list("abcd"))
    parser.add_argument("--sandbox")
    parser.add_argument("--parent-run-id")
    parser.add_argument("--seed-a", help="Continue from a verified stored A; never rerun or relabel it")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,45}", args.run_id):
        parser.error("run-id must be a short lowercase identifier")
    root = Path(__file__).resolve().parents[1]
    if args.phase:
        if not args.sandbox:
            parser.error("phase requires sandbox")
        phase(root, args.run_id, args.phase, args.sandbox, args.parent_run_id)
        return
    orchestrate(root, args.run_id, args.seed_a)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never emit credential-bearing connection/provider exceptions.
        print("chain stopped:", type(error).__name__)
        raise SystemExit(1)
