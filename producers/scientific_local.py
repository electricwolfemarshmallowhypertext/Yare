"""Local-only scientific acquisition; fresh process per role, no paid-provider client."""

import argparse
import hashlib
import json
import os
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from cli import integrity, storage
from cli.scientific import ScientificEvidenceError, text_hash
from producers import scientific

ENDPOINT = "http://127.0.0.1:11435"
MODEL = "qwen3:4b"
MODEL_DIGEST = "359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7"
LEDGER_DIGEST = "e3138784251046976ef395cf5e4060ed91912e9c0f770d7cd37b8c04973dcbb7"
ACTION_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["action"],
                 "properties": {"action": {"const": "analyze"}}}


def guard_database(authorization_path):
    """Serial research-only statement/byte envelope; never changes the paid ledger."""
    counter = authorization_path.parent / "database-usage.json"
    original = storage._connect
    class Cursor:
        def __init__(self, cursor):
            self.cursor = cursor
        def __enter__(self):
            self.cursor.__enter__()
            return self
        def __exit__(self, *args):
            return self.cursor.__exit__(*args)
        def execute(self, sql, args=()):
            verb = sql.lstrip().split()[0].upper()
            if verb not in ("SELECT", "INSERT"):
                raise ValueError("Only SELECT/INSERT allowed in scientific validation")
            if verb == "INSERT" and any(len(value.encode()) > 1048576 for value in args if isinstance(value, str)):
                raise ValueError("Scientific record exceeds one-MiB serialization bound")
            usage = scientific.read_json(counter) if counter.exists() else {"SELECT": 0, "INSERT": 0, "json_bytes": 0}
            usage[verb] += 1
            usage["json_bytes"] += sum(len(value.encode()) for value in args if isinstance(value, str)) if verb == "INSERT" else 0
            if usage["SELECT"] > 75 or usage["INSERT"] > 156 or usage["json_bytes"] > 32 * 1024 * 1024:
                raise ValueError("Scientific database envelope exhausted")
            scientific.write_json(counter, usage)
            return self.cursor.execute(sql, args)
        def fetchone(self):
            return self.cursor.fetchone()
        def fetchall(self):
            return self.cursor.fetchall()
    class Connection:
        def __init__(self, connection):
            self.connection = connection
        def __enter__(self):
            self.connection.__enter__()
            return self
        def __exit__(self, *args):
            return self.connection.__exit__(*args)
        def cursor(self):
            return Cursor(self.connection.cursor())
        def commit(self):
            return self.connection.commit()
    storage._connect = lambda url: Connection(original(url))


def reasoning_schema(stage=None):
    schema = scientific.read_json(scientific.ROOT / "schemas/scientific-evidence.schema.json")
    schema["$defs"]["disagreement"]["properties"]["hypothesis_ids"]["minItems"] = 2
    if stage:
        for key in ("hypothesis", "disagreement", "question"):
            schema["$defs"][key]["properties"]["id"]["pattern"] = "^" + stage + "-" + key + "-"
    result = {"type": "object", "additionalProperties": False, "required": ["action", "reasoning"],
            "properties": {"action": {"const": "emit"}, "reasoning": {
                "type": "object", "additionalProperties": False,
                "required": ["hypotheses", "disagreements", "questions"], "properties": {
                    name: {"type": "array", "maxItems": 0 if stage == "A" and name == "disagreements" else 3,
                           "items": {"$ref": "#/$defs/" + singular}}
                    for name, singular in (("hypotheses", "hypothesis"), ("disagreements", "disagreement"),
                                           ("questions", "question"))}}}}
    # Inline refs so Ollama's grammar sees cardinality constraints beside a ref.
    def inline(value):
        if isinstance(value, list):
            return [inline(item) for item in value]
        if isinstance(value, dict):
            if "$ref" in value:
                target = schema["$defs"][value["$ref"].split("/")[-1]]
                value = {**target, **{key: item for key, item in value.items() if key != "$ref"}}
            return {key: inline(item) for key, item in value.items()}
        return value
    return inline(result)


def request_local(path, payload=None, timeout=180):
    data = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
    request = urllib.request.Request(ENDPOINT + path, data=data, headers={"Content-Type": "application/json"})
    # Never inherit proxy settings or follow a redirect away from loopback.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError("Local provider redirect forbidden")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("Local provider response exceeds byte bound")
    return raw.decode("utf-8")


def verify_cached_model(models):
    manifest_path = models / "manifests/registry.ollama.ai/library/qwen3/4b"
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MODEL_DIGEST:
        raise ValueError("Cached model manifest changed")
    manifest = json.loads(raw)
    verified = []
    for layer in [manifest["config"], *manifest["layers"]]:
        blob = models / "blobs" / layer["digest"].replace(":", "-")
        hasher = hashlib.sha256()
        with blob.open("rb") as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                hasher.update(block)
        if blob.stat().st_size != layer["size"] or hasher.hexdigest() != layer["digest"].split(":")[1]:
            raise ValueError("Cached model layer differs")
        verified.append({"digest": layer["digest"], "bytes": layer["size"]})
    return {"model": MODEL, "manifest_sha256": MODEL_DIGEST, "layers": verified}


