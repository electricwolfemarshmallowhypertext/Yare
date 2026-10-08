import copy
import hashlib
import os
import uuid

import pytest

from cli import storage
from producers.handoff import load_handoff


@pytest.mark.skipif(not os.environ.get("YARE_TEST_DATABASE_URL"), reason="explicit live test URL required")
def test_live_snapshot_history_and_search():
    import psycopg

    url = os.environ["YARE_TEST_DATABASE_URL"]
    run_id = "integrity-check-" + uuid.uuid4().hex
    task = run_id
    storage.init_schema(database_url=url)
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT compiled_state_json FROM yare_runs WHERE run_id = %s",
                        ("nebius-boundary-20261007-b",))
            template = cur.fetchone()[0]
    packets = []
    try:
        for version in (1, 2):
            packet = copy.deepcopy(template)
            packet["task"] = task
            packet["proof"]["run_id"] = run_id
            assert storage._run_id(packet) == run_id
            packet["current_state"]["what_is_unverified"] = [f"Review version {version}"]
            for artifact in packet["artifacts"]:
                artifact["run_id"] = run_id
                artifact["task"] = task
                source = artifact["evidence"]["source_code"] + f"\n# Snapshot {version}\n"
                artifact["evidence"]["source_code"] = source
                artifact["evidence"]["source_sha256"] = hashlib.sha256(source.encode()).hexdigest()
            packet.pop("deterministic_hash", None)
            packet["deterministic_hash"] = storage._hash_json(packet)
            receipt = {"run_id": run_id, "current_state_hash": packet["deterministic_hash"],
                       "test_version": version}
            receipt["receipt_hash"] = storage._hash_json(receipt)
            assert storage.persist_lead_compile(packet, packet["artifacts"], receipt, database_url=url)
            packets.append(packet)
        loaded = load_handoff(url, run_id)
        assert loaded["current_state_hash"] == packets[-1]["deterministic_hash"]
        assert loaded["artifact"]["evidence"]["source_code"].endswith("# Snapshot 2\n")
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT packet_json FROM yare_current_states WHERE current_state_hash=%s",
                            (packets[0]["deterministic_hash"],))
                assert cur.fetchone()[0] == packets[0]
        history = storage.memory_timeline(limit=1, task=task, database_url=url)
        assert history[0]["state_hash"] == packets[-1]["deterministic_hash"]
        diff = storage.latest_memory_diff(task=task, database_url=url)
        assert diff["previous_state_hash"] == packets[0]["deterministic_hash"]
        assert diff["latest_state_hash"] == packets[-1]["deterministic_hash"]
        matches = storage.search_memory("what still needs human review?", 3, database_url=url)
        assert matches[0]["section_name"] == "human approval items"
        assert len({(item["section_name"], item["source_text"]) for item in matches}) == len(matches)
    finally:
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM yare_runs WHERE run_id = %s", (run_id,))
