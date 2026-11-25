"""Explicit command capture; no automatic hook installation or model invocation."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from cli.integrity import CAPTURE_FILE_MAX_BYTES

GENERATED_PARTS = {".git", ".yare", ".sticky", "__pycache__", ".pytest_cache"}


def run_command(command: list[str], root: Path) -> dict:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    return {"command": command, "exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def git_output(root: Path, *args: str) -> str:
    result = run_command(["git", *args], root)
    return result["stdout"] if result["exit_code"] == 0 else ""


def workspace_snapshot(root: Path) -> str | None:
    if git_output(root, "rev-parse", "--is-inside-work-tree").strip() != "true":
        return None
    files = {}
    listing = run_command(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], root)
    if listing["exit_code"] != 0:
        return None
    names = listing["stdout"]
    try:
        for name in sorted(set(names.split("\0")) - {""}):
            relative = Path(name)
            if any(part in GENERATED_PARTS for part in relative.parts):
                continue
            path = root / relative
            if path.is_symlink():
                files[name] = {"symlink_sha256": hashlib.sha256(str(path.readlink()).encode()).hexdigest()}
            elif not path.resolve().is_relative_to(root):
                return None
            elif not path.exists():
                files[name] = None
            elif path.is_file():
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1048576), b""):
                        digest.update(block)
                files[name] = {"sha256": digest.hexdigest()}
            else:
                return None
    except OSError:
        return None
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def capture_new_files(root: Path, names: list[str]) -> list[dict]:
    records = []
    for name in sorted(set(names)):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("capture_new_file_unavailable")
        with path.open("rb") as stream:
            raw = stream.read(CAPTURE_FILE_MAX_BYTES + 1)
        if len(raw) > CAPTURE_FILE_MAX_BYTES:
            raise ValueError("capture_new_file_too_large")
        records.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                        "content_base64": base64.b64encode(raw).decode("ascii")})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicitly supplied command and capture a Lead Artifact")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--tool", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--test-command-json", help="JSON argv array for an explicitly authorized test command")
    parser.add_argument("--open-loop", action="append", default=[])
    parser.add_argument("--include-new-file", action="append", default=[], help="Explicit relative file to preserve, at most 128 KiB each")
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
    includes = []
    for value in args.include_new_file:
        relative = Path(value)
        if (relative.is_absolute() or ".." in relative.parts or ":" in value or
                any(part in GENERATED_PARTS for part in relative.parts) or relative.as_posix() == "."):
            parser.error("included files must be relative task files inside the workspace")
        includes.append(relative.as_posix())
    before = git_output(root, "rev-parse", "HEAD").strip()
    try:
        process = run_command(command, root)
        tested_snapshot = workspace_snapshot(root) if test_command else None
        test = run_command(test_command, root) if test_command else None
        current_snapshot = workspace_snapshot(root)
    except OSError:
        print("capture_command_unavailable")
        return 1
    diff_base = before or "HEAD"
    evidence = {"process": process, "diff": git_output(root, "diff", "--no-ext-diff", diff_base),
                "commit_before": before, "commit_after": git_output(root, "rev-parse", "HEAD").strip(),
                "workspace_snapshot_sha256": current_snapshot}
    untracked = sorted(name for name in git_output(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
                       if name and not any(part in GENERATED_PARTS for part in Path(name).parts))
    try:
        evidence["new_files"] = capture_new_files(root, includes)
    except (OSError, ValueError):
        print("capture_new_file_failed: no artifact saved; check the explicitly included paths and size limits")
        return 1
    omitted = sorted(set(untracked) - set(includes))
    evidence["capture_complete"] = not omitted and current_snapshot is not None
    evidence["missing_new_file_contents"] = omitted
    open_loops = [*args.open_loop, *("Capture contents of new file before handoff: " + name for name in omitted)]
    if current_snapshot is None:
        open_loops.append("Capture a verifiable workspace snapshot before handoff")
    claims = []
    if test:
        claim = "Test command " + json.dumps(test["command"]) + " passed with exit code 0"
        stable = tested_snapshot is not None and tested_snapshot == current_snapshot
        evidence["test_run"] = {**test, "kind": "test", "claim": claim, "expected_exit_code": 0,
                                "snapshot_sha256": tested_snapshot, "snapshot_unchanged": stable}
        supported = test["exit_code"] == 0 and stable and bool(test["stdout"].strip() or test["stderr"].strip())
        status = "contradicted" if test["exit_code"] != 0 else "verified" if supported else "unverified"
        claims.append({"claim": claim, "verification_status": status,
                       "evidence_ref": "test_run"})
    files = sorted(set(filter(None, git_output(root, "diff", "--name-only", "-z", diff_base).split("\0"))) | set(untracked))
    artifact = {"schema_version": "lead-artifact.v1", "run_id": "capture-" + uuid.uuid4().hex,
                "tool": args.tool, "task": args.task,
                "timestamp": datetime.now(timezone.utc).isoformat(), "claims": claims,
                "decisions": [], "files_touched": files, "open_loops": open_loops,
                "contradictions": [], "human_approval_items": [],
                "verification_status": "partial" if open_loops else "unverified", "evidence": evidence}
    destination = root / ".yare" / "captures"
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / (artifact["run_id"] + ".json")
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print("artifact: " + output.relative_to(root).as_posix())
    if not evidence["capture_complete"]:
        print("capture_incomplete: source contents or snapshot evidence are missing; see open_loops")
    return test["exit_code"] if test and test["exit_code"] else process["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
