"""Bounded scientific evidence integrity; never executes supplied analysis code."""

import csv
import hashlib
import io
import json
import re
from functools import lru_cache
from pathlib import Path

import jsonschema

from cli.integrity import digest


class ScientificEvidenceError(ValueError):
    pass


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _validator():
    schema = json.loads((Path(__file__).resolve().parents[1] /
                         "schemas/scientific-evidence.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def dataset_rows(dataset):
    if dataset["media_type"] == "application/json":
        try:
            rows = json.loads(dataset["content_utf8"])
            for key in dataset["row_selector"]:
                rows = rows[key]
        except (ValueError, KeyError, TypeError) as exc:
            raise ScientificEvidenceError("science_dataset_selector_invalid") from exc
        if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) and row for row in rows):
            raise ScientificEvidenceError("science_dataset_rows_invalid")
        return rows
    reader = csv.DictReader(io.StringIO(dataset["content_utf8"]))
    names = reader.fieldnames
    if not names or len(set(names)) != len(names):
        raise ScientificEvidenceError("science_dataset_columns_invalid")
    rows = list(reader)
    if not rows or any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ScientificEvidenceError("science_dataset_rows_invalid")
    return rows


def _index(records):
    indexed = {record["id"]: record for record in records}
    if len(indexed) != len(records):
        raise ScientificEvidenceError("science_duplicate_id")
    return indexed


def verify_scientific_evidence(value):
    try:
        json.dumps(value, allow_nan=False)
        _validator().validate(value)
    except (ValueError, TypeError, jsonschema.ValidationError) as exc:
        raise ScientificEvidenceError("science_contract_invalid") from exc
    datasets = _index(value["datasets"])
    observations = _index(value["observations"])
    hypotheses = _index(value["hypotheses"])
    questions = _index(value["questions"])
    disagreements = _index(value["disagreements"])
    identities = [*datasets, *observations, *hypotheses, *questions, *disagreements]
    if len(set(identities)) != len(identities):
        raise ScientificEvidenceError("science_duplicate_id")
    rows_by_dataset, selected = {}, {}
    for identifier, dataset in datasets.items():
        if text_hash(dataset["content_utf8"]) != dataset["sha256"]:
            raise ScientificEvidenceError("science_dataset_hash_mismatch")
        rows = dataset_rows(dataset)
        selections = dataset["selected_rows"]
        indices = {record["index"] for record in selections}
        if len(indices) != len(selections):
            raise ScientificEvidenceError("science_duplicate_row")
        for record in selections:
            index = record["index"]
            if index >= len(rows) or digest(rows[index]) != record["sha256"]:
                raise ScientificEvidenceError("science_selected_row_mismatch")
        rows_by_dataset[identifier], selected[identifier] = rows, indices
    for observation in observations.values():
        identifier, index = observation["dataset_id"], observation["row_index"]
        if identifier not in datasets or index not in selected[identifier]:
            raise ScientificEvidenceError("science_observation_row_missing")
        row = rows_by_dataset[identifier][index]
        for column_key, value_key in (("value_column", "value"), ("uncertainty_column", "uncertainty"),
                                      ("time_column", "time_value")):
            try:
                matches = float(row[observation[column_key]]) == observation[value_key]
            except (ValueError, KeyError, TypeError) as exc:
                raise ScientificEvidenceError("science_observation_value_invalid") from exc
            if not matches:
                raise ScientificEvidenceError("science_observation_value_mismatch")
    references = set(datasets) | set(observations)
    for record in [*hypotheses.values(), *disagreements.values()]:
        if not set(record["evidence_refs"]) <= references:
            raise ScientificEvidenceError("science_evidence_reference_missing")
    for record in disagreements.values():
        if (len(record["hypothesis_ids"]) < 2 or
                not set(record["hypothesis_ids"]) <= set(hypotheses)):
            raise ScientificEvidenceError("science_disagreement_hypothesis_missing")
        if any(hypotheses[identifier]["status"] != "disputed" for identifier in record["hypothesis_ids"]):
            raise ScientificEvidenceError("science_disagreement_status_mismatch")
    analysis = value["analysis"]
    if text_hash(analysis["source_code"]) != analysis["sha256"]:
        raise ScientificEvidenceError("science_analysis_hash_mismatch")
    if digest(analysis["results"]) != analysis["results_sha256"]:
        raise ScientificEvidenceError("science_results_hash_mismatch")
    stage, parent, review = value["stage"], value["parent"], value["human_review"]
    if value["execution"] == "human_decision" and stage != "D":
        raise ScientificEvidenceError("science_human_execution_stage_invalid")
    if (stage == "A") != (parent is None):
        raise ScientificEvidenceError("science_parent_required")
    if stage != "D" and review is not None:
        raise ScientificEvidenceError("science_review_stage_invalid")
    if stage == "D":
        if review is None:
            raise ScientificEvidenceError("science_human_review_required")
        original = {key: item for key, item in review.items() if key != "record_sha256"}
        if (review["parent_receipt_hash"] != parent["receipt_hash"] or
                digest(original) != review["record_sha256"]):
            raise ScientificEvidenceError("science_human_review_mismatch")
    return value


