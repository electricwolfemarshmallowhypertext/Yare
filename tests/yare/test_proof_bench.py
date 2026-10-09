import copy
import io
from pathlib import Path

import pytest

from cli import storage, yare
from scripts import proof_bench as bench


@pytest.fixture
def sample(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(yare, "validate_workspace", lambda root: {"ok": True, "errors": [], "warnings": []})
    monkeypatch.setattr(yare, "_git_state", lambda root: {"available": False})
    artifacts = []
    for name in ("run-codex.jsonl", "run-claude.json", "run-gemini.jsonl"):
        records, warnings = yare._lead_load_artifacts_from_file(root, root / "examples/lead-artifacts" / name)
        assert not warnings
        artifacts.extend(yare._lead_normalize_artifact(raw, source, index)
                         for index, (raw, source) in enumerate(records, 1))
    packet = yare._lead_compile_packet(tmp_path, artifacts, "compile ai work lead state")
    _, receipt = yare._lead_write_receipt(tmp_path, packet, "yare lead compile")
    return packet, receipt


def test_sample_and_sources_pass(sample):
    packet, receipt = sample
    bench.verify_local(packet, receipt)
    bench.verify_sources(Path(__file__).resolve().parents[2], packet)


@pytest.mark.parametrize("mutation", ["state_hash", "receipt_hash", "wrong_state", "truth", "contradiction", "files"])
def test_bad_evidence_fails(sample, mutation):
    packet, receipt = copy.deepcopy(sample)
    if mutation == "state_hash":
        packet["task"] = "tampered"
    elif mutation == "receipt_hash":
        receipt["task"] = "tampered"
    elif mutation == "wrong_state":
        receipt["current_state_hash"] = "other"
        receipt["receipt_hash"] = bench.digest({k: v for k, v in receipt.items() if k != "receipt_hash"})
    else:
        key = {"truth": "what_is_true", "contradiction": "what_contradicts_prior_state", "files": "what_changed"}[mutation]
        packet["current_state"][key] = ["unsupported"]
        packet["deterministic_hash"] = bench.digest({k: v for k, v in packet.items() if k != "deterministic_hash"})
        receipt["current_state_hash"] = packet["deterministic_hash"]
        receipt["receipt_hash"] = bench.digest({k: v for k, v in receipt.items() if k != "receipt_hash"})
    with pytest.raises(bench.BenchFailure):
        bench.verify_local(packet, receipt)


def test_repeatability_rejects_changed_state_and_reused_receipt(sample):
    packet, receipt = sample
    for state, previous in (("wrong", "old"), (packet["deterministic_hash"], receipt["receipt_hash"])):
        with pytest.raises(bench.BenchFailure):
            bench.verify_local(packet, receipt, state, previous)
    bench.verify_local(packet, receipt, packet["deterministic_hash"], "older-receipt")


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, statement, params=None):
        assert statement.startswith(("SELECT", "SHOW CREATE", "EXPLAIN SELECT"))
        self.current = next(self.rows)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current


class Connection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self):
        return Cursor(self.rows)


@pytest.mark.parametrize("bad_row", [None, 0, 1, 2, 3, 4, 5, 6, 7])
def test_database_read_back_checks_every_table(sample, bad_row):
    packet, receipt = sample
    rows = [(packet, list(reversed(storage._artifact_rows(packet["artifacts"])))), (packet["current_state"], packet), (receipt,),
            [(a["source_artifact"], bench.digest(a), a) for a in packet["artifacts"]],
            [(v["section_name"], v["source_text"]) for v in storage.memory_vector_rows(packet)],
            ("yare_memory_vectors", "VECTOR INDEX yare_memory_vectors_embedding_idx (embedding vector_cosine_ops)"),
            [("vector search: yare_memory_vectors@yare_memory_vectors_embedding_idx",)],
            [("human approval items", "Review release", packet["deterministic_hash"], 0.5)]]
    if bad_row is not None:
        rows[bad_row] = [] if bad_row in (3, 4, 6, 7) else None
        with pytest.raises(bench.BenchFailure):
            bench.verify_database(packet, receipt, lambda: Connection(rows))
    else:
        bench.verify_database(packet, receipt, lambda: Connection(rows))


@pytest.mark.parametrize("bad_object", [None, "current-state.json", "current-state.md", "receipt.jsonl"])
def test_s3_compares_object_bodies_not_just_presence(sample, tmp_path, bad_object):
    packet, _ = sample
    paths = [tmp_path / name for name in ("current-state.json", "current-state.md", "receipt.jsonl")]
    for path in paths:
        path.write_bytes(path.name.encode())

    class Client:
        def get_object(self, Bucket, Key):
            assert Bucket == "fixture-bucket"
            name = Key.rsplit("/", 1)[1]
            assert Key.startswith(f"yare/current-states/{packet['deterministic_hash']}/")
            return {"Body": io.BytesIO(b"tampered" if name == bad_object else name.encode())}

    if bad_object:
        with pytest.raises(bench.BenchFailure):
            bench.verify_archive(packet, paths, "fixture-bucket", None, Client())
    else:
        bench.verify_archive(packet, paths, "fixture-bucket", None, Client())
