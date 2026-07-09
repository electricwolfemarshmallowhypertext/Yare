#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
import yaml

from cli import archive as archive_backend
from cli import storage as storage_backend

app = typer.Typer(add_completion=False, help="Yare context governance runtime CLI")
lead_app = typer.Typer(add_completion=False, help="AI Work Lead primitives")
skill_app = typer.Typer(add_completion=False, help="Skill optimization gates")
storage_app = typer.Typer(add_completion=False, help="CockroachDB durable memory storage")
memory_app = typer.Typer(add_completion=False, help="Search CockroachDB-backed Yare memory")
app.add_typer(lead_app, name="lead")
app.add_typer(skill_app, name="skill")
app.add_typer(storage_app, name="storage")
app.add_typer(memory_app, name="memory")

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "limits": {
        "max_file_bytes": 131072,
        "max_total_bytes": 524288,
    },
    "resolve": {
        "max_skills": 6,
        "max_memory": 6,
        "max_policies": 6,
        "max_evals": 4,
    },
    "skills": {
        "required_metadata": ["id", "name", "description", "version", "permissions"],
        "forbidden_permissions": ["filesystem:write_outside_workspace", "network:admin"],
    },
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "this",
    "that",
    "with",
    "from",
    "into",
    "your",
    "about",
    "agent",
    "agents",
    "repo",
    "project",
    "review",
    "context",
}

ADAPTER_INSTRUCTIONS = {
    "codex": "codex --task \"{task}\" --context-file \"{context_file}\"",
    "claude": "claude code --prompt \"{task}\" --context-file \"{context_file}\"",
    "gemini": "gemini --prompt \"{task}\" --context-file \"{context_file}\"",
}

LEAD_ARTIFACT_SCHEMA_FILE = "schemas/lead-artifact.schema.json"
SKILL_EDIT_SCHEMA_FILE = "schemas/skill-edit.schema.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _bundle_hash(selected_items: list[dict[str, Any]]) -> str:
    material = []
    for item in selected_items:
        p = str(item.get("path") or "")
        h = str(item.get("sha256") or "")
        if p:
            material.append({"path": p, "sha256": h})
    material.sort(key=lambda x: x["path"])
    payload = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _resolved_pointer_path(root: Path) -> Path:
    return root / ".yare" / "last-resolved-path.txt"


def _write_resolved_pointer(root: Path, resolved_path: Path) -> None:
    ptr = _resolved_pointer_path(root)
    ptr.parent.mkdir(parents=True, exist_ok=True)
    ptr.write_text(str(resolved_path.resolve()), encoding="utf-8")


def _read_resolved_pointer(root: Path) -> Path | None:
    ptr = _resolved_pointer_path(root)
    if not ptr.exists():
        return None
    raw = ptr.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = (root / p).resolve()
    return p


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path.resolve())


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)  # type: ignore[index]
        else:
            out[k] = v
    return out


def _load_config(root: Path) -> dict[str, Any]:
    path = root / "yare.yaml"
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        data = yaml.safe_load(_load_text(path)) or {}
        if not isinstance(data, dict):
            return dict(DEFAULT_CONFIG)
        return _merge_dict(DEFAULT_CONFIG, data)
    except Exception:
        return dict(DEFAULT_CONFIG)


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    front_matter = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        metadata = yaml.safe_load(front_matter) or {}
        if not isinstance(metadata, dict):
            metadata = {}
    except Exception:
        metadata = {}
    return metadata, body


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _tokenize(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
        if t not in STOPWORDS and not t.isdigit()
    }


def _score_text(task_tokens: set[str], text: str) -> int:
    if not task_tokens:
        return 0
    content_tokens = _tokenize(text)
    return len(task_tokens.intersection(content_tokens))


def _extract_markdown_links(text: str) -> list[str]:
    inline = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    refs = re.findall(r"^\[[^\]]+\]:\s*(\S+)", text, flags=re.MULTILINE)
    return inline + refs


def _normalize_reference(raw_ref: str) -> str:
    ref = raw_ref.strip().strip("<>").strip()
    for prefix in ("http://", "https://", "mailto:", "app://", "data:", "file://"):
        if ref.lower().startswith(prefix):
            return ""
    if not ref or ref.startswith("#"):
        return ""
    ref = ref.split("#", 1)[0].split("?", 1)[0].strip()
    return ref


def _check_jsonl(path: Path) -> tuple[bool, str]:
    try:
        for idx, line in enumerate(_load_text(path).splitlines(), start=1):
            if not line.strip():
                continue
            json.loads(line)
        return True, ""
    except Exception as e:
        return False, f"line {idx}: {e}"  # type: ignore[name-defined]


def _discover_context_files(root: Path) -> dict[str, list[Path]]:
    return {
        "agents": [root / "AGENTS.md"],
        "skills": sorted((root / "skills").glob("*/SKILL.md")),
        "memory": sorted((root / "memory").glob("*")),
        "policies": sorted((root / "policies").glob("*")),
        "evals": sorted((root / "evals").glob("*")),
    }