def verify_continuity(child, parent):
    """Check a child against an already verified, exact stored predecessor."""
    verify_scientific_evidence(child)
    if parent.get("verified") is not True:
        raise ScientificEvidenceError("science_parent_not_verified")
    identity = {key: parent[key] for key in ("run_id", "current_state_hash", "receipt_hash")}
    if child["parent"] != identity:
        raise ScientificEvidenceError("science_parent_identity_mismatch")
    artifacts = parent.get("artifacts", [])
    candidates = [artifact["evidence"]["scientific"] for artifact in artifacts
                  if isinstance(artifact.get("evidence"), dict) and "scientific" in artifact["evidence"]]
    if len(candidates) != 1:
        raise ScientificEvidenceError("science_parent_artifact_ambiguous")
    previous = verify_scientific_evidence(candidates[0])
    if ("ABCD".index(child["stage"]) != "ABCD".index(previous["stage"]) + 1 or
            child["investigation_id"] != previous["investigation_id"] or
            child["brief_sha256"] != previous["brief_sha256"] or
            (child["execution"] != previous["execution"] and not
             (child["stage"] == "D" and child["execution"] == "human_decision"))):
        raise ScientificEvidenceError("science_investigation_changed")
    if child["datasets"] != previous["datasets"] or child["analysis"] != previous["analysis"]:
        raise ScientificEvidenceError("science_frozen_provenance_changed")
    for key in ("observations", "hypotheses", "disagreements", "questions"):
        latest = _index(child[key])
        for identifier, old in _index(previous[key]).items():
            if identifier not in latest:
                raise ScientificEvidenceError("science_evidence_disappeared")
            new = latest[identifier]
            if key == "hypotheses":
                old, new = dict(old), dict(new)
                old_status, new_status = old.pop("status"), new.pop("status")
                if old_status == "disputed" and new_status != "disputed":
                    raise ScientificEvidenceError("science_disagreement_cleared")
            if old != new:
                raise ScientificEvidenceError("science_prior_evidence_changed")
    return child


def scientific_review_findings(science, unit_reference):
    """Annotate the human review without repairing or deduplicating model evidence."""
    if science["stage"] != "D" or science["execution"] != "human_decision":
        raise ScientificEvidenceError("science_deterministic_review_required")
    if (not isinstance(unit_reference, dict) or
            unit_reference.get("source_url") != "https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_main_source_catalogue/ssec_dm_gaia_source.html"
            or unit_reference.get("units") != {"ra_error": "mas", "dec_error": "mas"}
            or any(not re.search(key + r"\s*:\s*Standard error[^\n]*Angle\[mas\]", unit_reference.get("excerpt", ""))
                   for key in ("ra_error", "dec_error"))
            or text_hash(unit_reference.get("excerpt", "")) != unit_reference.get("excerpt_sha256")
            or not re.fullmatch("[0-9a-f]{64}", unit_reference.get("document_sha256", ""))):
        raise ScientificEvidenceError("science_unit_reference_invalid")
    groups = {}
    for item in science["hypotheses"]:
        groups.setdefault(" ".join(item["statement"].lower().split()), []).append(item["id"])
    duplicates = [ids for ids in groups.values() if len(ids) > 1]
    statements = [(item["id"], item["statement"]) for item in science["hypotheses"]]
    statements += [(item["id"], item["reason"]) for item in science["disagreements"]]
    wrong_units = [identifier for identifier, text in statements
                   if re.search(r"(?:ra_error|dec_error).{0,30}" + chr(176), text)]
    unsupported_trend = [item["id"] for item in science["hypotheses"]
                         if "steady decline" in item["statement"].lower()]
    return {"version": "scientific-human-review.v1", "source": "operator_supplied",
            "review_sha256": science["human_review"]["record_sha256"], "parent": science["parent"],
            "work_state_continuity": "PASSED", "scientific_reasoning_acceptance": "FAILED",
            "source_classification": "deferred", "original_evidence_retained": True,
            "duplicate_hypothesis_groups": duplicates,
            "unit_error_statement_ids": wrong_units, "unit_reference": unit_reference,
            "unsupported_trend_hypothesis_ids": unsupported_trend,
            "unresolved_gaia_question_ids": [item["id"] for item in science["questions"]],
            "diagnostic_only": True, "observing_or_paid_actions_authorized": False,
            "interpretation": "Review findings do not establish a source class, trend, or physical association."}
