#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
import yaml

app = typer.Typer(add_completion=False, help="AgentMD context governance runtime CLI")

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


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)  # type: ignore[index]
        else:
            out[k] = v
    return out


def _load_config(root: Path) -> dict[str, Any]:
    path = root / "agentmd.yaml"
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
    agentmd_path = root / "agentmd.yaml"
    check("agents_exists", agents_path.exists(), "present" if agents_path.exists() else "AGENTS.md missing")
    check("agentmd_config_exists", agentmd_path.exists(), "present" if agentmd_path.exists() else "agentmd.yaml missing")

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


def resolve_context(root: Path, task: str) -> dict[str, Any]:
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
    out_path = root / ".agentmd" / "resolved-context.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def _run_git(root: Path, args: list[str]) -> tuple[bool, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    except Exception as e:
        return False, str(e)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()
    return True, proc.stdout.strip()


def _git_state(root: Path) -> dict[str, Any]:
    ok, commit = _run_git(root, ["rev-parse", "HEAD"])
    if not ok:
        return {
            "available": False,
            "commit": None,
            "dirty": None,
            "changed_files": [],
            "reason": "not_a_git_repository",
        }
    ok_status, status_out = _run_git(root, ["status", "--porcelain"])
    changed: list[str] = []
    dirty = None
    if ok_status:
        lines = [line for line in status_out.splitlines() if line.strip()]
        dirty = len(lines) > 0
        for line in lines:
            payload = line[3:].strip()
            if "->" in payload:
                payload = payload.split("->", 1)[1].strip()
            changed.append(payload.replace("\\", "/"))
    return {"available": True, "commit": commit, "dirty": dirty, "changed_files": changed, "reason": None}


def _load_resolved(root: Path) -> dict[str, Any] | None:
    path = root / ".agentmd" / "resolved-context.json"
    if not path.exists():
        return None
    try:
        return json.loads(_load_text(path))
    except Exception:
        return None


def write_receipt(
    root: Path,
    command_run: str,
    task: str | None = None,
    adapter: str | None = None,
    phase: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    validation = validate_workspace(root)
    resolved = _load_resolved(root)
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
    timestamp = datetime.now(timezone.utc)
    receipt = {
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "task": task if task is not None else (resolved or {}).get("task"),
        "adapter": adapter,
        "phase": phase,
        "command_run": command_run,
        "resolved_context_file": ".agentmd/resolved-context.json" if resolved else None,
        "selected_context_files": selected_context,
        "git_commit": git.get("commit"),
        "git_dirty": git.get("dirty"),
        "git_available": git.get("available"),
        "git_reason": git.get("reason"),
        "changed_files": changed_files,
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
) -> None:
    root = root.resolve()
    output = resolve_context(root, task)
    out_path = root / ".agentmd" / "resolved-context.json"
    typer.echo(f"resolved_context: {_relative(root, out_path)}")
    typer.echo(f"selected_files: {output['totals']['selected_files']}")
    typer.echo(f"estimated_tokens: {output['totals']['estimated_tokens']}")


@app.command()
def receipt(
    root: Path = typer.Option(Path("."), "--root", help="Workspace root"),
    task: str | None = typer.Option(None, "--task", help="Override task in receipt"),
    adapter: str | None = typer.Option(None, "--adapter", help="Adapter value to record"),
) -> None:
    root = root.resolve()
    out_path, data = write_receipt(root, command_run="agentmd receipt", task=task, adapter=adapter)
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
    write_receipt(root, command_run=f"agentmd run --adapter {adapter} --task {task}", task=task, adapter=adapter, phase="pre")

    context_file = ".agentmd/resolved-context.json"
    launch = ADAPTER_INSTRUCTIONS[adapter].format(task=task.replace('"', '\\"'), context_file=context_file)
    typer.echo("agentmd run v1 does not execute adapters yet.")
    typer.echo(f"launch_instruction: {launch}")

    out_path, data = write_receipt(
        root,
        command_run=f"agentmd run --adapter {adapter} --task {task}",
        task=task,
        adapter=adapter,
        phase="post",
    )
    typer.echo(f"receipt: {_relative(root, out_path)}")
    typer.echo(f"receipt_hash: {data['receipt_hash']}")


if __name__ == "__main__":
    app()