def validate_workspace(root: Path) -> dict[str, Any]:
    cfg = _load_config(root)
    files = _discover_context_files(root)
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            errors.append(f"{name}: {detail}")

    agents_path = root / "AGENTS.md"
    yare_path = root / "yare.yaml"
    check("agents_exists", agents_path.exists(), "present" if agents_path.exists() else "AGENTS.md missing")
    check("yare_config_exists", yare_path.exists(), "present" if yare_path.exists() else "yare.yaml missing")

    # Required folders for v1.
    for folder in ("skills", "memory", "policies", "evals", "receipts"):
        exists = (root / folder).is_dir()
        check(f"{folder}_dir_exists", exists, "present" if exists else f"{folder}/ directory missing")

    # Skills metadata + duplicates + forbidden permissions.
    required_meta = cfg.get("skills", {}).get("required_metadata", [])
    forbidden_permissions = set(cfg.get("skills", {}).get("forbidden_permissions", []))
    seen_skill_ids: dict[str, Path] = {}
    skill_files = files["skills"]
    if not skill_files:
        check("skills_present", False, "no skills/*/SKILL.md files found")
    else:
        check("skills_present", True, f"{len(skill_files)} skill files")
    skill_sources_for_links: list[Path] = []
    for skill_path in skill_files:
        skill_sources_for_links.append(skill_path)
        metadata, _ = _parse_front_matter(_load_text(skill_path))
        missing = [m for m in required_meta if m not in metadata]
        if missing:
            errors.append(f"skill_metadata_missing: {_relative(root, skill_path)} missing {missing}")
        skill_id = str(metadata.get("id", "")).strip()
        if skill_id:
            if skill_id in seen_skill_ids:
                errors.append(
                    "duplicate_skill_id: "
                    f"{skill_id} in {_relative(root, seen_skill_ids[skill_id])} and {_relative(root, skill_path)}"
                )
            else:
                seen_skill_ids[skill_id] = skill_path
        permissions = metadata.get("permissions", [])
        if isinstance(permissions, str):
            permissions = [permissions]
        if not isinstance(permissions, list):
            errors.append(f"skill_permissions_invalid: {_relative(root, skill_path)} permissions must be a list")
            permissions = []
        blocked = [p for p in permissions if p in forbidden_permissions]
        if blocked:
            errors.append(f"skill_forbidden_permissions: {_relative(root, skill_path)} requests {blocked}")

    dup_ok = not any(e.startswith("duplicate_skill_id:") for e in errors)
    check("duplicate_skill_ids", dup_ok, "none" if dup_ok else "duplicate skill IDs")
    check(
        "forbidden_skill_permissions",
        not any(e.startswith("skill_forbidden_permissions:") for e in errors),
        "none" if not any(e.startswith("skill_forbidden_permissions:") for e in errors) else "forbidden permissions requested",
    )

    # Policies YAML.
    for p in files["policies"]:
        if p.is_dir():
            continue
        if p.suffix.lower() not in {".yaml", ".yml"}:
            errors.append(f"policy_extension_invalid: {_relative(root, p)}")
            continue
        try:
            yaml.safe_load(_load_text(p))
        except Exception as e:
            errors.append(f"policy_yaml_invalid: {_relative(root, p)} ({e})")
    policies_ok = not any(e.startswith("policy_") for e in errors)
    check("policies_valid_yaml", policies_ok, "valid" if policies_ok else "invalid policy YAML")

    # Memory markdown.
    for m in files["memory"]:
        if m.is_dir():
            continue
        if m.suffix.lower() != ".md":
            errors.append(f"memory_extension_invalid: {_relative(root, m)}")
    memory_ok = not any(e.startswith("memory_extension_invalid:") for e in errors)
    check("memory_markdown_only", memory_ok, "valid" if memory_ok else "non-markdown memory file")

    # Evals JSONL.
    for efile in files["evals"]:
        if efile.is_dir():
            continue
        if efile.suffix.lower() != ".jsonl":
            errors.append(f"eval_extension_invalid: {_relative(root, efile)}")
            continue
        ok, detail = _check_jsonl(efile)
        if not ok:
            errors.append(f"eval_jsonl_invalid: {_relative(root, efile)} ({detail})")
    evals_ok = not any(e.startswith("eval_") for e in errors)
    check("evals_valid_jsonl", evals_ok, "valid" if evals_ok else "invalid eval JSONL")

    # Broken local references in AGENTS + SKILL + memory markdown files.
    link_sources = []
    if agents_path.exists():
        link_sources.append(agents_path)
    link_sources.extend(skill_sources_for_links)
    for m in files["memory"]:
        if m.is_file() and m.suffix.lower() == ".md":
            link_sources.append(m)

    broken_refs: list[str] = []
    for source in link_sources:
        content = _load_text(source)
        for raw_ref in _extract_markdown_links(content):
            ref = _normalize_reference(raw_ref)
            if not ref:
                continue
            target = Path(ref)
            if target.is_absolute():
                exists = target.exists()
            else:
                exists = (source.parent / target).resolve().exists()
            if not exists:
                broken_refs.append(f"{_relative(root, source)} -> {raw_ref}")
    if broken_refs:
        errors.append(f"broken_local_references: {broken_refs}")
    refs_ok = len(broken_refs) == 0
    check("no_broken_local_references", refs_ok, "none" if refs_ok else "broken local markdown links")

    # Oversized files.
    max_file_bytes = int(cfg.get("limits", {}).get("max_file_bytes", DEFAULT_CONFIG["limits"]["max_file_bytes"]))
    candidates: list[Path] = []
    if agents_path.exists():
        candidates.append(agents_path)
    candidates.extend([p for p in files["skills"] if p.is_file()])
    candidates.extend([p for p in files["memory"] if p.is_file()])
    candidates.extend([p for p in files["policies"] if p.is_file()])
    candidates.extend([p for p in files["evals"] if p.is_file()])
    oversized = [_relative(root, p) for p in candidates if p.stat().st_size > max_file_bytes]
    if oversized:
        errors.append(f"oversized_context_files: limit={max_file_bytes} files={oversized}")
    size_ok = len(oversized) == 0
    check("context_size_limits", size_ok, "within limit" if size_ok else "one or more context files exceed max_file_bytes")

    ok = len(errors) == 0
    return {
        "ok": ok,
        "checked_at": _utc_now_iso(),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "config": cfg,
        "stats": {
            "skills": len(files["skills"]),
            "memory_files": len([p for p in files["memory"] if p.is_file()]),
            "policies": len([p for p in files["policies"] if p.is_file()]),
            "evals": len([p for p in files["evals"] if p.is_file()]),
        },
    }


def _build_item(root: Path, path: Path, kind: str, reason: str, score: int) -> dict[str, Any]:
    size_bytes = path.stat().st_size if path.exists() else 0
    return {
        "path": _relative(root, path),
        "kind": kind,
        "score": score,
        "reason": reason,
        "size_bytes": size_bytes,
        "estimated_tokens": max(1, round(size_bytes / 4)),
        "sha256": _sha256_file(path) if path.exists() and path.is_file() else "",
    }


def resolve_context(root: Path, task: str, output_path: Path | None = None) -> tuple[dict[str, Any], Path]:
    cfg = _load_config(root)
    validation = validate_workspace(root)
    files = _discover_context_files(root)
    limits = cfg.get("resolve", {})
    max_file_bytes = int(cfg.get("limits", {}).get("max_file_bytes", DEFAULT_CONFIG["limits"]["max_file_bytes"]))
    max_total_bytes = int(cfg.get("limits", {}).get("max_total_bytes", DEFAULT_CONFIG["limits"]["max_total_bytes"]))
    task_tokens = _tokenize(task)

    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    # Always include AGENTS.md when present and within file size limit.
    agents_path = root / "AGENTS.md"
    if agents_path.exists():
        if agents_path.stat().st_size <= max_file_bytes:
            selected.append(_build_item(root, agents_path, "agents", "global_project_instruction_layer", score=999))
        else:
            excluded.append(_build_item(root, agents_path, "agents", "oversized_file", score=0))
    else:
        excluded.append({"path": "AGENTS.md", "kind": "agents", "score": 0, "reason": "missing_required_file"})

    def rank_group(paths: list[Path], kind: str, max_items: int, fallback_reason: str) -> None:
        ranked: list[tuple[int, Path]] = []
        for p in paths:
            if not p.is_file():
                continue
            if p.stat().st_size > max_file_bytes:
                excluded.append(_build_item(root, p, kind, "oversized_file", 0))
                continue
            text = _load_text(p)
            score = _score_text(task_tokens, text)
            ranked.append((score, p))

        ranked.sort(key=lambda x: (-x[0], _relative(root, x[1])))
        chosen: list[tuple[int, Path]] = []
        relevant = [item for item in ranked if item[0] > 0]
        if relevant:
            chosen = relevant[:max_items]
            leftovers = ranked[max_items:]
            for score, p in leftovers:
                reason = "selection_limit" if score > 0 else "score_below_threshold"
                excluded.append(_build_item(root, p, kind, reason, score))
        elif ranked:
            chosen = ranked[:1]
            score, p = chosen[0]
            selected.append(_build_item(root, p, kind, fallback_reason, score))
            for score, p in ranked[1:]:
                excluded.append(_build_item(root, p, kind, "score_below_threshold", score))

        for score, p in chosen:
            if any(item["path"] == _relative(root, p) for item in selected):
                continue
            selected.append(_build_item(root, p, kind, "task_keyword_match", score))

    rank_group(files["skills"], "skill", int(limits.get("max_skills", 6)), "baseline_skill_fallback")
    rank_group(files["memory"], "memory", int(limits.get("max_memory", 6)), "recent_memory_fallback")
    rank_group(files["policies"], "policy", int(limits.get("max_policies", 6)), "baseline_policy")
    rank_group(files["evals"], "eval", int(limits.get("max_evals", 4)), "baseline_eval")

    # Enforce global total size budget.
    total_bytes = sum(item.get("size_bytes", 0) for item in selected)
    if total_bytes > max_total_bytes:
        removable = [item for item in selected if item.get("kind") != "agents"]
        removable.sort(key=lambda i: (i.get("score", 0), i.get("size_bytes", 0)))
        for item in removable:
            if total_bytes <= max_total_bytes:
                break
            selected.remove(item)
            item["reason"] = "excluded_from_total_size_budget"
            excluded.append(item)
            total_bytes -= int(item.get("size_bytes", 0))

    output = {
        "version": "1",
        "generated_at": _utc_now_iso(),
        "task": task,
        "root": str(root.resolve()),
        "selected": selected,
        "excluded": excluded,
        "totals": {
            "selected_files": len(selected),
            "selected_bytes": sum(item.get("size_bytes", 0) for item in selected),
            "estimated_tokens": sum(int(item.get("estimated_tokens", 0)) for item in selected),
        },
        "validation": {"ok": validation["ok"], "errors": validation["errors"], "warnings": validation["warnings"]},
    }
    output["context_bundle_hash"] = _bundle_hash(selected)
    out_path = output_path if output_path is not None else Path(".yare/resolved-context.json")
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    resolved_out = out_path.resolve()
    _write_resolved_pointer(root, resolved_out)
    return output, resolved_out


