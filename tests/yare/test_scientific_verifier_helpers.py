import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts import verify_scientific_review_bundle as verifier


def write_manifest(root):
    files = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in root.rglob("*") if path.is_file() and path.name != "manifest.json"}
    (root / "manifest.json").write_text(json.dumps({"files": files}))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    offline = tmp_path / "offline"
    offline.mkdir()
    files = {"verify.py": b"def verify(*args): pass\n", "analysis.py": b"value = 1\n"}
    archive = tmp_path / "original-offline-bundle.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, raw in files.items():
            zipped.writestr(name, raw)
            (offline / name).write_bytes(raw)
    shared = tmp_path / "shared_verifier.py"
    shared.write_bytes(b"value = 2\n")
    monkeypatch.setattr(verifier, "OFFLINE_HASH", verifier.sha(archive.read_bytes()))
    monkeypatch.setattr(verifier, "SHARED_VERIFIER_HASH", verifier.sha(shared.read_bytes()))
    write_manifest(tmp_path)
    return tmp_path


def test_helpers_match_trusted_bytes_without_execution(bundle, monkeypatch):
    monkeypatch.setattr(verifier.runpy, "run_path", lambda *args: pytest.fail("Helper must not run during authentication"))
    verifier.verify_helper_sources(bundle)


@pytest.mark.parametrize("name", ["offline/verify.py", "offline/analysis.py", "shared_verifier.py"])
@pytest.mark.parametrize("reproduce", [False, True])
def test_modified_helper_rejected_before_execution_even_with_updated_manifest(bundle, monkeypatch, name, reproduce):
    original_archive = (bundle / "original-offline-bundle.zip").read_bytes()
    (bundle / name).write_text("raise RuntimeError('Untrusted helper executed')\n")
    write_manifest(bundle)
    monkeypatch.setattr(verifier.runpy, "run_path", lambda *args: pytest.fail("Untrusted helper executed"))
    with pytest.raises(ValueError, match="pinned archive|Untrusted shared verifier"):
        verifier.verify(bundle, reproduce)
    assert (bundle / "original-offline-bundle.zip").read_bytes() == original_archive


def test_original_archive_must_match_trusted_digest(bundle):
    archive = bundle / "original-offline-bundle.zip"
    archive.write_bytes(archive.read_bytes() + b"modified")
    with pytest.raises(ValueError, match="Original offline bundle changed"):
        verifier.verify_helper_sources(bundle)


def test_shared_verifier_pin_matches_reviewed_source():
    source = Path(__file__).resolve().parents[2] / "scripts/verify_scientific_bundle.py"
    assert verifier.sha(source.read_bytes()) == verifier.SHARED_VERIFIER_HASH
