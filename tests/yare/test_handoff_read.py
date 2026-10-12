import hashlib
from copy import deepcopy

import pytest

from cli import storage


def saved_row():
    state = {"what_changed": ["task.py"], "next_clean_action": "Review"}
    source = "print('task')\n"
    packet = {"task": "task", "current_state": state, "artifacts": [
        {"run_id": "run-a", "evidence": {"source_code": source,
         "source_sha256": hashlib.sha256(source.encode()).hexdigest()}}]}
    state_hash = storage._hash_json(packet)
    packet["deterministic_hash"] = state_hash
    receipt = {"run_id": "run-a", "current_state_hash": state_hash}
    receipt_hash = storage._hash_json(receipt)
    receipt["receipt_hash"] = receipt_hash
    return ["run-a", state_hash, state, packet, receipt_hash, receipt]


def test_saved_handoff_verifies_content_and_source():
    result = storage.verify_handoff_record(saved_row())
    assert result["verified"] is True
    assert result["current_state"]["what_changed"] == ["task.py"]


@pytest.mark.parametrize("part", ["state", "packet", "receipt", "source"])
def test_saved_handoff_rejects_tampering(part):
    row = deepcopy(saved_row())
    if part == "state":
        row[2] = {"what_changed": ["other.py"]}
    elif part == "packet":
        row[3]["task"] = "other"
    elif part == "receipt":
        row[5]["run_id"] = "other"
    else:
        row[3]["artifacts"][0]["evidence"]["source_sha256"] = "wrong"
        row[1] = storage._hash_json({k: v for k, v in row[3].items() if k != "deterministic_hash"})
        row[3]["deterministic_hash"] = row[1]
        row[5]["current_state_hash"] = row[1]
        row[4] = storage._hash_json({k: v for k, v in row[5].items() if k != "receipt_hash"})
        row[5]["receipt_hash"] = row[4]
    with pytest.raises(storage.StorageError):
        storage.verify_handoff_record(row)


def test_handoff_requires_a_selector():
    with pytest.raises(storage.StorageError, match="handoff_selector_required"):
        storage.load_handoff(database_url="unused")


def test_missing_receipt_has_a_stable_error_for_v2_packet():
    row = saved_row()
    row[3]["hash_version"] = "work-state.v2"
    row[5] = None
    with pytest.raises(storage.StorageError, match="handoff_receipt_missing"):
        storage.verify_handoff_record(row)