def _run_git(root: Path, args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    except Exception as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").rstrip("\r\n")
    return True, proc.stdout.rstrip("\r\n")


def _git_state(root: Path) -> dict[str, Any]:
    ok, commit = _run_git(root, ["rev-parse", "HEAD"])
    if not ok:
        return {
            "available": False,
            "commit": None,
            "dirty": None,
            "changed_files": [],
            "untracked_files": [],
            "reason": "not_a_git_repository",
        }
    ok_status, status_out = _run_git(root, ["status", "--porcelain"])
    changed: list[str] = []
    untracked: list[str] = []
    dirty = None
    if ok_status:
        lines = [line for line in status_out.splitlines() if line.strip()]
        dirty = len(lines) > 0
        for line in lines:
            status_code = line[:2]
            payload = line[3:].strip()
            if "->" in payload:
                payload = payload.split("->", 1)[1].strip()
            normalized = payload.replace("\\", "/")
            if status_code == "??":
                untracked.append(normalized)
            else:
                changed.append(normalized)
    return {
        "available": True,
        "commit": commit,
        "dirty": dirty,
        "changed_files": changed,
        "untracked_files": untracked,
        "reason": None,
    }


def _load_resolved(root: Path) -> tuple[dict[str, Any] | None, Path | None]:
    candidates: list[Path] = []
    ptr_path = _read_resolved_pointer(root)
    if ptr_path is not None:
        candidates.append(ptr_path)
    candidates.append(root / ".yare" / "resolved-context.json")
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        if not path.exists():
            continue
        try:
            return json.loads(_load_text(path)), path.resolve()
        except Exception:
            continue
    return None, None


def write_receipt(
    root: Path,
    command_run: str,
    task: str | None = None,
    adapter: str | None = None,
    phase: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    validation = validate_workspace(root)
    resolved, resolved_path = _load_resolved(root)
    git = _git_state(root)

    selected_context: list[dict[str, Any]] = []
    detected_changes: list[str] = []
    if resolved:
        for item in resolved.get("selected", []):
            rel_path = item.get("path")
            if not rel_path:
                continue
            abs_path = root / rel_path
            current_hash = _sha256_file(abs_path) if abs_path.exists() and abs_path.is_file() else None
            selected_context.append({"path": rel_path, "sha256": current_hash})
            if item.get("sha256") and current_hash and item.get("sha256") != current_hash:
                detected_changes.append(rel_path)

    changed_files = git.get("changed_files") if git.get("available") else detected_changes
    untracked_files = git.get("untracked_files") if git.get("available") else []
    file_hashes = {item["path"]: item["sha256"] for item in selected_context if item.get("path")}
    context_bundle_hash = (resolved or {}).get("context_bundle_hash") if resolved else None
    if not context_bundle_hash:
        context_bundle_hash = _bundle_hash(selected_context)
    timestamp = datetime.now(timezone.utc)
    receipt = {
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "task": task if task is not None else (resolved or {}).get("task"),
        "adapter": adapter,
        "phase": phase,
        "command_run": command_run,
        "resolved_context_file": _display_path(root, resolved_path) if resolved_path else None,
        "selected_context_files": selected_context,
        "file_hashes": file_hashes,
        "context_bundle_hash": context_bundle_hash,
        "git_commit": git.get("commit"),
        "git_dirty": git.get("dirty"),
        "git_available": git.get("available"),
        "git_reason": git.get("reason"),
        "changed_files": changed_files,
        "untracked_files": untracked_files,
        "validation": {"ok": validation["ok"], "errors": validation["errors"], "warnings": validation["warnings"]},
    }
    receipt_material = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["receipt_hash"] = hashlib.sha256(receipt_material).hexdigest()

    receipts_dir = root / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    filename = timestamp.strftime("%Y%m%dT%H%M%S%fZ.jsonl")
    out_path = receipts_dir / filename
    out_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    return out_path, receipt


def _schema_candidates(root: Path, schema_file: str) -> list[Path]:
    return [
        root / schema_file,
        Path(__file__).resolve().parents[1] / schema_file,
    ]


def _load_json_schema(root: Path, schema_file: str, missing_code: str) -> dict[str, Any]:
    schema_path: Path | None = None
    for candidate in _schema_candidates(root, schema_file):
        if candidate.exists() and candidate.is_file():
            schema_path = candidate
            break
    if schema_path is None:
        wanted = ", ".join(_display_path(root, p) for p in _schema_candidates(root, schema_file))
        raise ValueError(f"{missing_code}: {wanted}")

    try:
        schema = json.loads(_load_text(schema_path))
    except Exception as e:
        raise ValueError(f"schema_invalid_json: {_display_path(root, schema_path)} ({e})") from e
    if not isinstance(schema, dict):
        raise ValueError(f"schema_invalid_shape: {_display_path(root, schema_path)}")
    return schema


def _require_jsonschema() -> Any:
    try:
        import jsonschema  # type: ignore
    except ImportError as e:
        raise ValueError("schema_dependency_missing: jsonschema is required; install requirements-cli.txt") from e
    return jsonschema


def _validate_json_payload(payload: dict[str, Any], schema: dict[str, Any], error_prefix: str) -> list[str]:
    jsonschema = _require_jsonschema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    out: list[str] = []
    for err in errors:
        if err.path:
            ptr = ".".join(str(part) for part in err.path)
        else:
            ptr = "$"
        out.append(f"{error_prefix} at {ptr} ({err.message})")
    return out


def _load_skill_edit_payload(root: Path, edit_path: Path) -> dict[str, Any]:
    path = edit_path if edit_path.is_absolute() else (root / edit_path)
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"skill_edit_missing: {_display_path(root, path)}")
    try:
        parsed = json.loads(_load_text(path))
    except Exception as e:
        raise ValueError(f"skill_edit_invalid_json: {_display_path(root, path)} ({e})") from e
    if not isinstance(parsed, dict):
        raise ValueError(f"skill_edit_invalid_shape: {_display_path(root, path)}")
    return parsed


def _apply_bounded_skill_edit(text: str, edit_type: str, target: str, replacement: str) -> str:
    occurrences = text.count(target)
    if occurrences == 0:
        raise ValueError("skill_edit_target_not_found")
    if occurrences > 1:
        raise ValueError(f"skill_edit_target_ambiguous: occurrences={occurrences}")

    if edit_type == "add":
        if not replacement:
            raise ValueError("skill_edit_invalid_replacement: add requires non-empty replacement")
        return text.replace(target, f"{target}{replacement}", 1)
    if edit_type == "delete":
        return text.replace(target, "", 1)
    if edit_type == "replace":
        if not replacement:
            raise ValueError("skill_edit_invalid_replacement: replace requires non-empty replacement")
        return text.replace(target, replacement, 1)
    raise ValueError(f"skill_edit_invalid_type: {edit_type}")


def _write_skill_gate_record(root: Path, relative_dir: str, record: dict[str, Any]) -> Path:
    out_dir = root / ".sticky" / relative_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_path = out_dir / f"{timestamp}.jsonl"
    out_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return out_path


def apply_skill_edit(root: Path, edit_path: Path) -> tuple[str, Path, dict[str, Any]]:
    edit_payload = _load_skill_edit_payload(root, edit_path)
    schema = _load_json_schema(root, SKILL_EDIT_SCHEMA_FILE, "skill_edit_schema_missing")
    schema_errors = _validate_json_payload(edit_payload, schema, "skill_edit_schema_invalid")
    if schema_errors:
        raise ValueError("; ".join(schema_errors))

    skill_path_raw = str(edit_payload.get("skill_path") or "").strip()
    if not skill_path_raw:
        raise ValueError("skill_edit_invalid_skill_path")
    skill_path = Path(skill_path_raw)
    skill_file = skill_path if skill_path.is_absolute() else (root / skill_path)
    skill_file = skill_file.resolve()
    if not skill_file.exists() or not skill_file.is_file():
        raise ValueError(f"skill_file_missing: {_display_path(root, skill_file)}")

    old_text = _load_text(skill_file)
    old_hash = _sha256_file(skill_file)

    edit_type = str(edit_payload.get("edit_type") or "").strip()
    target = str(edit_payload.get("target") or "")
    replacement_raw = edit_payload.get("replacement")
    replacement = "" if replacement_raw is None else str(replacement_raw)

    temp_parent = root / ".tmp" / "skill-edit-temp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="yare-skill-edit-", dir=temp_parent) as tmp_dir:
        tmp_path = Path(tmp_dir) / skill_file.name
        tmp_path.write_text(old_text, encoding="utf-8")
        new_text = _apply_bounded_skill_edit(old_text, edit_type, target, replacement)
        tmp_path.write_text(new_text, encoding="utf-8")
        proposed_hash = _sha256_file(tmp_path)

    baseline_score = float(edit_payload.get("baseline_score"))
    validation_score = float(edit_payload.get("validation_score"))
    score_delta = validation_score - baseline_score
    accepted = validation_score > baseline_score

    edit_material = json.dumps(edit_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    edit_hash = hashlib.sha256(edit_material).hexdigest()

    base_record = {
        "timestamp": _utc_now_iso(),
        "decision": "accepted" if accepted else "rejected",
        "schema_version": str(edit_payload.get("schema_version")),
        "skill_id": str(edit_payload.get("skill_id")),
        "skill_path": _display_path(root, skill_file),
        "edit_id": str(edit_payload.get("edit_id")),
        "edit_type": edit_type,
        "target": target,
        "replacement": replacement,
        "reason": str(edit_payload.get("reason") or ""),
        "baseline_score": baseline_score,
        "validation_score": validation_score,
        "score_delta": score_delta,
        "validation_task": str(edit_payload.get("validation_task") or ""),
        "evidence": edit_payload.get("evidence"),
        "proposed_by": str(edit_payload.get("proposed_by") or ""),
        "old_hash": old_hash,
        "new_hash": proposed_hash if accepted else old_hash,
        "proposed_new_hash": proposed_hash,
        "edit_hash": edit_hash,
    }

    if accepted:
        skill_file.write_text(new_text, encoding="utf-8")
        base_record["new_hash"] = _sha256_file(skill_file)
        receipt_path = _write_skill_gate_record(root, "skill-receipts", base_record)
        return "accepted", receipt_path, base_record

    rejection_path = _write_skill_gate_record(root, "rejected-skill-edits", base_record)
    return "rejected", rejection_path, base_record


LEAD_VERIFIED_STATUSES = {"verified", "true", "confirmed", "pass", "passed"}
LEAD_UNVERIFIED_STATUSES = {"unverified", "unknown", "pending", "needs_verification", "partial"}
LEAD_CONTRADICTORY_STATUSES = {"contradicted", "false", "failed", "fail", "rejected"}
LEAD_HUMAN_APPROVAL_STATUSES = {"needs_human_approval", "approval_required", "blocked"}


def _lead_status(value: Any) -> str:
    if isinstance(value, bool):
        return "verified" if value else "unverified"
    status = str(value or "").strip().lower().replace(" ", "_")
    if status in LEAD_VERIFIED_STATUSES:
        return "verified"
    if status in LEAD_CONTRADICTORY_STATUSES:
        return "contradicted"
    if status in LEAD_HUMAN_APPROVAL_STATUSES:
        return "needs_human_approval"
    if status in LEAD_UNVERIFIED_STATUSES:
        return "unverified"
    return "unknown"


def _lead_to_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        v = value.strip()
        return [v] if v else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("value") or "").strip()
            else:
                text = str(item).strip()
            if text:
                out.append(text)
        return out
    return []


def _lead_norm_path(path_value: str) -> str:
    return path_value.replace("\\", "/").strip()


def _lead_dedupe_sorted(items: list[str]) -> list[str]:
    return sorted({item for item in items if item})


def _lead_load_artifacts_from_file(root: Path, path: Path) -> tuple[list[tuple[dict[str, Any], str]], list[str]]:
    records: list[tuple[dict[str, Any], str]] = []
    warnings: list[str] = []
    source = _display_path(root, path)
    if not path.exists() or not path.is_file():
        warnings.append(f"artifact_missing: {source}")
        return records, warnings

    try:
        text = _load_text(path)
    except Exception as e:
        warnings.append(f"artifact_read_error: {source} ({e})")
        return records, warnings

    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        for idx, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception as e:
                warnings.append(f"artifact_jsonl_invalid: {source}:{idx} ({e})")
                continue
            if not isinstance(data, dict):
                warnings.append(f"artifact_record_not_object: {source}:{idx}")
                continue
            records.append((data, f"{source}:{idx}"))
        return records, warnings

    if suffix == ".json":
        try:
            parsed = json.loads(text)
        except Exception as e:
            warnings.append(f"artifact_json_invalid: {source} ({e})")
            return records, warnings
        if isinstance(parsed, dict):
            records.append((parsed, source))
        elif isinstance(parsed, list):
            for idx, item in enumerate(parsed, start=1):
                if isinstance(item, dict):
                    records.append((item, f"{source}:{idx}"))
                else:
                    warnings.append(f"artifact_record_not_object: {source}:{idx}")
        else:
            warnings.append(f"artifact_json_unsupported: {source}")
        return records, warnings

    warnings.append(f"artifact_extension_unsupported: {source}")
    return records, warnings


def _lead_schema_candidates(root: Path) -> list[Path]:
    # Prefer workspace-local schema, then fall back to the packaged repo schema.
    return [
        root / LEAD_ARTIFACT_SCHEMA_FILE,
        Path(__file__).resolve().parents[1] / LEAD_ARTIFACT_SCHEMA_FILE,
    ]


def _lead_load_schema(root: Path) -> dict[str, Any]:
    schema_path: Path | None = None
    for candidate in _lead_schema_candidates(root):
        if candidate.exists() and candidate.is_file():
            schema_path = candidate
            break
    if schema_path is None:
        wanted = ", ".join(_display_path(root, p) for p in _lead_schema_candidates(root))
        raise ValueError(f"lead_artifact_schema_missing: {wanted}")
    try:
        schema = json.loads(_load_text(schema_path))
    except Exception as e:
        raise ValueError(f"lead_artifact_schema_invalid_json: {_display_path(root, schema_path)} ({e})") from e
    if not isinstance(schema, dict):
        raise ValueError(f"lead_artifact_schema_invalid_shape: {_display_path(root, schema_path)}")
    return schema


def _lead_contract_payload(raw: dict[str, Any]) -> dict[str, Any]:
    claims = raw.get("claims")
    if claims is None:
        claims = raw.get("claims_made")
    if claims is None:
        claims = []

    decisions = raw.get("decisions")
    if decisions is None:
        decisions = raw.get("decisions_made")
    if decisions is None:
        decisions = []

    open_loops = raw.get("open_loops")
    if open_loops is None:
        open_loops = []

    contradictions = raw.get("contradictions")
    if contradictions is None:
        contradictions = []

    human_approval = raw.get("human_approval_items")
    if human_approval is None:
        human_approval = raw.get("needs_human_approval")
    if human_approval is None:
        human_approval = []

    git_state = raw.get("git_state")
    if not isinstance(git_state, dict):
        has_git_fields = any(
            raw.get(key) is not None
            for key in ("git_available", "git_commit", "git_dirty", "changed_files", "untracked_files", "git_reason")
        )
        if has_git_fields:
            available_value = raw.get("git_available")
            git_state = {
                "available": bool(available_value) if available_value is not None else False,
                "commit": raw.get("git_commit"),
                "dirty": raw.get("git_dirty"),
                "changed_files": _lead_to_str_list(raw.get("changed_files")),
                "untracked_files": _lead_to_str_list(raw.get("untracked_files")),
                "reason": raw.get("git_reason"),
            }
        else:
            git_state = None

    payload: dict[str, Any] = {
        "schema_version": str(raw.get("schema_version") or "").strip(),
        "run_id": str(raw.get("run_id") or raw.get("receipt_hash") or "").strip(),
        "tool": str(raw.get("tool") or raw.get("adapter") or raw.get("agent") or raw.get("chat") or "").strip(),
        "task": str(raw.get("task") or "").strip(),
        "timestamp": str(raw.get("timestamp") or raw.get("generated_at") or "").strip(),
        "claims": claims,
        "decisions": decisions,
        "files_touched": raw.get("files_touched") if raw.get("files_touched") is not None else [],
        "open_loops": open_loops,
        "contradictions": contradictions,
        "human_approval_items": human_approval,
        "verification_status": str(raw.get("verification_status") or "unknown"),
    }

    optional_map = {
        "context_bundle_hash": raw.get("context_bundle_hash"),
        "receipt_hash": raw.get("receipt_hash"),
        "source_artifacts": raw.get("source_artifacts"),
        "git_state": git_state,
    }
    for key, value in optional_map.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        payload[key] = value
    return payload


def _lead_validate_artifact_schema(root: Path, raw: dict[str, Any], source_ref: str) -> list[str]:
    schema = _lead_load_schema(root)
    payload = _lead_contract_payload(raw)

    try:
        import jsonschema  # type: ignore
    except ImportError as e:
        raise ValueError(
            "lead_artifact_schema_dependency_missing: jsonschema is required; install requirements-cli.txt"
        ) from e

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    out: list[str] = []
    for err in errors:
        if err.path:
            ptr = ".".join(str(part) for part in err.path)
        else:
            ptr = "$"
        out.append(f"lead_artifact_schema_invalid: {source_ref} at {ptr} ({err.message})")
    return out


def _lead_extract_files_touched(raw: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for key in ("files_touched", "changed_files", "untracked_files"):
        files.extend(_lead_to_str_list(raw.get(key)))

    selected_context = raw.get("selected_context_files")
    if isinstance(selected_context, list):
        for item in selected_context:
            if isinstance(item, dict):
                p = str(item.get("path") or "").strip()
                if p:
                    files.append(p)
            elif isinstance(item, str):
                p = item.strip()
                if p:
                    files.append(p)

    return _lead_dedupe_sorted([_lead_norm_path(p) for p in files])


def _lead_extract_claims(raw: dict[str, Any]) -> list[dict[str, str]]:
    raw_claims = raw.get("claims")
    if raw_claims is None:
        raw_claims = raw.get("claims_made")
    claims: list[dict[str, str]] = []
    if isinstance(raw_claims, list):
        for item in raw_claims:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    claims.append({"text": text, "verification_status": "unverified"})
            elif isinstance(item, dict):
                text = str(item.get("claim") or item.get("text") or item.get("message") or "").strip()
                if not text:
                    continue
                claims.append(
                    {
                        "text": text,
                        "verification_status": _lead_status(item.get("verification_status") or item.get("status")),
                    }
                )
    claims.sort(key=lambda x: (x["text"].lower(), x["verification_status"]))
    return claims


def _lead_extract_decisions(raw: dict[str, Any]) -> list[dict[str, Any]]:
    raw_decisions = raw.get("decisions")
    if raw_decisions is None:
        raw_decisions = raw.get("decisions_made")
    decisions: list[dict[str, Any]] = []
    if isinstance(raw_decisions, list):
        for item in raw_decisions:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    decisions.append({"text": text, "status": "unknown", "requires_human_approval": False})
            elif isinstance(item, dict):
                text = str(item.get("decision") or item.get("text") or item.get("message") or "").strip()
                if not text:
                    continue
                status = _lead_status(item.get("status") or item.get("verification_status"))
                requires_human_approval = bool(item.get("requires_human_approval")) or status == "needs_human_approval"
                decisions.append(
                    {
                        "text": text,
                        "status": status,
                        "requires_human_approval": requires_human_approval,
                    }
                )
    decisions.sort(key=lambda x: (x["text"].lower(), x["status"]))
    return decisions


def _lead_extract_open_loops(raw: dict[str, Any]) -> list[dict[str, str]]:
    loops_raw = raw.get("open_loops")
    loops: list[dict[str, str]] = []
    if isinstance(loops_raw, list):
        for item in loops_raw:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    loops.append({"text": text, "status": "open"})
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("loop") or item.get("item") or "").strip()
                if not text:
                    continue
                loops.append({"text": text, "status": str(item.get("status") or "open")})
    loops.sort(key=lambda x: (x["text"].lower(), x["status"]))
    return loops


def _lead_extract_contradictions(raw: dict[str, Any]) -> list[str]:
    raw_contradictions = raw.get("contradictions")
    out: list[str] = []
    if isinstance(raw_contradictions, list):
        for item in raw_contradictions:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("claim") or item.get("message") or "").strip()
            else:
                text = ""
            if text:
                out.append(text)
    return _lead_dedupe_sorted(out)


