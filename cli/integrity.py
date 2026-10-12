"""Versioned state identity, separate from full-packet receipt integrity."""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def state_material(packet):
    if packet.get("hash_version") != "work-state.v2":
        return {key: value for key, value in packet.items() if key != "deterministic_hash"}
    excluded = {"source_artifact", "git_state", "context_bundle_hash", "receipt_hash", "source_artifacts"}
    artifacts = [{key: value for key, value in artifact.items() if key not in excluded}
                 for artifact in packet["artifacts"]]
    return {"hash_version": "work-state.v2", "task": packet["task"],
            "current_state": packet["current_state"], "artifacts": sorted(artifacts, key=digest)}


def state_hash(packet):
    return digest(state_material(packet))
