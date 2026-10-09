"""Assertions for the sample handoff bench; never calls a model."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from cli import archive, storage, yare


class BenchFailure(ValueError):
    pass


def require(condition, name):
    if not condition:
        raise BenchFailure(name)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_local(packet, receipt, previous_state=None, previous_receipt=None):
    state_hash = packet.get("deterministic_hash")
    require(state_hash == digest({k: v for k, v in packet.items() if k != "deterministic_hash"}),
            "state hash mismatch")
    require(receipt.get("receipt_hash") == digest({k: v for k, v in receipt.items() if k != "receipt_hash"}),
            "receipt hash mismatch")
    require(receipt.get("current_state_hash") == state_hash, "receipt names another state")
    require(receipt.get("run_id") == packet["proof"]["run_id"], "receipt names another run")
    require(packet["validation"]["ok"] is True, "workspace validation failed")
    require(packet["artifacts_ingested"] == 3 and len(packet["artifacts"]) == 3, "expected three artifacts")
    state = packet["current_state"]
    require(set(state["what_changed"]) == {
        "README.md", "cli/yare.py", "apps/api/src/memory/server.py",
        "examples/lead-artifacts/run-gemini.jsonl"}, "changed files differ from samples")
    require(state["what_is_true"] == [], "unsupported sample claims became true")
    require(set(state["what_is_unverified"]) == {
        "Receipt includes git dirty status", "All receipt tests passed in CI",
        "Endpoint returns latest receipt", "README includes Yare handoff section"},
        "unverified sample claims differ")
    require(state["what_contradicts_prior_state"] == ["Receipt includes git dirty status"],
            "sample contradiction missing or changed")
    require(set(state["what_needs_human_approval"]) == {
        "Approve endpoint release gate exception", "Hold release until endpoint smoke test exists",
        'Resolve contradiction: Receipt includes git dirty status'}, "approval items differ")
    require({item["text"] for item in state["open_loops"]} == {
        "Add integration coverage for lead compile", "Confirm rollback procedure with ops",
        "Validate demo command on fresh clone"}, "open loops differ")
    require(state["next_clean_action"] == "Resolve human-approval items before the next run.",
            "next action differs")
    if previous_state is not None:
        require(state_hash == previous_state, "identical compiles changed state hash")
        require(receipt["receipt_hash"] != previous_receipt, "repeat compile reused receipt")


def verify_sources(root, packet):
    loaded = []
    for name in ("run-codex.jsonl", "run-claude.json", "run-gemini.jsonl"):
        path = root / "examples" / "lead-artifacts" / name
        records, warnings = yare._lead_load_artifacts_from_file(root, path)
        require(not warnings, "sample input load warning")
        for index, (record, source) in enumerate(records, 1):
            loaded.append(yare._lead_normalize_artifact(record, source, index))
    require(sorted(loaded, key=lambda a: a["run_id"]) ==
            sorted(packet["artifacts"], key=lambda a: a["run_id"]), "compiled sources differ from files")


def verify_database(packet, receipt, connect):
    run_id = packet["proof"]["run_id"]
    state_hash = packet["deterministic_hash"]
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT compiled_state_json, source_artifact_hashes FROM yare_runs WHERE run_id = %s",
                           (run_id,))
            run = cursor.fetchone()
            require(run is not None and run[0] == packet, "Cockroach run packet read-back mismatch")
            expected_hashes = storage._artifact_rows(packet["artifacts"])
            require(sorted(run[1], key=lambda item: item["source_artifact"]) ==
                    sorted(expected_hashes, key=lambda item: item["source_artifact"]),
                    "Cockroach source hashes read-back mismatch")
            cursor.execute("SELECT state_json, packet_json FROM yare_current_states WHERE current_state_hash = %s",
                           (state_hash,))
            require(cursor.fetchone() == (packet["current_state"], packet), "Cockroach state read-back mismatch")
            cursor.execute("SELECT receipt_json FROM yare_receipts WHERE receipt_hash = %s", (receipt["receipt_hash"],))
            require(cursor.fetchone() == (receipt,), "Cockroach receipt read-back mismatch")
            cursor.execute("SELECT source_artifact, artifact_hash, artifact_json FROM yare_lead_artifacts WHERE run_id = %s",
                           (run_id,))
            expected = sorted((a["source_artifact"], digest(a), a) for a in packet["artifacts"])
            require(sorted(cursor.fetchall(), key=lambda row: row[0]) == expected,
                    "Cockroach artifact read-back mismatch")
            cursor.execute("SELECT section_name, source_text FROM yare_memory_vectors WHERE current_state_hash = %s",
                           (state_hash,))
            expected_vectors = sorted((v["section_name"], v["source_text"]) for v in storage.memory_vector_rows(packet))
            require(sorted(cursor.fetchall()) == expected_vectors, "Cockroach vector section read-back mismatch")
            cursor.execute("SHOW CREATE TABLE yare_memory_vectors")
            schema = cursor.fetchone()
            require(schema is not None and "VECTOR INDEX yare_memory_vectors_embedding_idx" in schema[1],
                    "Cockroach vector index missing")
            vector = storage._vector_literal(storage.embed_text("what still needs human review?"))
            query = ("SELECT section_name, source_text, current_state_hash, embedding <=> %s::VECTOR AS distance "
                     "FROM yare_memory_vectors ORDER BY embedding <=> %s::VECTOR LIMIT 3")
            cursor.execute("EXPLAIN " + query, (vector, vector))
            plan = "\n".join(str(row[0]) for row in cursor.fetchall())
            require("vector search" in plan and "yare_memory_vectors_embedding_idx" in plan,
                    "Cockroach nearest-neighbor query did not use vector index")
            cursor.execute(query, (vector, vector))
            matches = cursor.fetchall()
            require(0 < len(matches) <= 3 and all(row[0] and row[1] and row[2] and math.isfinite(float(row[3]))
                                                for row in matches), "Cockroach vector query returned invalid matches")


def verify_archive(packet, paths, bucket, prefix, client):
    base = f"{archive._prefix(prefix)}current-states/{packet['deterministic_hash']}"
    for name, path in zip(("current-state.json", "current-state.md", "receipt.jsonl"), paths):
        body = client.get_object(Bucket=bucket, Key=f"{base}/{name}")["Body"]
        try:
            require(body.read() == path.read_bytes(), f"S3 {name} read-back mismatch")
        finally:
            body.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--previous-state")
    parser.add_argument("--previous-receipt")
    args = parser.parse_args()
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        verify_local(packet, receipt, args.previous_state, args.previous_receipt)
        verify_sources(Path.cwd(), packet)
        print("assertions: PASS (sample state, source inputs, state hash, receipt integrity)")
        if args.previous_state:
            print("repeatability: PASS (same state hash, distinct timestamped receipt)")
        url = os.environ.get("YARE_DATABASE_URL")
        if url:
            verify_database(packet, receipt, lambda: storage._connect(url))
            print("cockroach_read_back: PASS (run, packet, artifacts, receipt, vector sections)")
            print("vector_query: PASS (index exists, plan uses index, nearest-neighbor query returns rows)")
        else:
            print("cockroach_read_back: SKIPPED (not configured)")
        bucket = os.environ.get("YARE_S3_BUCKET")
        if bucket:
            verify_archive(packet, (args.packet, args.markdown, args.receipt), bucket,
                           os.environ.get("YARE_S3_PREFIX"), archive._client())
            print("s3_read_back: PASS (all three object bodies match local bytes)")
        else:
            print("s3_read_back: SKIPPED (not configured)")
        print("mcp_clients: NOT RUN (separate client sessions required)")
    except BenchFailure as error:
        print(f"assertions: FAIL ({error})")
        return 1
    except Exception:
        # Provider exceptions may contain connection URLs or credential metadata.
        print("assertions: FAIL (input or configured service check failed; credentials omitted)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