def _lead_extract_git_state(raw: dict[str, Any]) -> dict[str, Any]:
    git_state = raw.get("git_state")
    if isinstance(git_state, dict):
        return {
            "available": bool(git_state.get("available", True)),
            "commit": git_state.get("commit"),
            "dirty": git_state.get("dirty"),
            "changed_files": _lead_to_str_list(git_state.get("changed_files")),
            "untracked_files": _lead_to_str_list(git_state.get("untracked_files")),
            "reason": git_state.get("reason"),
        }
    return {
        "available": bool(raw.get("git_available", False)),
        "commit": raw.get("git_commit"),
        "dirty": raw.get("git_dirty"),
        "changed_files": _lead_to_str_list(raw.get("changed_files")),
        "untracked_files": _lead_to_str_list(raw.get("untracked_files")),
        "reason": raw.get("git_reason"),
    }


def _lead_normalize_artifact(raw: dict[str, Any], source_ref: str, index: int) -> dict[str, Any]:
    claims = _lead_extract_claims(raw)
    decisions = _lead_extract_decisions(raw)
    open_loops = _lead_extract_open_loops(raw)
    contradictions = _lead_extract_contradictions(raw)

    task = str(raw.get("task") or "").strip()
    timestamp = str(raw.get("timestamp") or raw.get("generated_at") or "").strip()
    adapter = str(raw.get("adapter") or raw.get("tool") or raw.get("chat") or raw.get("agent") or "").strip()
    verification_status = _lead_status(raw.get("verification_status") or ((raw.get("validation") or {}).get("ok")))

    needs_human_approval = _lead_to_str_list(raw.get("human_approval_items"))
    needs_human_approval.extend(_lead_to_str_list(raw.get("needs_human_approval")))
    needs_human_approval.extend(d["text"] for d in decisions if d.get("requires_human_approval"))
    needs_human_approval = _lead_dedupe_sorted(needs_human_approval)

    run_id = str(raw.get("run_id") or "").strip()
    if not run_id:
        run_id = str(raw.get("receipt_hash") or "").strip()
    if not run_id:
        material = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
        run_id = hashlib.sha256(material + f"{source_ref}:{index}".encode("utf-8")).hexdigest()[:16]

    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "source_artifact": source_ref,
        "task": task or None,
        "adapter": adapter or None,
        "files_touched": _lead_extract_files_touched(raw),
        "claims_made": claims,
        "decisions_made": decisions,
        "open_loops": open_loops,
        "contradictions": contradictions,
        "needs_human_approval": needs_human_approval,
        "verification_status": verification_status,
        "context_bundle_hash": str(raw.get("context_bundle_hash") or "") or None,
        "receipt_hash": str(raw.get("receipt_hash") or "") or None,
        "source_artifacts": _lead_to_str_list(raw.get("source_artifacts")),
        "git_state": _lead_extract_git_state(raw),
    }


