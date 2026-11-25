"""Versioned state identity, separate from full-packet receipt integrity."""
import base64
import hashlib
import json
from pathlib import PurePosixPath

CAPTURE_FILE_MAX_BYTES = 131072


def verify_captured_files(evidence):
    if "new_files" not in evidence:
        return
    records = evidence["new_files"]
    if not isinstance(records, list):
        raise ValueError("capture_file_evidence_invalid")
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("capture_file_evidence_invalid")
        name, content = record.get("path"), record.get("content_base64")
        if (not isinstance(name, str) or not name or not PurePosixPath(name).parts or PurePosixPath(name).is_absolute() or
                any(part in {"..", ".git", ".yare", ".sticky"} for part in PurePosixPath(name).parts) or
                ":" in name or "\\" in name or PurePosixPath(name).as_posix() != name or name in seen or
                not isinstance(content, str) or len(content) > 4 * ((CAPTURE_FILE_MAX_BYTES + 2) // 3)):
            raise ValueError("capture_file_evidence_invalid")
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("capture_file_evidence_invalid") from exc
        if len(raw) > CAPTURE_FILE_MAX_BYTES or hashlib.sha256(raw).hexdigest() != record.get("sha256"):
            raise ValueError("capture_file_hash_mismatch")
        seen.add(name)


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
