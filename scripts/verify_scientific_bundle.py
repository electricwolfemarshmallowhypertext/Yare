"""Independent, standard-library verification of the offline evidence bundle."""

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def reject(value):
        raise ValueError("Nonfinite JSON: " + value)
    return json.loads(path.read_bytes().decode("utf-8"), parse_constant=reject)


def state_hash(packet):
    require(packet.get("hash_version") == "work-state.v2", "Unexpected state identity version")
    excluded = {"source_artifact", "git_state", "context_bundle_hash", "receipt_hash", "source_artifacts"}
    artifacts = [{key: value for key, value in artifact.items() if key not in excluded}
                 for artifact in packet["artifacts"]]
    return digest({"hash_version": "work-state.v2", "task": packet["task"],
                   "current_state": packet["current_state"], "artifacts": sorted(artifacts, key=digest)})


def verify_science(root, science, expected_execution="scripted_fixture", decision=None):
    require(science["version"] == "scientific-evidence.v1" and science["execution"] == expected_execution,
            "Execution provenance differs")
    require(science["brief_sha256"] == sha((root / "brief.md").read_bytes()), "Brief differs")
    rows_by_id, selected = {}, {}
    require({dataset["id"] for dataset in science["datasets"]} == {"ztf", "gaia"}, "Unexpected datasets")
    for dataset in science["datasets"]:
        path = root / "data" / ("ztf.json" if dataset["id"] == "ztf" else "gaia.csv")
        raw = path.read_bytes()
        require(raw == dataset["content_utf8"].encode("utf-8") and sha(raw) == dataset["sha256"], "Dataset changed")
        if dataset["media_type"] == "application/json":
            rows = read_json(path)
            for key in dataset["row_selector"]:
                rows = rows[key]
        else:
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        indices = [item["index"] for item in dataset["selected_rows"]]
        require(len(indices) == len(set(indices)), "Duplicate selected row")
        for item in dataset["selected_rows"]:
            require(0 <= item["index"] < len(rows) and digest(rows[item["index"]]) == item["sha256"], "Row differs")
        rows_by_id[dataset["id"]], selected[dataset["id"]] = rows, set(indices)
    require(len(science["observations"]) == 100, "Observation loss")
    for observation in science["observations"]:
        require(observation["row_index"] in selected[observation["dataset_id"]], "Observation not selected")
        row = rows_by_id[observation["dataset_id"]][observation["row_index"]]
        for column, value in (("value_column", "value"), ("uncertainty_column", "uncertainty"), ("time_column", "time_value")):
            require(math.isfinite(observation[value]) and float(row[observation[column]]) == observation[value], "Measurement differs")
        require(observation["uncertainty"] > 0 and observation["unit"] == "mag" and
                observation["time_format"] == "MJD" and observation["time_scale"] == "unverified", "Observation metadata differs")
    analysis = science["analysis"]
    require(analysis["source_code"].encode("utf-8") == (root / "analysis.py").read_bytes(), "Analysis source differs")
    require(sha(analysis["source_code"].encode()) == analysis["sha256"], "Analysis source hash differs")
    require(digest(analysis["results"]) == analysis["results_sha256"], "Analysis results hash differs")
    require(sorted(analysis["parameters"]["ztf_rows"]) == sorted(item["row_index"] for item in science["observations"]),
            "Analysis selection differs")
    require(all(item["status"] in ("unverified", "disputed") for item in science["hypotheses"]), "Hypothesis overstated")
    require(all(item["status"] == "open" for item in science["questions"]), "Question silently closed")
    if science["stage"] == "D":
        review = science["human_review"]
        require(review is not None and review["parent_receipt_hash"] == science["parent"]["receipt_hash"], "Review binding differs")
        require(digest({key: value for key, value in review.items() if key != "record_sha256"}) == review["record_sha256"],
                "Review hash differs")
        decision = decision or read_json(root / "checkpoint.json")["operator_decision"]
        require(review["decision"] == decision["decision"] and review["note"] == decision["note"], "Review decision differs")
    else:
        require(science["human_review"] is None, "Unexpected early review")


def verify_parent(science, parent, human_transition=False):
    previous, identity = parent
    require(science["parent"] == identity, "Parent identity differs")
    require("ABCD".index(science["stage"]) == "ABCD".index(previous["stage"]) + 1, "Stage order differs")
    require(science["execution"] == previous["execution"] or
            (human_transition and science["stage"] == "D" and science["execution"] == "human_decision"),
            "Execution provenance changed")
    for key in ("investigation_id", "brief_sha256", "datasets", "analysis", "observations"):
        require(science[key] == previous[key], "Frozen context changed: " + key)
    for key in ("hypotheses", "disagreements", "questions"):
        latest = {item["id"]: item for item in science[key]}
        for old in previous[key]:
            require(old["id"] in latest, "Prior research evidence disappeared")
            new = latest[old["id"]]
            if key == "hypotheses":
                require(old["status"] != "disputed" or new["status"] == "disputed", "Disagreement cleared")
                old, new = ({k: v for k, v in item.items() if k != "status"} for item in (old, new))
            require(old == new, "Prior research evidence changed")