def _lead_collect_artifact_paths(root: Path, explicit: list[Path]) -> list[Path]:
    if explicit:
        out = []
        for p in explicit:
            path = p if p.is_absolute() else (root / p)
            out.append(path.resolve())
        unique = sorted({str(p): p for p in out}.values(), key=lambda p: str(p).lower())
        return unique

    discovered: list[Path] = []
    discovered.extend(sorted((root / "receipts").glob("*.jsonl")))
    discovered.extend(sorted((root / ".sticky" / "receipts").glob("*.jsonl")))
    resolved = root / ".yare" / "resolved-context.json"
    if resolved.exists():
        discovered.append(resolved)
    unique = sorted({str(p.resolve()): p.resolve() for p in discovered}.values(), key=lambda p: str(p).lower())
    return unique


def _lead_compile_packet(root: Path, artifacts: list[dict[str, Any]], task_override: str | None) -> dict[str, Any]:
    validation = validate_workspace(root)

    if not artifacts:
        default_task = (task_override or "").strip()
        synthetic_id_source = default_task or "no-artifacts"
        synthetic = {
            "run_id": hashlib.sha256(synthetic_id_source.encode("utf-8")).hexdigest()[:16],
            "timestamp": "",
            "source_artifact": "none",
            "task": default_task or None,
            "adapter": None,
            "files_touched": [],
            "claims_made": [],
            "decisions_made": [],
            "open_loops": [],
            "contradictions": [],
            "needs_human_approval": [],
            "verification_status": "unknown",
            "context_bundle_hash": None,
            "receipt_hash": None,
            "git_state": {
                "available": False,
                "commit": None,
                "dirty": None,
                "changed_files": [],
                "untracked_files": [],
                "reason": "no_artifacts",
            },
        }
        artifacts = [synthetic]

    artifacts_sorted = sorted(
        artifacts,
        key=lambda a: (str(a.get("timestamp") or ""), str(a.get("run_id") or ""), str(a.get("source_artifact") or "")),
    )

    task_candidates = [str(a.get("task") or "").strip() for a in artifacts_sorted if a.get("task")]
    task = (task_override or "").strip() or (task_candidates[-1] if task_candidates else "unspecified task")

    changed_files = _lead_dedupe_sorted([p for a in artifacts_sorted for p in a.get("files_touched", [])])

    claim_statuses: dict[str, set[str]] = {}
    claim_original: dict[str, str] = {}
    true_claims: list[str] = []
    unverified_claims: list[str] = []
    contradictions: list[str] = []

    for artifact in artifacts_sorted:
        for claim in artifact.get("claims_made", []):
            text = str(claim.get("text") or "").strip()
            if not text:
                continue
            status = _lead_status(claim.get("verification_status"))
            key = text.lower()
            claim_statuses.setdefault(key, set()).add(status)
            claim_original.setdefault(key, text)
            if status == "verified":
                true_claims.append(text)
            elif status in {"unverified", "unknown"}:
                unverified_claims.append(text)
            elif status == "contradicted":
                contradictions.append(text)

    for key, statuses in claim_statuses.items():
        if "verified" in statuses and ("contradicted" in statuses or "unverified" in statuses or "unknown" in statuses):
            contradictions.append(claim_original[key])

    contradictions.extend([c for a in artifacts_sorted for c in a.get("contradictions", [])])

    open_loops_map: dict[str, dict[str, str]] = {}
    for artifact in artifacts_sorted:
        for loop in artifact.get("open_loops", []):
            text = str(loop.get("text") or "").strip()
            if not text:
                continue
            key = text.lower()
            open_loops_map[key] = {"text": text, "status": str(loop.get("status") or "open")}
    open_loops = sorted(open_loops_map.values(), key=lambda x: (x["text"].lower(), x["status"]))

    needs_human_approval = []
    for artifact in artifacts_sorted:
        needs_human_approval.extend(artifact.get("needs_human_approval", []))
    needs_human_approval = _lead_dedupe_sorted(needs_human_approval)
    contradictions = _lead_dedupe_sorted(contradictions)
    if contradictions:
        needs_human_approval.extend([f"Resolve contradiction: {c}" for c in contradictions])
        needs_human_approval = _lead_dedupe_sorted(needs_human_approval)

    true_claims = _lead_dedupe_sorted(true_claims)
    unverified_claims = _lead_dedupe_sorted(unverified_claims)

    next_clean_action = "Proceed to the next scoped task."
    if needs_human_approval:
        next_clean_action = "Resolve human-approval items before the next run."
    elif contradictions:
        next_clean_action = "Resolve contradictions and update verified state."
    elif unverified_claims:
        next_clean_action = "Verify unverified claims."
    elif open_loops:
        next_clean_action = f"Close open loop: {open_loops[0]['text']}"

    latest = artifacts_sorted[-1]
    latest_context_bundle_hash = None
    latest_receipt_hash = None
    for artifact in reversed(artifacts_sorted):
        if artifact.get("context_bundle_hash") and latest_context_bundle_hash is None:
            latest_context_bundle_hash = artifact.get("context_bundle_hash")
        if artifact.get("receipt_hash") and latest_receipt_hash is None:
            latest_receipt_hash = artifact.get("receipt_hash")

    latest_git_state = latest.get("git_state") or {}
    if not isinstance(latest_git_state, dict) or (
        latest_git_state.get("commit") is None and latest_git_state.get("dirty") is None and not latest_git_state.get("available")
    ):
        live_git = _git_state(root)
        latest_git_state = {
            "available": live_git.get("available"),
            "commit": live_git.get("commit"),
            "dirty": live_git.get("dirty"),
            "changed_files": live_git.get("changed_files"),
            "untracked_files": live_git.get("untracked_files"),
            "reason": live_git.get("reason"),
        }

    packet = {
        "version": "0.2",
        "primitive": "ai_work_lead",
        "task": task,
        "artifacts_ingested": len(artifacts_sorted),
        "artifact_sources": sorted({str(a.get("source_artifact") or "") for a in artifacts_sorted if a.get("source_artifact")}),
        "artifacts": artifacts_sorted,
        "current_state": {
            "what_changed": changed_files,
            "what_is_true": true_claims,
            "what_is_unverified": unverified_claims,
            "what_contradicts_prior_state": contradictions,
            "what_needs_human_approval": needs_human_approval,
            "open_loops": open_loops,
            "next_clean_action": next_clean_action,
        },
        "proof": {
            "run_id": latest.get("run_id"),
            "timestamp": latest.get("timestamp"),
            "context_bundle_hash": latest_context_bundle_hash,
            "receipt_hash": latest_receipt_hash,
            "source_artifacts": sorted({str(a.get("source_artifact") or "") for a in artifacts_sorted if a.get("source_artifact")}),
            "git_state": {
                "available": latest_git_state.get("available"),
                "commit": latest_git_state.get("commit"),
                "dirty": latest_git_state.get("dirty"),
                "changed_files": _lead_dedupe_sorted(_lead_to_str_list(latest_git_state.get("changed_files"))),
                "untracked_files": _lead_dedupe_sorted(_lead_to_str_list(latest_git_state.get("untracked_files"))),
                "reason": latest_git_state.get("reason"),
            },
        },
        "validation": {
            "ok": validation["ok"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        },
    }

    material = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
    packet["deterministic_hash"] = hashlib.sha256(material).hexdigest()
    return packet


def _lead_current_state_markdown(packet: dict[str, Any]) -> str:
    current = packet.get("current_state", {})
    proof = packet.get("proof", {})
    git_state = proof.get("git_state", {})

    def lines_for_list(title: str, items: list[str]) -> list[str]:
        out = [f"## {title}"]
        if items:
            out.extend([f"- {item}" for item in items])
        else:
            out.append("- none")
        out.append("")
        return out

    md: list[str] = [
        "# Sticky Current State",
        "",
        f"Task: {packet.get('task')}",
        f"Deterministic Hash: {packet.get('deterministic_hash')}",
        f"Artifacts Ingested: {packet.get('artifacts_ingested')}",
        "",
    ]

    md.extend(lines_for_list("What Changed", current.get("what_changed", [])))
    md.extend(lines_for_list("What Is True", current.get("what_is_true", [])))
    md.extend(lines_for_list("What Is Unverified", current.get("what_is_unverified", [])))
    md.extend(lines_for_list("What Contradicts Prior State", current.get("what_contradicts_prior_state", [])))
    md.extend(lines_for_list("What Needs Human Approval", current.get("what_needs_human_approval", [])))

    md.append("## Open Loops")
    open_loops = current.get("open_loops", [])
    if open_loops:
        for loop in open_loops:
            md.append(f"- {loop.get('text')} ({loop.get('status')})")
    else:
        md.append("- none")
    md.append("")

    md.append("## Next Clean Action")
    md.append(f"- {current.get('next_clean_action')}")
    md.append("")

    md.append("## Proof")
    md.append(f"- run_id: {proof.get('run_id')}")
    md.append(f"- timestamp: {proof.get('timestamp')}")
    md.append(f"- context_bundle_hash: {proof.get('context_bundle_hash')}")
    md.append(f"- receipt_hash: {proof.get('receipt_hash')}")
    md.append(f"- git_commit: {git_state.get('commit')}")
    md.append(f"- git_dirty: {git_state.get('dirty')}")
    md.append(f"- changed_files: {', '.join(git_state.get('changed_files', [])) or 'none'}")
    md.append(f"- untracked_files: {', '.join(git_state.get('untracked_files', [])) or 'none'}")
    md.append("")

    md.append("## Validation")
    validation = packet.get("validation", {})
    md.append(f"- status: {'PASS' if validation.get('ok') else 'FAIL'}")
    for err in validation.get("errors", []):
        md.append(f"- error: {err}")
    if not validation.get("errors"):
        md.append("- errors: none")

    return "\n".join(md).rstrip() + "\n"


def _lead_write_receipt(root: Path, packet: dict[str, Any], command_run: str) -> tuple[Path, dict[str, Any]]:
    proof = packet.get("proof", {})
    git_state = proof.get("git_state", {})
    timestamp = datetime.now(timezone.utc)
    receipt = {
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "run_id": proof.get("run_id"),
        "task": packet.get("task"),
        "command_run": command_run,
        "context_bundle_hash": proof.get("context_bundle_hash"),
        "receipt_hash_source": proof.get("receipt_hash"),
        "current_state_hash": packet.get("deterministic_hash"),
        "source_artifacts": proof.get("source_artifacts", []),
        "git_commit": git_state.get("commit"),
        "git_dirty": git_state.get("dirty"),
        "git_available": git_state.get("available"),
        "git_reason": git_state.get("reason"),
        "changed_files": git_state.get("changed_files", []),
        "untracked_files": git_state.get("untracked_files", []),
        "validation_ok": (packet.get("validation") or {}).get("ok"),
        "validation_errors": (packet.get("validation") or {}).get("errors", []),
    }
    material = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["receipt_hash"] = hashlib.sha256(material).hexdigest()

    receipts_dir = root / ".sticky" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    filename = timestamp.strftime("%Y%m%dT%H%M%S%fZ.jsonl")
    out_path = receipts_dir / filename
    out_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    return out_path, receipt


def compile_lead_state(
    root: Path,
    task_override: str | None,
    artifact_paths: list[Path],
    validate_artifacts: bool = False,
) -> tuple[dict[str, Any], Path, Path, Path, dict[str, Any], list[str]]:
    artifacts: list[dict[str, Any]] = []
    warnings: list[str] = []
    schema_errors: list[str] = []
    for artifact_path in _lead_collect_artifact_paths(root, artifact_paths):
        loaded_records, loaded_warnings = _lead_load_artifacts_from_file(root, artifact_path)
        warnings.extend(loaded_warnings)
        for idx, (raw, source_ref) in enumerate(loaded_records, start=1):
            if validate_artifacts:
                try:
                    schema_errors.extend(_lead_validate_artifact_schema(root, raw, source_ref))
                except ValueError as e:
                    schema_errors.append(str(e))
            artifacts.append(_lead_normalize_artifact(raw, source_ref=source_ref, index=idx))

    if validate_artifacts and warnings:
        raise ValueError("; ".join(warnings))

    if validate_artifacts and not artifacts:
        raise ValueError("lead_artifact_input_empty: no valid artifact records loaded")

    if schema_errors:
        raise ValueError("; ".join(schema_errors))

    packet = _lead_compile_packet(root, artifacts, task_override)
    if warnings:
        validation = packet.get("validation")
        if isinstance(validation, dict):
            current_warnings = validation.get("warnings")
            if isinstance(current_warnings, list):
                merged = sorted({*current_warnings, *warnings})
                validation["warnings"] = merged

    sticky_dir = root / ".sticky"
    sticky_dir.mkdir(parents=True, exist_ok=True)
    json_path = sticky_dir / "current-state.json"
    md_path = sticky_dir / "current-state.md"
    json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    md_path.write_text(_lead_current_state_markdown(packet), encoding="utf-8")

    receipt_path, receipt = _lead_write_receipt(root, packet, command_run="yare lead compile")
    storage_backend.persist_lead_compile(packet=packet, artifacts=artifacts, receipt=receipt)
    s3_uris = archive_backend.archive_lead_compile(
        packet=packet,
        json_path=json_path,
        md_path=md_path,
        receipt_path=receipt_path,
    )
    return packet, json_path, md_path, receipt_path, receipt, s3_uris


@storage_app.command("init")
def storage_init() -> None:
    try:
        storage_backend.init_schema()
    except storage_backend.StorageError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)
    typer.echo("storage: initialized")
    typer.echo(f"tables: {', '.join(storage_backend.SCHEMA_TABLES)}")


