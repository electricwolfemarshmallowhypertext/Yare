"""Synthetic provider responses verify the controller, not live model quality."""

import copy
import json

import pytest

from cli import integrity
from cli.scientific import ScientificEvidenceError, text_hash
from producers import scientific, scientific_local as local


@pytest.fixture
def captured(tmp_path, monkeypatch):
    bundle = scientific.prepare_bundle(scientific.EXAMPLE / "data/manifest.json", tmp_path / "bundle.json")
    reasoning = scientific.read_json(scientific.EXAMPLE / "requests/a.json")
    for key, singular in (("hypotheses", "hypothesis"), ("disagreements", "disagreement"), ("questions", "question")):
        reasoning.setdefault(key, [])
        for item in reasoning[key]:
            item["id"] = "A-" + singular + "-" + item["id"]
    responses = [{"action": "analyze"}, {"action": "emit", "reasoning": reasoning}]
    def fake(path, payload):
        action = responses.pop(0)
        return json.dumps({"model": local.MODEL, "message": {"role": "assistant", "content": json.dumps(action)},
                           "done": True, "done_reason": "stop", "prompt_eval_count": 1500, "eval_count": 100})
    monkeypatch.setattr(local, "request_local", fake)
    output = tmp_path / "acquisition"
    output.mkdir()
    value, trace = local.acquire(bundle, None, "A", output, "synthetic-session")
    science = scientific.build_science(bundle, "A", "synthetic-origin", value, execution_mode="live_model")
    return value, trace, science


def test_capture_binds_actual_tool_output_and_actions(captured):
    value, trace, science = captured
    assert local.verify_model_trace(trace, value, science)
    assert len(trace["calls"]) == 2
    assert trace["analysis_tool"]["exit_code"] == 0
    serialized = json.dumps(trace["calls"][0]["request"])
    assert "content_utf8" not in serialized
    assert "YARE_DATABASE_URL" not in serialized


@pytest.mark.parametrize("part", ["response", "request", "tool", "parent", "truncation", "stdout", "reasoning"])
def test_origin_rejects_tampering_and_invalid_actions(captured, part):
    value, trace, science = copy.deepcopy(captured)
    if part == "response":
        trace["calls"][1]["response_utf8"] += " "
    elif part == "request":
        trace["calls"][0]["request"]["model"] = "remote-model"
    elif part == "tool":
        trace["analysis_tool"]["stdout"] = "{}"
    elif part == "parent":
        trace["parent"] = {"run_id": "wrong"}
    elif part in ("truncation", "stdout"):
        call = trace["calls"][0]
        response = json.loads(call["response_utf8"])
        if part == "truncation":
            response["done_reason"] = "length"
        else:
            response["message"]["content"] = json.dumps({"action": "analyze", "stdout": "invented"})
        call["response_utf8"] = json.dumps(response)
        call["response_sha256"] = text_hash(call["response_utf8"])
    else:
        value["hypotheses"][0]["statement"] = "Substituted interpretation"
    with pytest.raises((ScientificEvidenceError, ValueError)):
        local.verify_model_trace(trace, value, science)


def test_fixture_cannot_follow_live_parent_without_captured_origin(captured, tmp_path, monkeypatch):
    value, trace, science = captured
    artifact = scientific.make_artifact(science, "synthetic-live-a", {"exit_code": 0})
    parent = {"verified": True, "run_id": "synthetic-live-a", "current_state_hash": "a" * 64,
              "receipt_hash": "b" * 64, "artifacts": [artifact]}
    monkeypatch.setenv("YARE_DATABASE_URL", "fixture-only")
    monkeypatch.setattr(scientific.storage, "load_handoff", lambda **kwargs: parent)
    reasoning = scientific.read_json(scientific.EXAMPLE / "requests/b.json")
    for item in reasoning["disagreements"]:
        item["hypothesis_ids"] = ["A-hypothesis-" + identifier if identifier == "hypothesis-endpoints" else identifier
                                  for identifier in item["hypothesis_ids"]]
    with pytest.raises(ScientificEvidenceError, match="execution_origin_changed"):
        scientific.record_stage(None, "B", "synthetic-origin", "synthetic-b", reasoning,
                                tmp_path / "b", storage_mode="cockroach", parent_run_id="synthetic-live-a")
    assert not (tmp_path / "b").exists()


def test_stage_schema_prevents_cross_kind_id_collision_and_single_sided_dispute():
    import jsonschema
    payload = {"action": "emit", "reasoning": {"hypotheses": [{"id": "A-1", "statement": "Fixture only",
              "status": "unverified", "evidence_refs": ["ztf"]}], "questions": [], "disagreements": []}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, local.reasoning_schema("A"))
    payload["reasoning"] = {"hypotheses": [], "questions": [], "disagreements": [{"id": "B-disagreement-1",
        "hypothesis_ids": ["A-hypothesis-1"], "evidence_refs": ["ztf"], "reason": "Fixture only", "status": "open"}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, local.reasoning_schema("B"))
    assert "$ref" not in json.dumps(local.reasoning_schema("B"))
    assert local.reasoning_schema("B")["properties"]["reasoning"]["properties"]["disagreements"]["items"]["properties"]["hypothesis_ids"]["minItems"] == 2


def test_relative_output_does_not_make_artifact_missing(tmp_path, monkeypatch):
    bundle = scientific.prepare_bundle(scientific.EXAMPLE / "data/manifest.json", tmp_path / "bundle.json")
    monkeypatch.chdir(tmp_path)
    result = scientific.record_stage(bundle, "A", "relative-science", "relative-a",
                                    scientific.read_json(scientific.EXAMPLE / "requests/a.json"),
                                    __import__("pathlib").Path("relative-output"))
    assert result["run_id"] == "relative-a"


def test_replacement_disagreement_marks_new_hypothesis_disputed(captured):
    _, _, first = captured
    a = {"verified": True, "run_id": "synthetic-a", "current_state_hash": "a" * 64,
         "receipt_hash": "b" * 64, "artifacts": [scientific.make_artifact(first, "synthetic-a", {})]}
    request = scientific.read_json(scientific.EXAMPLE / "requests/b.json")
    request["disagreements"][0]["hypothesis_ids"][0] = first["hypotheses"][0]["id"]
    bundle = {key: first[key] for key in ("datasets", "analysis", "observations", "brief_sha256")}
    b = scientific.build_science(bundle, "B", first["investigation_id"], request, a, execution_mode="live_model")
    parent = {"verified": True, "run_id": "synthetic-b", "current_state_hash": "c" * 64,
              "receipt_hash": "d" * 64, "artifacts": [scientific.make_artifact(b, "synthetic-b", {})]}
    reasoning = {"hypotheses": [{"id": "C-hypothesis-1", "statement": "Synthetic alternative only",
                                 "status": "unverified", "evidence_refs": ["ztf"]}],
                 "disagreements": [{"id": "C-disagreement-1", "hypothesis_ids": [first["hypotheses"][0]["id"], "C-hypothesis-1"],
                                    "evidence_refs": ["ztf"], "reason": "Synthetic contract test", "status": "open"}], "questions": []}
    c = scientific.build_science(bundle, "C", first["investigation_id"], reasoning, parent, execution_mode="live_model")
    assert c["hypotheses"][-1]["status"] == "disputed"