def reproduce(root, science):
    # Only the separately inspectable, hash-pinned bundled program is executed.
    parameters = science["analysis"]["parameters"]
    for key in ("reproduction_relative_tolerance", "reproduction_absolute_tolerance"):
        require(type(parameters[key]) in (int, float) and 0 <= parameters[key] <= 1e-9, "Tolerance invalid")
    with tempfile.TemporaryDirectory(prefix="yare-public-analysis-") as directory:
        path = Path(directory) / "input.json"
        path.write_text(json.dumps({"datasets": {item["id"]: item["content_utf8"] for item in science["datasets"]},
                                   "parameters": parameters}), encoding="utf-8")
        result = subprocess.run([sys.executable, str(root / "analysis.py"), "--input", str(path)],
                                capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, "Bundled analysis failed")
    actual, expected = json.loads(result.stdout), science["analysis"]["results"]
    require(actual.keys() == expected.keys(), "Analysis result fields differ")
    for key, value in expected.items():
        require(math.isclose(actual[key], value, rel_tol=parameters["reproduction_relative_tolerance"],
                             abs_tol=parameters["reproduction_absolute_tolerance"])
                if isinstance(value, (int, float)) else actual[key] == value, "Calculation differs: " + key)


def verify(root, run_analysis=False):
    root = root.resolve()
    manifest = read_json(root / "manifest.json")
    actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    require(actual_files == set(manifest["files"]) | {"manifest.json"}, "Unexpected or missing bundle files")
    for name, expected in manifest["files"].items():
        relative = PurePosixPath(name)
        path = root / name
        require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in name and
                ":" not in name and not path.is_symlink() and path.resolve().is_relative_to(root), "Unsafe bundle path")
        require(path.stat().st_size <= 2 * 1024 * 1024, "Oversized bundle member")
        require(sha(path.read_bytes()) == expected, "Bundle file hash differs: " + name)
    checkpoint = read_json(root / "checkpoint.json")
    fingerprints = checkpoint["source_fingerprints"]
    for name, expected in fingerprints["files"].items():
        require("source/" + name in manifest["files"], "Unlisted implementation file")
        require(sha((root / "source" / name).read_bytes()) == expected, "Implementation fingerprint differs")
    require(digest(fingerprints["files"]) == fingerprints["combined_sha256"], "Source fingerprint aggregate differs")
    parents, records, links = {}, 0, 0
    require(len(checkpoint["stages"]) == 12, "Unexpected record count")
    for expected in checkpoint["stages"]:
        repetition = expected["run_id"].split("-")[-2]
        name = "records/" + repetition + "/" + expected["stage"].lower() + ".json"
        require(name in manifest["files"], "Unlisted evidence record")
        export = read_json(root / name)
        require(export["mode"] == "offline_export", "Storage mode overstated")
        packet, receipt = export["packet"], export["receipt"]
        require(state_hash(packet) == packet["deterministic_hash"] == expected["state_hash"], "State hash differs")
        require(receipt["receipt_hash"] == expected["receipt_hash"] ==
                digest({key: value for key, value in receipt.items() if key != "receipt_hash"}), "Receipt hash differs")
        require(receipt["run_id"] == expected["run_id"] and receipt["current_state_hash"] == expected["state_hash"], "Record association differs")
        require(receipt["packet_snapshot"] == packet and receipt["packet_hash"] == digest(packet), "Packet receipt binding differs")
        science = packet["artifacts"][0]["evidence"]["scientific"]
        require(science["stage"] == expected["stage"], "Stage label differs")
        verify_science(root, science)
        if repetition in parents:
            verify_parent(science, parents[repetition])
            links += 1
        else:
            require(science["stage"] == "A" and science["parent"] is None, "Initial parent differs")
        identity = {"run_id": expected["run_id"], "current_state_hash": expected["state_hash"], "receipt_hash": expected["receipt_hash"]}
        parents[repetition] = (science, identity)
        if run_analysis:
            reproduce(root, science)
        records += 1
    require(records == 12 and links == 9 and len(parents) == 3, "Incomplete fixture evaluation")
    print(json.dumps({"status": "PASS", "evidence": "offline_scripted_fixtures", "records": records,
                      "parent_links": links, "calculations_reproduced": records if run_analysis else 0,
                      "live_model_or_cockroach_proof": False, "identity_authenticated": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--reproduce", action="store_true", help="After source review, run bundled analysis.py; never embedded source")
    args = parser.parse_args()
    verify(args.root, args.reproduce)