@memory_app.command("search")
def memory_search(
    query: str = typer.Option(..., "--query", help="Search query for prior agent memory"),
    limit: int = typer.Option(3, "--limit", min=1, help="Maximum results to return"),
) -> None:
    try:
        results = storage_backend.search_memory(query=query, limit=limit)
    except storage_backend.StorageError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)

    if not results:
        typer.echo("memory_search: no results")
        return

    for idx, result in enumerate(results, start=1):
        typer.echo(f"result: {idx}")
        typer.echo(f"section: {result['section_name']}")
        typer.echo(f"distance: {result['distance']:.6f}")
        typer.echo(f"current_state_hash: {result['current_state_hash']}")
        typer.echo("text:")
        typer.echo(str(result["source_text"]))
        if idx != len(results):
            typer.echo("")


@memory_app.command("timeline")
def memory_timeline(
    limit: int = typer.Option(25, "--limit", min=1, help="Maximum timeline states to print"),
) -> None:
    try:
        rows = storage_backend.memory_timeline(limit=limit)
    except storage_backend.StorageError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)

    if not rows:
        typer.echo("memory_timeline: no states")
        return

    for row in rows:
        typer.echo(f"state_hash: {row['state_hash']}")
        typer.echo(f"created_at: {row['created_at']}")
        typer.echo(f"task: {row['task']}")
        typer.echo(f"run_id: {row['run_id']}")
        typer.echo(f"receipt_hash: {row['receipt_hash']}")
        typer.echo(f"changed_files_count: {row['changed_files_count']}")
        typer.echo(f"verified_facts_count: {row['verified_facts_count']}")
        typer.echo(f"unresolved_claims_count: {row['unresolved_claims_count']}")
        typer.echo(f"contradictions_count: {row['contradictions_count']}")
        typer.echo(f"human_approval_count: {row['human_approval_count']}")
        typer.echo(f"next_clean_action: {row['next_clean_action']}")
        if row != rows[-1]:
            typer.echo("")


