"""Standard-library verification of original offline and captured live/human evidence."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import runpy


DECISION = ("Defer source classification. Retain the duplicated hypotheses, disputed unit statements, "
            "unresolved Gaia associations and unsupported trend claim. Request diagnostic follow-up only.")
MODEL = "qwen3:4b"
MODEL_HASH = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
OFFLINE_HASH = "ae452a1e3da5a0ca9fb244aecf02f999b8be9bbc90fbaee2c5f9d9247a5ab5c1"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    def reject(value):
        raise ValueError("Nonfinite JSON")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def verify_trace(evidence, science):
    trace = evidence["local_model"]
    require(trace["provider"] == "ollama-local" and trace["endpoint"] == "http://127.0.0.1:11435" and
            trace["model_digest"] == MODEL_HASH and trace["stage"] == science["stage"] and
            trace["brief_sha256"] == science["brief_sha256"] and trace["parent"] == science["parent"] and
            len(trace["calls"]) == 2, "Model origin differs")
    for index, call in enumerate(trace["calls"]):
        response = json.loads(call["response_utf8"])
        request = call["request"]
        require(digest(request) == call["request_sha256"] and sha(call["response_utf8"].encode()) == call["response_sha256"],
                "Provider transcript hash differs")
        require(request["model"] == response["model"] == MODEL and request["stream"] is False and
                request["think"] is False and request["options"]["num_predict"] == 2048 and
                request["options"]["num_ctx"] == 8192 and response["done"] is True and
                response["done_reason"] == "stop" and 0 < response["eval_count"] <= 2048, "Model request/finish differs")
        action = json.loads(response["message"]["content"])
        if index == 0:
            require(action == {"action": "analyze"}, "Model supplied an invalid action or stdout")
        else:
            require(set(action) == {"action", "reasoning"} and action["action"] == "emit", "Final action differs")
            for name in ("hypotheses", "disagreements", "questions"):
                by_id = {item["id"]: item for item in science[name]}
                for item in action["reasoning"][name]:
                    require(item["id"] in by_id, "Model output missing from saved state")
                    original, recorded = dict(item), dict(by_id[item["id"]])
                    if name == "hypotheses":
                        require(original["status"] in ("unverified", "disputed") and recorded["status"] in
                                ("unverified", "disputed"), "Scientific claim promoted")
                        original.pop("status")
                        recorded.pop("status")
                    require(original == recorded, "Model wording changed")
    tool = trace["analysis_tool"]
    require(tool["exit_code"] == 0 and json.loads(tool["stdout"]) == science["analysis"]["results"], "Tool result differs")
    require(trace["calls"][1]["request"]["messages"][-1]["content"] == json.dumps({"analysis_tool": tool}, sort_keys=True),
            "Actual tool feedback missing")
    return trace["session_id"]


def verify_review(evidence, science, parent, reference):
    review = evidence["scientific_review"]
    require("local_model" not in evidence and science["execution"] == "human_decision", "D mislabeled as model execution")
    require(review["review_sha256"] == science["human_review"]["record_sha256"] and review["parent"] == science["parent"] and
            review["work_state_continuity"] == "PASSED" and review["scientific_reasoning_acceptance"] == "FAILED" and
            review["source_classification"] == "deferred" and review["original_evidence_retained"] is True and
            review["observing_or_paid_actions_authorized"] is False and review["diagnostic_only"] is True and
            review["unit_reference"] == reference, "Human review findings differ")
    for key in ("datasets", "analysis", "observations", "hypotheses", "disagreements", "questions"):
        require(science[key] == parent[key], "Human D changed original research evidence")
    groups = {}
    for item in science["hypotheses"]:
        groups.setdefault(" ".join(item["statement"].lower().split()), []).append(item["id"])
    require(review["duplicate_hypothesis_groups"] == [ids for ids in groups.values() if len(ids) > 1], "Duplicate annotations differ")
    import re
    statements = [(item["id"], item["statement"]) for item in science["hypotheses"]]
    statements += [(item["id"], item["reason"]) for item in science["disagreements"]]
    require(review["unit_error_statement_ids"] == [identifier for identifier, text in statements
                if re.search(r"(?:ra_error|dec_error).{0,30}" + chr(176), text)], "Unit-error annotations differ")
    require(review["unsupported_trend_hypothesis_ids"] == [item["id"] for item in science["hypotheses"]
                if "steady decline" in item["statement"].lower()], "Trend annotation differs")
    require(all(item["diagnostic_only"] is True and item["review_sha256"] == review["review_sha256"]
                for item in evidence["followup_recommendations"]), "Follow-up exceeds decision")


def verify(root, reproduce=False):
    root = root.resolve()
    manifest = read(root / "manifest.json")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    require(actual == set(manifest["files"]) | {"manifest.json"}, "Bundle file set differs")
    for name, expected in manifest["files"].items():
        path, relative = root / name, PurePosixPath(name)
        require(not relative.is_absolute() and ".." not in relative.parts and ":" not in name and "\\" not in name and
                not path.is_symlink() and path.resolve().is_relative_to(root) and path.stat().st_size <= 2 * 1024 * 1024,
                "Unsafe bundle path")
        require(sha(path.read_bytes()) == expected, "Member hash differs: " + name)
    require(sha((root / "original-offline-bundle.zip").read_bytes()) == OFFLINE_HASH, "Original offline bundle changed")
    frozen = runpy.run_path(str(root / "offline/verify.py"))
    frozen["verify"](root / "offline", reproduce)
    shared = runpy.run_path(str(root / "shared_verifier.py"))
    checkpoint = read(root / "live/checkpoint.json")
    require(len(checkpoint["stages"]) == 12, "Incomplete live/human sequence")
    reference = read(root / "live/unit-reference/units.json")
    raw = (root / "live/unit-reference/gaia-source.html").read_bytes()
    require(sha(raw) == reference["document_sha256"] and sha(reference["excerpt"].encode()) == reference["excerpt_sha256"] and
            reference["units"] == {"ra_error": "mas", "dec_error": "mas"}, "Unit reference changed")
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, value):
            self.parts.append(value)
    parsed = Text()
    parsed.feed(raw.decode("utf-8"))
    text = " ".join(" ".join(parsed.parts).split())
    require(all(line in text for line in reference["excerpt"].splitlines()), "Unit excerpt absent from official document")
    parents, links, sessions = {}, 0, set()
    for expected in checkpoint["stages"]:
        export = read(root / expected["path"])
        packet, receipt = export["packet"], export["receipt"]
        require(export["mode"] == "cockroach_record" and shared["state_hash"](packet) == packet["deterministic_hash"] == expected["state_hash"],
                "Live state identity differs")
        require(receipt["receipt_hash"] == expected["receipt_hash"] == digest({k: v for k, v in receipt.items() if k != "receipt_hash"}) and
                receipt["run_id"] == expected["run_id"] and receipt["current_state_hash"] == expected["state_hash"] and
                receipt["packet_snapshot"] == packet and receipt["packet_hash"] == digest(packet), "Live receipt binding differs")
        evidence = packet["artifacts"][0]["evidence"]
        science = evidence["scientific"]
        mode = "human_decision" if expected["stage"] == "D" else "live_model"
        shared["verify_science"](root / "offline", science, mode, {"decision": "request_followup", "note": DECISION})
        repetition = science["investigation_id"]
        require(science["stage"] == expected["stage"], "Stage differs")
        if repetition in parents:
            shared["verify_parent"](science, parents[repetition], human_transition=True)
            links += 1
        else:
            require(science["stage"] == "A" and science["parent"] is None, "Initial identity differs")
        if mode == "live_model":
            sessions.add(verify_trace(evidence, science))
        else:
            verify_review(evidence, science, parents[repetition][0], reference)
        if reproduce:
            shared["reproduce"](root / "offline", science)
        parents[repetition] = (science, {"run_id": expected["run_id"], "current_state_hash": expected["state_hash"],
                                       "receipt_hash": expected["receipt_hash"]})
    require(links == 9 and len(parents) == 3 and len(sessions) == 9, "Live/human continuity incomplete")
    originals = read(root / "live/originals-checkpoint.json")
    for name, expected_hash in originals["files"].items():
        require(sha((root / "live/originals" / name).read_bytes()) == expected_hash, "Original evidence changed")
    responses = list((root / "live/originals").glob("*/acquisition/response-*.json"))
    require(len(responses) == 24 and checkpoint["new_model_generations"] == 0, "Generation accounting differs")
    require(checkpoint["work_state_continuity"] == "PASSED" and checkpoint["scientific_reasoning_acceptance"] == "FAILED",
            "Review outcome misstated")
    for name, expected_hash in checkpoint["final_source_fingerprints"].items():
        require(sha((root / "source" / name).read_bytes()) == expected_hash, "Final source fingerprint differs")
    return {"work_state_continuity": "PASSED", "scientific_reasoning_acceptance": "FAILED",
            "offline_records": 12, "offline_parent_links": 9, "live_model_records": 9, "human_D_records": 3,
            "live_human_parent_links": links, "calculations_reproduced": 24 if reproduce else 0,
            "original_local_generations": 24, "new_model_generations": 0,
            "provider_identity_authenticated": False, "fresh_database_contact": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--reproduce", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.reproduce)))
