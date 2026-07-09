from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Callable

DATABASE_URL_ENV = "YARE_DATABASE_URL"
VECTOR_DIMENSIONS = 32

SCHEMA_TABLES = (
    "yare_runs",
    "yare_lead_artifacts",
    "yare_current_states",
    "yare_receipts",
    "yare_memory_vectors",
)

SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS yare_runs (
        run_id TEXT PRIMARY KEY,
        task TEXT NOT NULL,
        current_state_hash TEXT NOT NULL,
        compiled_state_json JSONB NOT NULL,
        source_artifact_hashes JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS yare_lead_artifacts (
        run_id TEXT NOT NULL REFERENCES yare_runs (run_id) ON DELETE CASCADE,
        source_artifact TEXT NOT NULL,
        artifact_hash TEXT NOT NULL,
        artifact_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (run_id, source_artifact)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS yare_current_states (
        current_state_hash TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES yare_runs (run_id) ON DELETE CASCADE,
        state_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS yare_receipts (
        receipt_hash TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES yare_runs (run_id) ON DELETE CASCADE,
        current_state_hash TEXT NOT NULL,
        receipt_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS yare_memory_vectors (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id TEXT NOT NULL REFERENCES yare_runs (run_id) ON DELETE CASCADE,
        current_state_hash TEXT NOT NULL,
        section_name TEXT NOT NULL,
        source_text TEXT NOT NULL,
        embedding VECTOR({VECTOR_DIMENSIONS}) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (current_state_hash, section_name),
        VECTOR INDEX yare_memory_vectors_embedding_idx (embedding vector_cosine_ops)
    )
    """,
)

SECTION_KEYS = (
    ("what changed", "what_changed"),
    ("what is true", "what_is_true"),
    ("what is unverified", "what_is_unverified"),
    ("contradictions", "what_contradicts_prior_state"),
    ("human approval items", "what_needs_human_approval"),
    ("open loops", "open_loops"),
    ("next clean action", "next_clean_action"),
)

TOKEN_SYNONYMS = {
    "review": ("approval", "human"),
    "reviews": ("approval", "human"),
    "approved": ("approval",),
    "unresolved": ("unverified", "contradictions", "open"),
    "pending": ("open", "approval"),
    "todo": ("next", "action"),
    "handoff": ("memory", "state"),
    "claim": ("fact", "true", "unverified"),
    "claims": ("fact", "true", "unverified"),
}


class StorageError(RuntimeError):
    pass


def _database_url(explicit_url: str | None = None) -> str | None:
    return explicit_url or os.environ.get(DATABASE_URL_ENV)


def _connect(database_url: str) -> Any:
    try:
        import psycopg  # type: ignore
    except ImportError as e:
        raise StorageError("psycopg is required for CockroachDB persistence") from e
    return psycopg.connect(database_url)


def _jsonb(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_jsonb(value).encode("utf-8")).hexdigest()


def _run_schema(cur: Any) -> None:
    cur.execute("SET CLUSTER SETTING feature.vector_index.enabled = true")
    for statement in SCHEMA_SQL:
        cur.execute(statement)


def _tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9_]{2,}", text.lower())
    out: list[str] = []
    for token in raw:
        out.append(token)
        out.extend(TOKEN_SYNONYMS.get(token, ()))
    return out


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMENSIONS
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        slot = int.from_bytes(digest[:2], "big") % VECTOR_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[slot] += sign
    magnitude = sum(v * v for v in vector) ** 0.5
    if magnitude == 0:
        return vector
    return [round(v / magnitude, 6) for v in vector]


def _vector_literal(vector: list[float]) -> str:
    if len(vector) != VECTOR_DIMENSIONS:
        raise StorageError(f"embedding_vector_invalid: expected {VECTOR_DIMENSIONS} dimensions")
    return "[" + ",".join(f"{value:.6f}".rstrip("0").rstrip(".") or "0" for value in vector) + "]"


def _section_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                status = str(item.get("status") or "").strip()
                if text and status:
                    lines.append(f"{text} ({status})")
                elif text:
                    lines.append(text)
            else:
                text = str(item).strip()
                if text:
                    lines.append(text)
        return "\n".join(lines)
    return ""


def memory_vector_rows(packet: dict[str, Any]) -> list[dict[str, str]]:
    current_state = packet.get("current_state")
    if not isinstance(current_state, dict):
        return []
    rows: list[dict[str, str]] = []
    for section_name, key in SECTION_KEYS:
        source_text = _section_text(current_state.get(key))
        if not source_text:
            continue
        rows.append(
            {
                "section_name": section_name,
                "source_text": source_text,
                "embedding": _vector_literal(embed_text(f"{section_name}\n{source_text}")),
            }
        )
    return rows


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value


def _iso_value(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def _state_list(state: dict[str, Any], key: str) -> list[str]:
    value = state.get(key)
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                status = str(item.get("status") or "").strip()
                if text and status:
                    out.append(f"{text} ({status})")
                elif text:
                    out.append(text)
            else:
                text = str(item).strip()
                if text:
                    out.append(text)
        return sorted(set(out))
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _state_count(state: dict[str, Any], key: str) -> int:
    return len(_state_list(state, key))


def timeline_entry(row: Any) -> dict[str, Any]:
    state = _json_value(row[5])
    if not isinstance(state, dict):
        state = {}
    return {
        "state_hash": str(row[0]),
        "created_at": _iso_value(row[1]),
        "task": str(row[2] or ""),
        "run_id": str(row[3] or ""),
        "receipt_hash": str(row[4] or ""),
        "changed_files_count": _state_count(state, "what_changed"),
        "verified_facts_count": _state_count(state, "what_is_true"),
        "unresolved_claims_count": _state_count(state, "what_is_unverified"),
        "contradictions_count": _state_count(state, "what_contradicts_prior_state"),
        "human_approval_count": _state_count(state, "what_needs_human_approval"),
        "next_clean_action": str(state.get("next_clean_action") or ""),
        "state": state,
    }


def diff_states(previous: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    previous_state = previous.get("state") if isinstance(previous.get("state"), dict) else previous
    latest_state = latest.get("state") if isinstance(latest.get("state"), dict) else latest
    prev_true = set(_state_list(previous_state, "what_is_true"))
    latest_true = set(_state_list(latest_state, "what_is_true"))
    prev_unresolved = set(_state_list(previous_state, "what_is_unverified"))
    latest_unresolved = set(_state_list(latest_state, "what_is_unverified"))
    prev_contradictions = set(_state_list(previous_state, "what_contradicts_prior_state"))
    latest_contradictions = set(_state_list(latest_state, "what_contradicts_prior_state"))
    prev_approvals = set(_state_list(previous_state, "what_needs_human_approval"))
    latest_approvals = set(_state_list(latest_state, "what_needs_human_approval"))
    previous_action = str(previous_state.get("next_clean_action") or "")
    latest_action = str(latest_state.get("next_clean_action") or "")

    return {
        "previous_state_hash": str(previous.get("state_hash") or previous.get("current_state_hash") or ""),
        "latest_state_hash": str(latest.get("state_hash") or latest.get("current_state_hash") or ""),
        "new_truths": sorted(latest_true - prev_true),
        "removed_truths": sorted(prev_true - latest_true),
        "still_unresolved": sorted(prev_unresolved & latest_unresolved),
        "new_unresolved_claims": sorted(latest_unresolved - prev_unresolved),
        "resolved_claims": sorted(prev_unresolved - latest_unresolved),
        "new_contradictions": sorted(latest_contradictions - prev_contradictions),
        "cleared_contradictions": sorted(prev_contradictions - latest_contradictions),
        "new_approval_items": sorted(latest_approvals - prev_approvals),
        "next_clean_action_previous": previous_action,
        "next_clean_action_latest": latest_action,
        "next_clean_action_changed": previous_action != latest_action,
    }


def init_schema(
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
) -> None:
    url = _database_url(database_url)
    if not url:
        raise StorageError(f"{DATABASE_URL_ENV} is required for storage init")
    connector = connect_func or _connect
    try:
        with connector(url) as conn:
            if hasattr(conn, "autocommit"):
                conn.autocommit = True
            with conn.cursor() as cur:
                _run_schema(cur)
            conn.commit()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"storage_init_failed: {e}") from e


def _run_id(packet: dict[str, Any]) -> str:
    proof = packet.get("proof") if isinstance(packet.get("proof"), dict) else {}
    raw = proof.get("run_id") or packet.get("deterministic_hash") or _hash_json(packet)
    return str(raw)


def _artifact_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, artifact in enumerate(artifacts, start=1):
        source = str(artifact.get("source_artifact") or f"artifact:{idx}")
        rows.append(
            {
                "source_artifact": source,
                "artifact_hash": _hash_json(artifact),
            }
        )
    return rows


def persist_lead_compile(
    packet: dict[str, Any],
    artifacts: list[dict[str, Any]],
    receipt: dict[str, Any],
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
) -> bool:
    url = _database_url(database_url)
    if not url:
        return False

    run_id = _run_id(packet)
    current_state_hash = str(packet.get("deterministic_hash") or _hash_json(packet))
    task = str(packet.get("task") or "")
    artifact_rows = _artifact_rows(artifacts)
    vector_rows = memory_vector_rows(packet)
    receipt_hash = str(receipt.get("receipt_hash") or _hash_json(receipt))
    connector = connect_func or _connect

    try:
        with connector(url) as conn:
            if hasattr(conn, "autocommit"):
                conn.autocommit = True
            with conn.cursor() as cur:
                _run_schema(cur)
            if hasattr(conn, "autocommit"):
                conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO yare_runs (
                        run_id,
                        task,
                        current_state_hash,
                        compiled_state_json,
                        source_artifact_hashes
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                    ON CONFLICT (run_id) DO UPDATE SET
                        task = excluded.task,
                        current_state_hash = excluded.current_state_hash,
                        compiled_state_json = excluded.compiled_state_json,
                        source_artifact_hashes = excluded.source_artifact_hashes
                    """,
                    (run_id, task, current_state_hash, _jsonb(packet), _jsonb(artifact_rows)),
                )
                cur.execute(
                    """
                    INSERT INTO yare_current_states (current_state_hash, run_id, state_json)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (current_state_hash) DO UPDATE SET
                        run_id = excluded.run_id,
                        state_json = excluded.state_json
                    """,
                    (current_state_hash, run_id, _jsonb(packet.get("current_state") or {})),
                )
                for artifact, artifact_row in zip(artifacts, artifact_rows):
                    cur.execute(
                        """
                        INSERT INTO yare_lead_artifacts (
                            run_id,
                            source_artifact,
                            artifact_hash,
                            artifact_json
                        )
                        VALUES (%s, %s, %s, %s::jsonb)
                        ON CONFLICT (run_id, source_artifact) DO UPDATE SET
                            artifact_hash = excluded.artifact_hash,
                            artifact_json = excluded.artifact_json
                        """,
                        (
                            run_id,
                            artifact_row["source_artifact"],
                            artifact_row["artifact_hash"],
                            _jsonb(artifact),
                        ),
                    )
                cur.execute(
                    """
                    INSERT INTO yare_receipts (
                        receipt_hash,
                        run_id,
                        current_state_hash,
                        receipt_json
                    )
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (receipt_hash) DO UPDATE SET
                        run_id = excluded.run_id,
                        current_state_hash = excluded.current_state_hash,
                        receipt_json = excluded.receipt_json
                    """,
                    (receipt_hash, run_id, current_state_hash, _jsonb(receipt)),
                )
                for row in vector_rows:
                    cur.execute(
                        """
                        INSERT INTO yare_memory_vectors (
                            run_id,
                            current_state_hash,
                            section_name,
                            source_text,
                            embedding
                        )
                        VALUES (%s, %s, %s, %s, %s::VECTOR)
                        ON CONFLICT (current_state_hash, section_name) DO UPDATE SET
                            run_id = excluded.run_id,
                            source_text = excluded.source_text,
                            embedding = excluded.embedding
                        """,
                        (
                            run_id,
                            current_state_hash,
                            row["section_name"],
                            row["source_text"],
                            row["embedding"],
                        ),
                    )
            conn.commit()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"lead_compile_persist_failed: {e}") from e

    return True


def search_memory(
    query: str,
    limit: int,
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
) -> list[dict[str, Any]]:
    url = _database_url(database_url)
    if not url:
        raise StorageError(f"{DATABASE_URL_ENV} is required for memory search")
    if limit < 1:
        raise StorageError("memory_search_limit_invalid: limit must be at least 1")

    connector = connect_func or _connect
    query_vector = _vector_literal(embed_text(query))
    try:
        with connector(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        section_name,
                        embedding <=> %s::VECTOR AS distance,
                        current_state_hash,
                        source_text
                    FROM yare_memory_vectors
                    ORDER BY embedding <=> %s::VECTOR
                    LIMIT %s
                    """,
                    (query_vector, query_vector, limit),
                )
                rows = cur.fetchall()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"memory_search_failed: {e}") from e

    return [
        {
            "section_name": str(row[0]),
            "distance": float(row[1]),
            "current_state_hash": str(row[2]),
            "source_text": str(row[3]),
        }
        for row in rows
    ]


def memory_timeline(
    limit: int = 25,
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
) -> list[dict[str, Any]]:
    url = _database_url(database_url)
    if not url:
        raise StorageError(f"{DATABASE_URL_ENV} is required for memory timeline")
    if limit < 1:
        raise StorageError("memory_timeline_limit_invalid: limit must be at least 1")

    connector = connect_func or _connect
    try:
        with connector(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        cs.current_state_hash,
                        cs.created_at,
                        COALESCE(r.task, ''),
                        cs.run_id,
                        COALESCE((
                            SELECT yr.receipt_hash
                            FROM yare_receipts yr
                            WHERE yr.current_state_hash = cs.current_state_hash
                            ORDER BY yr.created_at DESC
                            LIMIT 1
                        ), ''),
                        cs.state_json
                    FROM yare_current_states cs
                    LEFT JOIN yare_runs r ON r.run_id = cs.run_id
                    ORDER BY cs.created_at ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"memory_timeline_failed: {e}") from e

    return [timeline_entry(row) for row in rows]


def latest_memory_diff(
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    url = _database_url(database_url)
    if not url:
        raise StorageError(f"{DATABASE_URL_ENV} is required for memory diff")

    connector = connect_func or _connect
    try:
        with connector(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        cs.current_state_hash,
                        cs.created_at,
                        COALESCE(r.task, ''),
                        cs.run_id,
                        COALESCE((
                            SELECT yr.receipt_hash
                            FROM yare_receipts yr
                            WHERE yr.current_state_hash = cs.current_state_hash
                            ORDER BY yr.created_at DESC
                            LIMIT 1
                        ), ''),
                        cs.state_json
                    FROM yare_current_states cs
                    LEFT JOIN yare_runs r ON r.run_id = cs.run_id
                    ORDER BY cs.created_at DESC
                    LIMIT 2
                    """
                )
                rows = cur.fetchall()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"memory_diff_failed: {e}") from e

    if len(rows) < 2:
        raise StorageError("memory_diff_not_enough_states: need at least two current-state records")

    latest = timeline_entry(rows[0])
    previous = timeline_entry(rows[1])
    return diff_states(previous, latest)