def _echo_list(title: str, items: list[str]) -> None:
    typer.echo(f"{title}:")
    if items:
        for item in items:
            typer.echo(f"- {item}")
    else:
        typer.echo("- none")


@memory_app.command("diff")
def memory_diff(
    latest: bool = typer.Option(False, "--latest", help="Compare latest current state to the previous one"),
) -> None:
    if not latest:
        typer.echo("memory_diff_requires_latest: pass --latest")
        raise typer.Exit(code=1)

    try:
        diff = storage_backend.latest_memory_diff()
    except storage_backend.StorageError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)

    typer.echo(f"previous_state_hash: {diff['previous_state_hash']}")
    typer.echo(f"latest_state_hash: {diff['latest_state_hash']}")
    _echo_list("new_truths", diff["new_truths"])
    _echo_list("removed_truths", diff["removed_truths"])
    _echo_list("still_unresolved", diff["still_unresolved"])
    _echo_list("new_unresolved_claims", diff["new_unresolved_claims"])
    _echo_list("resolved_claims", diff["resolved_claims"])
    _echo_list("new_contradictions", diff["new_contradictions"])
    _echo_list("cleared_contradictions", diff["cleared_contradictions"])
    _echo_list("new_approval_items", diff["new_approval_items"])
    if diff["next_clean_action_changed"]:
        typer.echo(
            "next_clean_action_changed: "
            f"{diff['next_clean_action_previous']} -> {diff['next_clean_action_latest']}"
        )
    else:
        typer.echo(f"next_clean_action_changed: no ({diff['next_clean_action_latest']})")


