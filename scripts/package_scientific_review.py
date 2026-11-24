"""Allowlisted offline/live review bundle; original receipt files remain byte-identical."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from producers import scientific
from scripts.package_scientific_evidence import PATTERNS
from scripts.verify_scientific_review_bundle import OFFLINE_HASH


def screen_values(value):
    """Inspect decoded JSON strings, including nested provider JSON, not escape syntax."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from screen_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from screen_values(item)
    elif isinstance(value, str):
        if value.lstrip().startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except ValueError:
                pass
            else:
                yield from screen_values(parsed)
                return
        yield value


def screen_member(name, raw):
    text = raw.decode("utf-8")
    values = screen_values(json.loads(text)) if name.endswith(".json") else [text]
    for text in values:
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                literal = (kind == "host_path" and "/source/" in "/" + name and name.endswith(".py") and
                           match.group() == "file://" and match.start() > 0 and match.end() < len(text) and
                           text[match.start() - 1] in "\"'" and text[match.end()] == text[match.start() - 1])
                if not literal:
                    raise ValueError("Privacy screening rejected " + name + " (" + kind + ")")


def package(live, decisions, output):
    root = scientific.ROOT
    old = root / ".tmp/yare-scientific-review-20261124"
    old_archive = old.with_suffix(".zip")
    if hashlib.sha256(old_archive.read_bytes()).hexdigest() != OFFLINE_HASH:
        raise ValueError("Original offline bundle changed")
    archive = output.with_suffix(".zip")
    if output.exists() or archive.exists():
        raise ValueError("Combined review output exists; do not overwrite")
    copies = {"verify.py": root / "scripts/verify_scientific_review_bundle.py",
              "shared_verifier.py": root / "scripts/verify_scientific_bundle.py",
              "README.md": root / "docs/SCIENTIFIC_COMBINED_BUNDLE_README.md",
              "docs/SCIENTIFIC_HUMAN_REVIEW_RESULT.md": root / "docs/SCIENTIFIC_HUMAN_REVIEW_RESULT.md",
              "docs/SCIENTIFIC_LIVE_PILOT_RESULT.md": root / "docs/SCIENTIFIC_LIVE_PILOT_RESULT.md",
              "original-offline-bundle.zip": old_archive,
              "live/originals-checkpoint.json": live / "pre-human-review-originals.json",
              "live/abc-review.json": live / "review-result.json",
              "live/model-integrity.json": live / "model-integrity.json",
              "live/regression-summary.json": root / "docs/SCIENTIFIC_REVIEW_REGRESSION.json",
              "live/human-review-result.json": decisions / "verified-result.json"}
    for source in sorted(old.rglob("*")):
        if source.is_file():
            copies["offline/" + source.relative_to(old).as_posix()] = source
    unit_dir = scientific.EXAMPLE / "references/gaia-dr3-units"
    for name in ("units.json", "gaia-source.html"):
        copies["live/unit-reference/" + name] = unit_dir / name
    originals = scientific.read_json(live / "pre-human-review-originals.json")
    for name, digest in originals["files"].items():
        path = live / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Original live evidence changed")
        copies["live/originals/" + name] = path
    previous = scientific.read_json(live / "review-result.json")
    completed = scientific.read_json(decisions / "verified-result.json")
    stages = []
    for repetition in range(1, 4):
        for letter in "abcd":
            run_id = f"public-science-local-20261124-{repetition}-{letter}"
            if letter == "d":
                path = decisions / str(repetition) / "d/handoff.json"
                expected = next(item for item in completed["records"] if item["run_id"] == run_id)
            else:
                matches = list(live.glob(str(repetition) + "-" + letter + "*/record/handoff.json"))
                if len(matches) != 1:
                    raise ValueError("Original handoff path ambiguous")
                path = matches[0]
                expected = next(item for item in previous["records"] if item["run_id"] == run_id)
            target = "live/records/" + str(repetition) + "/" + letter + ".json"
            copies[target] = path
            stages.append({"path": target, "run_id": run_id, "stage": letter.upper(),
                           "state_hash": expected.get("state_hash"), "receipt_hash": expected["receipt_hash"]})
        copies["live/reviews/" + str(repetition) + ".json"] = decisions / str(repetition) / "review.json"
    source_names = list(previous["controller_fingerprints_final_revision_only"])
    source_names += ["scripts/record_scientific_decision.py", "scripts/package_scientific_review.py",
                     "scripts/verify_scientific_review_bundle.py", "scripts/verify_scientific_bundle.py"]
    fingerprints = {}
    for name in sorted(set(source_names)):
        copies["source/" + name] = root / name
        fingerprints[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    # Screen before creating output. Do not redact/re-hash immutable evidence.
    for name, source in copies.items():
        if source.is_symlink() or not source.resolve().is_relative_to(root) or source.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Unsafe bundle member")
        if source.suffix == ".zip":
            continue  # Exact original archive was separately fingerprinted and verified.
        screen_member(name, source.read_bytes())
    output.mkdir(parents=True)
    for name, source in copies.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    checkpoint = {"work_state_continuity": "PASSED", "scientific_reasoning_acceptance": "FAILED",
                  "new_model_generations": 0, "stages": stages, "final_source_fingerprints": fingerprints,
                  "original_evidence_preserved": True, "provider_attestation": False}
    scientific.write_json(output / "live/checkpoint.json", checkpoint)
    files = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in output.rglob("*") if path.is_file()}
    scientific.write_json(output / "manifest.json", {"scope": "offline_fixtures_and_captured_live_human_continuity",
        "sanitization": "Allowlisted and pattern-screened; no original receipt redaction; not a universal secret detector",
        "files": dict(sorted(files.items()))})
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(output).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n", encoding="ascii")
    print(json.dumps({"files": len(files) + 1, "zip_bytes": archive.stat().st_size, "sha256": digest, "published": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package(args.live.resolve(), args.decisions.resolve(), args.output.resolve())
