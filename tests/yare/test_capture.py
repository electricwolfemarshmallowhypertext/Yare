import json
import shutil
import subprocess
import sys

import pytest

from cli import capture, yare


def test_capture_includes_changes_committed_by_the_command(tmp_path, monkeypatch):
    calls = []
    commits = iter(["before", "after"])

    def git_output(root, *args):
        calls.append(args)
        if args == ("rev-parse", "HEAD"):
            return next(commits)
        if args[:2] == ("diff", "--no-ext-diff"):
            return "+actual change"
        if args[:2] == ("diff", "--name-only"):
            return "task.py\n"
        return ""

    monkeypatch.setattr(capture, "git_output", git_output)
    monkeypatch.setattr(capture, "run_command", lambda command, root: {
        "command": command, "exit_code": 0, "stdout": "done", "stderr": ""})
    monkeypatch.setattr("sys.argv", ["capture", "--root", str(tmp_path),
                                   "--tool", "fixture", "--task", "task", "--", "fixture-command"])
    assert capture.main() == 0
    artifact = json.loads(next((tmp_path / ".yare/captures").glob("*.json")).read_text())
    assert artifact["evidence"]["commit_before"] == "before"
    assert artifact["evidence"]["commit_after"] == "after"
    assert artifact["evidence"]["diff"] == "+actual change"
    assert artifact["files_touched"] == ["task.py"]
    assert ("diff", "--no-ext-diff", "before") in calls
    assert ("diff", "--name-only", "before") in calls


@pytest.mark.parametrize("fixed,expected_exit", [(True, 0), (False, 1)])
def test_capture_records_real_command_tests_and_compile_evidence(tmp_path, monkeypatch, fixed, expected_exit):
    if not shutil.which("git"):
        pytest.skip("Git is required for the isolated capture integration")
    empty = tmp_path / "empty-git-template"
    empty.mkdir()
    def git(*args):
        subprocess.run(["git", "-c", "core.hooksPath=" + str(empty),
                        "-c", "user.name=Capture Fixture", "-c", "user.email=fixture@example.invalid",
                        *args], cwd=tmp_path, check=True, capture_output=True)
    git("init", "--template=" + str(empty))
    (tmp_path / "task.py").write_text("def add(a, b):\n    return a\n")
    (tmp_path / "test_task.py").write_text(
        "import unittest\nfrom task import add\n"
        "class TaskTests(unittest.TestCase):\n"
        "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n")
    git("add", "task.py", "test_task.py")
    git("commit", "-m", "Initial fixture")
    test_command = [sys.executable, "-m", "unittest", "-v", "test_task"]
    source = "def add(a, b):\n    return a + b\n" if fixed else "def add(a, b):\n    return b\n"
    command = [sys.executable, "-c", "from pathlib import Path; Path('task.py').write_text(" + repr(source) + ")"]
    monkeypatch.setattr(sys, "argv", ["capture", "--root", str(tmp_path), "--tool", "local-fixture",
                        "--task", "Fix addition", "--test-command-json", json.dumps(test_command), "--", *command])
    assert capture.main() == expected_exit
    artifact_path = next((tmp_path / ".yare/captures").glob("*.json"))
    artifact = json.loads(artifact_path.read_text())
    evidence = artifact["evidence"]
    assert evidence["process"]["exit_code"] == 0
    assert evidence["test_run"]["exit_code"] == expected_exit
    assert ("OK" if fixed else "FAILED") in evidence["test_run"]["stderr"]
    assert "-    return a" in evidence["diff"]
    assert "task.py" in artifact["files_touched"]
    normalized = yare._lead_normalize_artifact(artifact, "captured.json", 1)
    monkeypatch.setattr(yare, "validate_workspace", lambda root: {"ok": True, "errors": [], "warnings": []})
    packet = yare._lead_compile_packet(tmp_path, [normalized], "Fix addition")
    claims = packet["current_state"]["what_is_true"] if fixed else packet["current_state"]["what_is_unverified"]
    assert any("Test command" in claim for claim in claims)
    if not fixed:
        assert packet["current_state"]["what_is_true"] == []
