"""Build an allowlisted local review bundle; preserve original receipt bytes."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / ".tmp/scientific-evaluation-final-20261124"
PATTERNS = {
    "host_path": re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[A-Za-z0-9]|file://|/(?:home|Users|root)/)"),
    "database_url": re.compile(r"postgres(?:ql)?://", re.I),
    "credential": re.compile(r"\b(?:AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{20,})\b"),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def package(output):
    archive = output.with_suffix(".zip")
    if output.exists() or archive.exists():
        raise ValueError("Review output already exists; refusing to overwrite evidence")
    checkpoint_path = ROOT / "examples/scientific-handoff/evaluation-checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    copies = {
        "README.md": ROOT / "docs/SCIENTIFIC_EVIDENCE_BUNDLE_README.md",
        "verify.py": ROOT / "scripts/verify_scientific_bundle.py",
        "docs/SCIENTIFIC_EVALUATION_RESULT.md": ROOT / "docs/SCIENTIFIC_EVALUATION_RESULT.md",
        "docs/SCIENTIFIC_REPORT_REVIEW.md": ROOT / "docs/SCIENTIFIC_REPORT_REVIEW.md",
        "docs/SCIENTIFIC_LIVE_VALIDATION_PLAN.md": ROOT / "docs/SCIENTIFIC_LIVE_VALIDATION_PLAN.md",
        "docs/SCIENTIFIC_WORK_CONTINUITY.md": ROOT / "docs/SCIENTIFIC_WORK_CONTINUITY.md",
        "checkpoint.json": checkpoint_path,
        "examples/scientific-handoff/evaluation-checkpoint.json": checkpoint_path,
        "analysis.py": ROOT / "examples/scientific-handoff/analysis.py",
        "brief.md": ROOT / "examples/scientific-handoff/brief.md",
        "scientific-evidence.schema.json": ROOT / "schemas/scientific-evidence.schema.json",
    }
    for name in ("ztf.json", "gaia.csv", "manifest.json"):
        copies["data/" + name] = ROOT / "examples/scientific-handoff/data" / name
    for name, expected in checkpoint["source_fingerprints"]["files"].items():
        source = ROOT / name
        if sha(source.read_bytes()) != expected:
            raise ValueError("Implementation differs from the evaluation checkpoint: " + name)
        copies["source/" + name] = source
    for stage in checkpoint["stages"]:
        repetition = stage["run_id"].split("-")[-2]
        letter = stage["stage"].lower()
        copies["records/" + repetition + "/" + letter + ".json"] = RECORDS / repetition / letter / "handoff.json"
    # Screen all chosen bytes before creating any distributable output.
    for name, source in copies.items():
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError("Unexpected source path")
        text = source.read_bytes().decode("utf-8")
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                policy_literal = (kind == "host_path" and name.startswith("source/") and name.endswith(".py") and
                                  match.group() == "file://" and match.start() > 0 and match.end() < len(text) and
                                  text[match.start() - 1] in "\"'" and text[match.end()] == text[match.start() - 1])
                if not policy_literal:
                    raise ValueError("Privacy screening rejected " + name + " (" + kind + "); no redaction performed")
    output.mkdir(parents=True)
    hashes = {}
    for name, source in copies.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[name] = sha(target.read_bytes())
    manifest = {"scope": "offline_scripted_fixtures_only", "original_receipts_preserved": True,
                "sanitization": "Allowlisted and screened; originals not modified; not a universal secret detector",
                "not_proved": ["live model reasoning", "live Cockroach persistence", "scientific correctness", "reviewer identity"],
                "files": dict(sorted(hashes.items()))}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(output).as_posix())
    checksum = sha(archive.read_bytes())
    archive.with_suffix(".zip.sha256").write_text(checksum + "  " + archive.name + "\n", encoding="ascii")
    print(json.dumps({"files": len(hashes) + 1, "zip_bytes": archive.stat().st_size,
                      "zip_sha256": checksum, "receipt_files": 12, "publication": "none"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    package(parser.parse_args().output.resolve())