@lead_app.command("compile")
def lead_compile(
    root: Path = typer.Option(Path("."), "--root", help="Workspace root"),
    task: str | None = typer.Option(None, "--task", help="Optional task override for current-state packet"),
    artifact: list[Path] = typer.Option(None, "--artifact", help="Artifact file (.json or .jsonl). Repeat to include multiple files."),
    json_output: bool = typer.Option(False, "--json", help="Print compiled current-state JSON"),
) -> None:
    root = root.resolve()
    artifact_paths = artifact or []
    try:
        packet, json_path, md_path, receipt_path, receipt, s3_uris = compile_lead_state(
            root,
            task_override=task,
            artifact_paths=artifact_paths,
            validate_artifacts=bool(artifact_paths),
        )
    except (ValueError, storage_backend.StorageError, archive_backend.ArchiveError) as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(packet, indent=2))
        return

    typer.echo(f"current_state_json: {_display_path(root, json_path)}")
    typer.echo(f"current_state_md: {_display_path(root, md_path)}")
    typer.echo(f"deterministic_hash: {packet['deterministic_hash']}")
    typer.echo(f"receipt: {_display_path(root, receipt_path)}")
    typer.echo(f"receipt_hash: {receipt['receipt_hash']}")
    for uri in s3_uris:
        typer.echo(f"s3_uri: {uri}")


@skill_app.command("apply-edit")
def skill_apply_edit(
    edit: Path = typer.Option(..., "--edit", help="Path to skill edit JSON payload"),
    root: Path = typer.Option(Path("."), "--root", help="Workspace root"),
) -> None:
    root = root.resolve()
    try:
        decision, record_path, record = apply_skill_edit(root, edit)
    except ValueError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1)

    typer.echo(f"decision: {decision}")
    typer.echo(f"skill_path: {record['skill_path']}")
    typer.echo(f"record: {_display_path(root, record_path)}")
    typer.echo(f"score_delta: {record['score_delta']}")
    typer.echo(f"edit_hash: {record['edit_hash']}")


@app.command()
def doctor(
    root: Path = typer.Option(Path("."), "--root", help="Workspace root"),
    json_output: bool = typer.Option(False, "--json", help="Print full JSON output"),
) -> None:
    root = root.resolve()
    result = validate_workspace(root)
    if json_output:
        typer.echo(json.dumps(result, indent=2))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        typer.echo(f"doctor: {status}")
        for check in result["checks"]:
            marker = "ok" if check["ok"] else "err"
            typer.echo(f"- [{marker}] {check['name']} {check['detail']}".rstrip())
        if result["errors"]:
            typer.echo("errors:")
            for err in result["errors"]:
                typer.echo(f"- {err}")
    raise typer.Exit(code=0 if result["ok"] else 1)


@app.command()
def resolve(
    task: str = typer.Option(..., "--task", help="Task to resolve context for"),
    root: Path = typer.Option(Path("."), "--root", help="Workspace root"),
    output: Path = typer.Option(Path(".yare/resolved-context.json"), "--output", help="Resolved context output path"),
    json_output: bool = typer.Option(False, "--json", help="Print resolved context as JSON"),
) -> None:
    root = root.resolve()
    resolved, out_path = resolve_context(root, task, output_path=output)
    if json_output:
        typer.echo(json.dumps(resolved, indent=2))
        return
    typer.echo(f"resolved_context: {_display_path(root, out_path)}")
    typer.echo(f"context_bundle_hash: {resolved['context_bundle_hash']}")
    typer.echo(f"selected_files: {resolved['totals']['selected_files']}")
    typer.echo(f"estimated_tokens: {resolved['totals']['estimated_tokens']}")


@app.command()
def receipt(
    root: Path = typer.Option(Path("."), "--root", help="Workspace root"),
    task: str | None = typer.Option(None, "--task", help="Override task in receipt"),
    adapter: str | None = typer.Option(None, "--adapter", help="Adapter value to record"),
) -> None:
    root = root.resolve()
    out_path, data = write_receipt(root, command_run="yare receipt", task=task, adapter=adapter)
    typer.echo(f"receipt: {_relative(root, out_path)}")
    typer.echo(f"receipt_hash: {data['receipt_hash']}")


@app.command()
def run(
    adapter: str = typer.Option(..., "--adapter", help="Adapter to launch: codex|claude|gemini"),
    task: str = typer.Option(..., "--task", help="Task to execute"),
    root: Path = typer.Option(Path("."), "--root", help="Workspace root"),
) -> None:
    root = root.resolve()
    adapter = adapter.lower().strip()
    if adapter not in ADAPTER_INSTRUCTIONS:
        raise typer.BadParameter("adapter must be one of: codex, claude, gemini")

    resolve_context(root, task)
    write_receipt(root, command_run=f"yare run --adapter {adapter} --task {task}", task=task, adapter=adapter, phase="pre")

    context_file = ".yare/resolved-context.json"
    launch = ADAPTER_INSTRUCTIONS[adapter].format(task=task.replace('"', '\\"'), context_file=context_file)
    typer.echo("yare run v1 does not execute adapters yet.")
    typer.echo(f"launch_instruction: {launch}")

    out_path, data = write_receipt(
        root,
        command_run=f"yare run --adapter {adapter} --task {task}",
        task=task,
        adapter=adapter,
        phase="post",
    )
    typer.echo(f"receipt: {_relative(root, out_path)}")
    typer.echo(f"receipt_hash: {data['receipt_hash']}")


if __name__ == "__main__":
    app()
