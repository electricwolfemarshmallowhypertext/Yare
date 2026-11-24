"""Explicit command capture; no automatic hook installation or model invocation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid


def run_command(command: list[str], root: Path) -> dict:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def git_output(root: Path, *args: str) -> str:
    result = run_command(["git", *args], root)
    return result["stdout"] if result["exit_code"] == 0 else ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicitly supplied command and capture a Lead Artifact")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--tool", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--test-command-json", help="JSON argv array for an explicitly authorized test command")
    parser.add_argument("--open-loop", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("supply the command after --")
    test_command = None
    if args.test_command_json:
        try:
            test_command = json.loads(args.test_command_json)
        except json.JSONDecodeError:
            parser.error("test command must be a JSON argv array")
        if not isinstance(test_command, list) or not test_command or any(
                not isinstance(value, str) or not value for value in test_command):
            parser.error("test command must be a nonempty string argv array")
    root = args.root.resolve(strict=True)
    before = git_output(root, "rev-parse", "HEAD").strip()
    try:
        process = run_command(command, root)
        test = run_command(test_command, root) if test_command else None
    except OSError:
        print("capture_command_unavailable")
        return 1
    diff_base = before or "HEAD"
    evidence = {"process": process, "diff": git_output(root, "diff", "--no-ext-diff", diff_base),
                "commit_before": before, "commit_after": git_output(root, "rev-parse", "HEAD").strip()}
    claims = []
    if test:
        claim = "Test command " + json.dumps(test["command"]) + " passed with exit code 0"
        evidence["test_run"] = {**test, "kind": "test", "claim": claim, "expected_exit_code": 0}
        supported = test["exit_code"] == 0 and bool(test["stdout"].strip() or test["stderr"].strip())
        claims.append({"claim": claim, "verification_status": "verified" if supported else "unverified",
                       "evidence_ref": "test_run"})
    files = sorted(set(git_output(root, "diff", "--name-only", diff_base).splitlines()
                       + git_output(root, "ls-files", "--others", "--exclude-standard").splitlines()))
    artifact = {"schema_version": "lead-artifact.v1", "run_id": "capture-" + uuid.uuid4().hex,
                "tool": args.tool, "task": args.task,
                "timestamp": datetime.now(timezone.utc).isoformat(), "claims": claims,
                "decisions": [], "files_touched": files, "open_loops": args.open_loop,
                "contradictions": [], "human_approval_items": [],
                "verification_status": "partial" if args.open_loop else "unverified", "evidence": evidence}
    destination = root / ".yare" / "captures"
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / (artifact["run_id"] + ".json")
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print("artifact: " + output.relative_to(root).as_posix())
    return test["exit_code"] if test and test["exit_code"] else process["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