def projection(bundle, parent):
    science = scientific.scientific_payload(parent) if parent else bundle
    return {"datasets": [{**{key: item[key] for key in ("id", "release", "sha256")},
                          "selected_row_count": len(item["selected_rows"]),
                          "selection_sha256": integrity.digest(item["selected_rows"])}
                         for item in science["datasets"]],
            "observations": science["observations"][:5], "observation_count": len(science["observations"]),
            "gaia_positional_candidates": scientific.dataset_rows(science["datasets"][1]),
            "analysis_results": science["analysis"]["results"], "analysis_sha256": science["analysis"]["sha256"],
            "parameters": science["analysis"]["parameters"],
            "hypotheses": science.get("hypotheses", []), "disagreements": science.get("disagreements", []),
            "questions": science.get("questions", []),
            "parent": {key: parent[key] for key in ("run_id", "current_state_hash", "receipt_hash")} if parent else None}


def verify_model_trace(trace, reasoning, science):
    if (trace.get("provider") != "ollama-local" or trace.get("endpoint") != ENDPOINT or
            trace.get("model_digest") != MODEL_DIGEST or trace.get("stage") != science["stage"] or
            trace.get("parent") != science["parent"] or len(trace.get("calls", [])) != 2):
        raise ScientificEvidenceError("science_model_origin_invalid")
    expected = [{"action": "analyze"}, {"action": "emit", "reasoning": reasoning}]
    for index, (call, action) in enumerate(zip(trace["calls"], expected)):
        request, raw = call["request"], call["response_utf8"]
        response = json.loads(raw)
        if (integrity.digest(request) != call["request_sha256"] or text_hash(raw) != call["response_sha256"] or
                request.get("model") != MODEL or request.get("think") is not False or request.get("stream") is not False or
                request.get("options", {}).get("num_ctx") != 8192 or
                request.get("options", {}).get("num_predict") != 2048 or
                response.get("model") != MODEL or response.get("done") is not True or
                response.get("done_reason") != "stop" or not 0 < response.get("eval_count", 0) <= 2048 or
                json.loads(response["message"]["content"]) != action):
            raise ScientificEvidenceError("science_model_trace_mismatch")
        jsonschema.validate(action, ACTION_SCHEMA if index == 0 else reasoning_schema())
    tool = trace["analysis_tool"]
    if (tool["exit_code"] != 0 or json.loads(tool["stdout"]) != science["analysis"]["results"] or
            trace["brief_sha256"] != science["brief_sha256"] or
            trace["calls"][1]["request"]["messages"][-1]["content"] != json.dumps({"analysis_tool": tool}, sort_keys=True)):
        raise ScientificEvidenceError("science_model_tool_mismatch")
    return True


