import base64
import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from cli import capture, integrity, storage, yare


@pytest.fixture
def repository(tmp_path):
    if not shutil.which("git"):
        pytest.skip("Git is required for capture fixtures")
    def git(*args):
        subprocess.run(["git", "-c", "core.hooksPath=", "-c", "commit.gpgsign=false",
                        "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
                       cwd=tmp_path, check=True, capture_output=True)
    git("init", "--template=")
    (tmp_path / "tracked.py").write_text("value = 1\n")
    git("add", "tracked.py")
    git("commit", "-m", "Fixture")
    return tmp_path


def run_capture(root, monkeypatch, includes=(), content=b"value = 2\n"):
    command = [sys.executable, "-c", "from pathlib import Path; Path('new task.py').write_bytes(" + repr(content) + ")"]
    argv = ["capture", "--root", str(root), "--tool", "fixture", "--task", "new task"]
    for name in includes:
        argv += ["--include-new-file", name]
    argv += ["--test-command-json", json.dumps([sys.executable, "-c", "print('OK')"]), "--", *command]
    monkeypatch.setattr(sys, "argv", argv)
    return capture.main()


def compile_capture(root, monkeypatch):
    monkeypatch.setattr(yare, "validate_workspace", lambda root: {"ok": True, "errors": [], "warnings": []})
    monkeypatch.setattr(yare.storage_backend, "persist_lead_compile", lambda **kwargs: False)
    monkeypatch.setattr(yare.archive_backend, "archive_lead_compile", lambda **kwargs: [])
    path = next((root / ".yare/captures").glob("*.json"))
    packet, _, _, _, receipt, _ = yare.compile_lead_state(root, None, [path])
    row = [receipt["run_id"], packet["deterministic_hash"], packet["current_state"], packet,
           receipt["receipt_hash"], receipt]
    return storage.verify_handoff_record(row)


@pytest.mark.parametrize("content", [b"value = 2\n", bytes(range(256))])
def test_explicit_new_file_survives_compile_and_verified_reload(repository, monkeypatch, content):
    assert run_capture(repository, monkeypatch, ["new task.py"], content) == 0
    stored = compile_capture(repository, monkeypatch)
    evidence = stored["artifacts"][0]["evidence"]
    record = evidence["new_files"][0]
    assert record["path"] == "new task.py"
    assert base64.b64decode(record["content_base64"]) == content
    assert record["sha256"] == hashlib.sha256(content).hexdigest()
    assert evidence["capture_complete"] is True
    assert evidence["missing_new_file_contents"] == []


def test_omitted_new_file_is_explicitly_incomplete(repository, monkeypatch, capsys):
    assert run_capture(repository, monkeypatch) == 0
    assert "capture_incomplete" in capsys.readouterr().out
    stored = compile_capture(repository, monkeypatch)
    evidence = stored["artifacts"][0]["evidence"]
    assert evidence["capture_complete"] is False
    assert evidence["missing_new_file_contents"] == ["new task.py"]
    assert evidence["new_files"] == []
    state = stored["current_state"]
    assert any("new task.py" in item["text"] for item in state["open_loops"])
    assert state["next_clean_action"] != "Proceed to the next scoped task."


def test_unknown_snapshot_cannot_be_labeled_complete(repository, monkeypatch):
    monkeypatch.setattr(capture, "workspace_snapshot", lambda root: None)
    assert run_capture(repository, monkeypatch, ["new task.py"]) == 0
    artifact = json.loads(next((repository / ".yare/captures").glob("*.json")).read_text())
    assert artifact["evidence"]["capture_complete"] is False
    assert "Capture a verifiable workspace snapshot before handoff" in artifact["open_loops"]
    assert artifact["claims"][0]["verification_status"] == "unverified"


def test_oversized_new_file_is_not_silently_omitted(repository, monkeypatch):
    assert run_capture(repository, monkeypatch, ["new task.py"], b"x" * (integrity.CAPTURE_FILE_MAX_BYTES + 1)) == 1
    assert not (repository / ".yare/captures").exists()


@pytest.mark.parametrize("name", ["../outside.py", ".git/config"])
def test_forbidden_include_is_rejected_before_running_command(repository, monkeypatch, name):
    monkeypatch.setattr(capture, "run_command", lambda *args: pytest.fail("Forbidden include launched a command"))
    with pytest.raises(SystemExit) as exc:
        run_capture(repository, monkeypatch, [name])
    assert exc.value.code == 2


@pytest.mark.parametrize("change", ["bytes", "hash", "path", "encoding"])
def test_bad_new_file_evidence_rejected(change):
    record = {"path": "task.py", "content_base64": base64.b64encode(b"source").decode(),
              "sha256": hashlib.sha256(b"source").hexdigest()}
    if change == "bytes":
        record["content_base64"] = base64.b64encode(b"different").decode()
    elif change == "hash":
        record["sha256"] = "wrong"
    elif change == "path":
        record["path"] = "../outside.py"
    else:
        record["content_base64"] = "not base64!"
    with pytest.raises(ValueError, match="capture_file_"):
        integrity.verify_captured_files({"new_files": [record]})


def test_loader_rejects_new_file_hash_mismatch_after_outer_rehash(repository, monkeypatch):
    assert run_capture(repository, monkeypatch, ["new task.py"]) == 0
    stored = compile_capture(repository, monkeypatch)
    packet = stored["receipt"]["packet_snapshot"]
    packet["artifacts"][0]["evidence"]["new_files"][0]["sha256"] = "wrong"
    state_hash = integrity.state_hash(packet)
    packet["deterministic_hash"] = state_hash
    receipt = stored["receipt"]
    receipt.update(packet_snapshot=packet, packet_hash=integrity.digest(packet), current_state_hash=state_hash)
    receipt["receipt_hash"] = integrity.digest({key: value for key, value in receipt.items() if key != "receipt_hash"})
    with pytest.raises(storage.StorageError, match="capture_file_hash_mismatch"):
        storage.verify_handoff_record([stored["run_id"], state_hash, packet["current_state"], packet, receipt["receipt_hash"], receipt])
