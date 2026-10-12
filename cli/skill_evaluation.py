"""Run an operator-configured evaluator; proposal scores are never authoritative."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(root: Path, original: Path, proposed: Path, task: str) -> dict | None:
    config_path = root / ".yare" / "skill-evaluator.json"
    if not config_path.exists():
        return None
    try:
        config_bytes = config_path.read_bytes()
        config_hash = hashlib.sha256(config_bytes).hexdigest()
        config = json.loads(config_bytes)
        relative = Path(config["program"])
        program = (root / relative).resolve()
        scripts = (root / "scripts").resolve()
        expected = config["program_sha256"]
        timeout = config.get("timeout_seconds", 60)
        if (relative.is_absolute() or relative.drive or ".." in relative.parts
                or scripts != root / "scripts" or not program.is_relative_to(scripts)
                or program.suffix != ".py"
                or not isinstance(expected, str) or len(expected) != 64
                or type(timeout) is not int or not 1 <= timeout <= 300):
            raise ValueError("invalid configuration")
        results = []
        for skill in (original, proposed):
            if digest(program) != expected or digest(config_path) != config_hash:
                raise ValueError("evaluator changed")
            source_hash = digest(skill)
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                result = subprocess.run([sys.executable, str(program), str(skill), task],
                                        cwd=root, stdout=output, stderr=errors,
                                        timeout=timeout, check=False)
                if result.returncode != 0 or output.tell() > 1048576:
                    raise ValueError("evaluator failed or output exceeded limit")
                output.seek(0)
                report = json.load(output)
            if (digest(skill) != source_hash or digest(program) != expected
                    or digest(config_path) != config_hash):
                raise ValueError("evaluation inputs changed")
            if not isinstance(report, dict) or report.get("skill_sha256") != source_hash:
                raise ValueError("result does not match skill")
            cases = report.get("cases")
            if not isinstance(cases, list) or not cases:
                raise ValueError("no evaluated cases")
            by_id = {}
            for case in cases:
                if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                        or not case["id"] or type(case.get("passed")) is not bool
                        or case["id"] in by_id):
                    raise ValueError("invalid or duplicate case")
                by_id[case["id"]] = case["passed"]
            results.append({"skill_sha256": source_hash, "cases": by_id,
                            "score": sum(by_id.values()) / len(by_id)})
        if results[0]["cases"].keys() != results[1]["cases"].keys():
            raise ValueError("different evaluation cases")
        return {"evaluator_sha256": expected, "configuration_sha256": config_hash,
                "baseline": results[0], "proposed": results[1]}
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        raise ValueError("skill_edit_evaluation_failed") from exc