def acquire(bundle, parent, stage, output, session_id):
    brief = (scientific.EXAMPLE / "brief.md").read_text(encoding="utf-8")
    instructions = (
        "You are a fresh research assistant session. Use only the supplied public brief, verified handoff projection, "
        "and controller tool output. No private files, web, shell, editing, or observing actions. "
        "These are observations and descriptive statistics, not a source classification. "
        "First request the pinned analysis with exactly {\"action\":\"analyze\"}. After its real result, emit JSON "
        "matching the supplied schema. Emit only NEW hypotheses/disagreements/questions; existing entries are retained "
        "by the controller. Use unique IDs of the form STAGE-hypothesis-N, STAGE-disagreement-N, or STAGE-question-N, "
        "where STAGE is your assigned letter and N is a unique number within that kind. Evidence references are dataset IDs ztf "
        "or gaia (or shown observation IDs), not invented analysis IDs. All hypotheses remain unverified or disputed. "
        "Disagreement means two genuinely different interpretations of identified evidence, not merely copied wording "
        "or an unrelated caveat; reference both hypothesis IDs. Do not fabricate agreement, "
        "disagreement, approval, data, or tool output. Keep text concise.\nFixed brief:\n" + brief)
    roles = {"A": "Record a tentative interpretation and open questions; no prior collaborator disagreement exists yet.",
             "B": "Assess A's existing interpretation using the computed results. Preserve it and, only if justified, "
                  "propose a genuinely competing interpretation and evidence-based disagreement referencing both IDs.",
             "C": "Act as the replacement researcher. Request a real recomputation, assess the saved investigation, "
                  "and retain unresolved questions without claiming resolution."}
    instructions += "\nYour role only: " + stage + ": " + roles[stage]
    messages = [{"role": "system", "content": instructions}, {"role": "user", "content": json.dumps({
        "stage": stage, "verified_input": projection(bundle, parent), "output_schema": reasoning_schema(stage)}, sort_keys=True)}]
    calls = []
    for turn in range(2):
        payload = {"model": MODEL, "stream": False, "think": False, "messages": messages.copy(),
                   "format": ACTION_SCHEMA if turn == 0 else reasoning_schema(stage), "keep_alive": "2m",
                   "options": {"num_ctx": 8192, "num_predict": 2048, "temperature": 0, "seed": 101}}
        scientific.write_json(output / ("request-" + str(turn + 1) + ".json"), payload)
        started = time.perf_counter()
        raw = request_local("/api/chat", payload)
        (output / ("response-" + str(turn + 1) + ".json")).write_text(raw, encoding="utf-8")
        response = json.loads(raw)
        calls.append({"request": payload, "request_sha256": integrity.digest(payload), "response_utf8": raw,
                      "response_sha256": text_hash(raw), "wall_ms": (time.perf_counter() - started) * 1000})
        if response.get("done_reason") != "stop" or response.get("done") is not True:
            raise ValueError("Local generation did not finish cleanly; response retained")
        if response.get("prompt_eval_count", 0) > 6144:
            raise ValueError("Local prompt exceeds reserved context allowance")
        action = json.loads(response["message"]["content"])
        jsonschema.validate(action, payload["format"])
        if turn == 0:
            # Tool output is computed by the controller, never accepted from the model.
            tool_science = scientific.scientific_payload(parent) if parent else bundle
            tool = scientific.reproduce(tool_science, output)
            scientific.write_json(output / "analysis-tool.json", tool)
            messages.extend([{"role": "assistant", "content": response["message"]["content"]},
                             {"role": "user", "content": json.dumps({"analysis_tool": tool}, sort_keys=True)}])
    trace = {"provider": "ollama-local", "endpoint": ENDPOINT, "model": MODEL, "model_digest": MODEL_DIGEST,
             "stage": stage, "session_id": session_id, "pid": os.getpid(), "fresh_message_context": True,
             "brief_sha256": text_hash(brief), "parent": projection(bundle, parent)["parent"],
             "analysis_tool": tool, "calls": calls}
    scientific.write_json(output / "trace.json", trace)
    return action["reasoning"], trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=list("ABC"), required=True, help="D is deliberately unavailable before review")
    parser.add_argument("--investigation-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--parent-run-id")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--replay-trace", type=Path, help="Reuse an already captured response after a controller-only failure; no inference")
    args = parser.parse_args()
    authorization = scientific.read_json(args.authorization)
    if (authorization.get("provider") != "ollama-local" or authorization.get("max_calls") != 24 or
            authorization.get("stop_before") != "D" or authorization.get("paid_calls") is not False):
        raise ValueError("Missing scoped local execution authorization")
    if args.run_id not in authorization["run_ids"] or args.output.exists():
        raise ValueError("Run not authorized or output already exists")
    ledger = Path(authorization["ledger_path"])
    if hashlib.sha256(ledger.read_bytes()).hexdigest() != LEDGER_DIGEST:
        raise ValueError("Shared ledger changed; refusing execution")
    if (args.stage == "A") != (args.parent_run_id is None) or (args.stage != "A" and args.bundle is not None):
        raise ValueError("Replacement agents must use only a Cockroach parent, not a local bundle")
    completed_requests = list(args.authorization.parent.glob("*/acquisition/request-*.json"))
    if not args.replay_trace and len(completed_requests) + 2 > authorization["max_calls"]:
        raise ValueError("Local generation allowance exhausted")
    if not args.replay_trace:
        tags = json.loads(request_local("/api/tags", timeout=10))
        if not any(item.get("name") == MODEL and item.get("digest") == MODEL_DIGEST for item in tags["models"]):
            raise ValueError("Pinned cached local model unavailable; no download/fallback")
    if not os.environ.get("YARE_DATABASE_URL"):
        raise ValueError("Existing Cockroach runtime credential required")
    guard_database(args.authorization)
    parent = storage.load_handoff(run_id=args.parent_run_id) if args.parent_run_id else None
    bundle = scientific.read_json(args.bundle) if args.bundle else None
    args.output.mkdir(parents=True)
    acquisition = args.output / "acquisition"
    acquisition.mkdir()
    before = ledger.read_bytes()
    try:
        if args.replay_trace:
            trace = scientific.read_json(args.replay_trace)
            reasoning = json.loads(json.loads(trace["calls"][1]["response_utf8"])["message"]["content"])["reasoning"]
            scientific.write_json(acquisition / "replay.json", {"source_trace_sha256": integrity.digest(trace),
                                                              "new_generations": 0})
        else:
            reasoning, trace = acquire(bundle, parent, args.stage, acquisition, str(uuid.uuid4()))
        result = scientific.record_stage(bundle, args.stage, args.investigation_id, args.run_id, reasoning,
                                         args.output / "record", storage_mode="cockroach",
                                         parent_run_id=args.parent_run_id, model_trace=trace)
        print(json.dumps(result))
    except Exception as exc:
        scientific.write_json(args.output / "failure.json", {"error_type": type(exc).__name__,
                              "error_code": str(exc) if isinstance(exc, ScientificEvidenceError) else "local_stage_failed",
                              "stage": args.stage, "run_id": args.run_id})
        raise
    finally:
        if ledger.read_bytes() != before:
            raise ValueError("Shared ledger changed during local execution")


if __name__ == "__main__":
    main()
