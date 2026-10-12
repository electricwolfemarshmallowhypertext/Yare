from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Callable
from cli import integrity

DATABASE_URL_ENV = "YARE_DATABASE_URL"
VECTOR_DIMENSIONS = 32

SCHEMA_TABLES = (
    "yare_runs",
    "yare_lead_artifacts",
    "yare_current_states",
    "yare_receipts",
    "yare_memory_vectors",
    "yare_run_snapshots",
    "yare_events",
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
        packet_json JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "ALTER TABLE yare_current_states ADD COLUMN IF NOT EXISTS packet_json JSONB",
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
    """
    CREATE TABLE IF NOT EXISTS yare_run_snapshots (
        run_id TEXT NOT NULL REFERENCES yare_runs(run_id),
        current_state_hash TEXT NOT NULL,
        packet_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (run_id, current_state_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS yare_events (
        receipt_hash TEXT PRIMARY KEY REFERENCES yare_receipts(receipt_hash),
        run_id TEXT NOT NULL REFERENCES yare_runs(run_id),
        current_state_hash TEXT NOT NULL,
        task TEXT NOT NULL,
        packet_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        INDEX yare_events_task_time (task, created_at DESC)
    )
    """,
    """
    INSERT INTO yare_events (receipt_hash, run_id, current_state_hash, task, packet_json, created_at)
    SELECT rec.receipt_hash, rec.run_id, rec.current_state_hash,
           COALESCE(cs.packet_json->>'task', r.task),
           COALESCE(rec.receipt_json->'packet_snapshot', cs.packet_json,
             jsonb_build_object('task', r.task, 'current_state', cs.state_json)), rec.created_at
    FROM yare_receipts rec JOIN yare_current_states cs ON cs.current_state_hash = rec.current_state_hash
    JOIN yare_runs r ON r.run_id = rec.run_id
    ON CONFLICT (receipt_hash) DO NOTHING
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
SEARCH_STOP_WORDS = {"what", "is", "are", "the", "a", "an", "and", "or", "to", "for", "of",
                     "in", "on", "still", "needs", "need", "does", "do", "which", "with", "me"}


class StorageError(RuntimeError):
    pass


def _database_url(explicit_url: str | None = None) -> str | None:
    return explicit_url or os.environ.get(DATABASE_URL_ENV)


def _connect(database_url: str) -> Any:
    try:
        import psycopg  # type: ignore
    except ImportError as e:
        raise StorageError("psycopg is required for CockroachDB persistence") from e
    return psycopg.connect(database_url, connect_timeout=15)


def _jsonb(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_jsonb(value).encode("utf-8")).hexdigest()


def verify_handoff_record(row: Any) -> dict[str, Any]:
    run_id, state_hash, state, packet, receipt_hash, receipt = row
    if not isinstance(receipt, dict) or receipt.get("receipt_hash") != receipt_hash:
        raise StorageError("handoff_receipt_missing")
    if isinstance(receipt, dict) and "packet_snapshot" in receipt:
        packet = receipt["packet_snapshot"]
    if not isinstance(packet, dict) or packet.get("deterministic_hash") != state_hash:
        raise StorageError("handoff_packet_missing")
    if integrity.state_hash(packet) != state_hash:
        raise StorageError("handoff_state_hash_mismatch")
    if packet.get("hash_version") == "work-state.v2" and receipt.get("packet_hash") != integrity.digest(packet):
        raise StorageError("handoff_packet_hash_mismatch")
    if packet.get("current_state") != state:
        raise StorageError("handoff_state_content_mismatch")
    if (_hash_json({key: value for key, value in receipt.items() if key != "receipt_hash"}) != receipt_hash
            or receipt.get("run_id") != run_id or receipt.get("current_state_hash") != state_hash):
        raise StorageError("handoff_receipt_hash_mismatch")
    artifacts = packet.get("artifacts")
    if not isinstance(artifacts, list):
        raise StorageError("handoff_artifacts_missing")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise StorageError("handoff_artifact_invalid")
        evidence = artifact.get("evidence") or {}
        if not isinstance(evidence, dict):
            raise StorageError("handoff_evidence_invalid")
        if "source_code" in evidence or "source_sha256" in evidence:
            source = evidence.get("source_code")
            if not isinstance(source, str) or hashlib.sha256(source.encode("utf-8")).hexdigest() != evidence.get("source_sha256"):
                raise StorageError("handoff_source_hash_mismatch")
    return {"run_id": run_id, "task": packet.get("task"), "current_state_hash": state_hash,
            "current_state": state, "artifacts": artifacts, "receipt_hash": receipt_hash,
            "receipt": receipt, "verified": True}


def load_handoff(*, task: str | None = None, run_id: str | None = None,
                 state_hash: str | None = None, database_url: str | None = None,
                 connect_func: Callable[[str], Any] | None = None) -> dict[str, Any]:
    if not any((task, run_id, state_hash)):
        raise StorageError("handoff_selector_required")
    url = _database_url(database_url)
    if not url:
        raise StorageError("YARE_DATABASE_URL is required")
    clauses, values = [], []
    for value, clause in ((run_id, "cs.run_id = %s"), (state_hash, "cs.current_state_hash = %s"),
                          (task, "COALESCE(cs.packet_json->>'task', r.task) = %s")):
        if value:
            clauses.append(clause)
            values.append(value)
    try:
        with (connect_func or _connect)(url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cs.run_id, cs.current_state_hash, cs.state_json,
                           COALESCE(cs.packet_json, CASE WHEN r.current_state_hash = cs.current_state_hash
                             THEN r.compiled_state_json END), rec.receipt_hash, rec.receipt_json
                    FROM yare_current_states cs JOIN yare_runs r ON r.run_id = cs.run_id
                    JOIN yare_receipts rec ON rec.run_id = cs.run_id
                      AND rec.current_state_hash = cs.current_state_hash
                    WHERE """ + " AND ".join(clauses) + """
                    ORDER BY rec.created_at DESC, rec.receipt_hash DESC,
                             cs.created_at DESC, cs.current_state_hash DESC LIMIT 1
                """, tuple(values))
                row = cur.fetchone()
        if row is None:
            raise StorageError("handoff_not_found")
        return verify_handoff_record(row)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError("handoff_database_read_failed") from exc


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
    prev_files = set(_state_list(previous_state, "what_changed"))
    latest_files = set(_state_list(latest_state, "what_changed"))
    prev_loops = set(_state_list(previous_state, "open_loops"))
    latest_loops = set(_state_list(latest_state, "open_loops"))
    previous_action = str(previous_state.get("next_clean_action") or "")
    latest_action = str(latest_state.get("next_clean_action") or "")
    disappeared = prev_unresolved - latest_unresolved
    approved_resolutions = {
        record["claim"] for record in latest_state.get("claim_resolutions", [])
        if isinstance(record, dict) and record.get("kind") == "human_review"
        and record.get("decision") == "approved" and record.get("reviewer")
        and isinstance(record.get("claim"), str)
    }
    resolved = disappeared & (latest_true | approved_resolutions)

    return {
        "previous_state_hash": str(previous.get("state_hash") or previous.get("current_state_hash") or ""),
        "latest_state_hash": str(latest.get("state_hash") or latest.get("current_state_hash") or ""),
        "new_truths": sorted(latest_true - prev_true),
        "removed_truths": sorted(prev_true - latest_true),
        "still_unresolved": sorted(prev_unresolved & latest_unresolved),
        "new_unresolved_claims": sorted(latest_unresolved - prev_unresolved),
        "resolved_claims": sorted(resolved),
        "removed_claims": sorted(disappeared - resolved),
        "new_contradictions": sorted(latest_contradictions - prev_contradictions),
        "cleared_contradictions": sorted(prev_contradictions - latest_contradictions),
        "new_approval_items": sorted(latest_approvals - prev_approvals),
        "new_files": sorted(latest_files - prev_files),
        "removed_files": sorted(prev_files - latest_files),
        "new_open_loops": sorted(latest_loops - prev_loops),
        "removed_open_loops": sorted(prev_loops - latest_loops),
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
                    ON CONFLICT (run_id) DO NOTHING
                    """,
                    (run_id, task, current_state_hash, _jsonb(packet), _jsonb(artifact_rows)),
                )
                cur.execute(
                    """
                    INSERT INTO yare_current_states (current_state_hash, run_id, state_json, packet_json)
                    VALUES (%s, %s, %s::jsonb, %s::jsonb)
                    ON CONFLICT (current_state_hash) DO NOTHING
                    """,
                    (current_state_hash, run_id, _jsonb(packet.get("current_state") or {}), _jsonb(packet)),
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
                        ON CONFLICT (run_id, source_artifact) DO NOTHING
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
                    ON CONFLICT (receipt_hash) DO NOTHING
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
                        ON CONFLICT (current_state_hash, section_name) DO NOTHING
                        """,
                        (
                            run_id,
                            current_state_hash,
                            row["section_name"],
                            row["source_text"],
                            row["embedding"],
                        ),
                    )
                cur.execute("""INSERT INTO yare_run_snapshots (run_id, current_state_hash, packet_json)
                    VALUES (%s, %s, %s::jsonb) ON CONFLICT (run_id, current_state_hash) DO NOTHING""",
                    (run_id, current_state_hash, _jsonb(packet)))
                cur.execute("""INSERT INTO yare_events (receipt_hash, run_id, current_state_hash, task, packet_json)
                    VALUES (%s, %s, %s, %s, %s::jsonb) ON CONFLICT (receipt_hash) DO NOTHING""",
                    (receipt_hash, run_id, current_state_hash, task, _jsonb(packet)))
            conn.commit()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError("lead_compile_persist_failed") from e

    return True


def _search_sections(query: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    sections: set[str] = set()
    if (words & {"review", "approval", "approve", "approved"}
            or {"sign", "off"} <= words
            or (words & {"person", "human"} and words & {"blocked", "waiting", "pending"})):
        sections.add("human approval items")
    if words & {"file", "files"} and words & {"changed", "modified", "edited"}:
        sections.add("what changed")
    if words & {"unfinished", "remaining", "blocked", "waiting"}:
        sections.add("open loops")
    return sections


def search_memory(
    query: str,
    limit: int,
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
    task: str | None = None,
) -> list[dict[str, Any]]:
    url = _database_url(database_url)
    if not url:
        raise StorageError(f"{DATABASE_URL_ENV} is required for memory search")
    if limit < 1:
        raise StorageError("memory_search_limit_invalid: limit must be at least 1")

    connector = connect_func or _connect
    query_vector = _vector_literal(embed_text(query))
    terms = set(_tokens(query)) - SEARCH_STOP_WORDS
    preferred_sections = _search_sections(query)
    for section in preferred_sections:
        terms.update(set(_tokens(section)) - SEARCH_STOP_WORDS)
    if not terms:
        raise StorageError("memory_search_query_invalid: enter a meaningful query")
    candidate_limit = min(max(limit * 10, 50), 500)
    scope_sql = ""
    scope_args: tuple[Any, ...] = ()
    if task is not None:
        scope_sql = """current_state_hash IN (
            SELECT cs.current_state_hash FROM yare_current_states cs
            JOIN yare_runs r ON r.run_id = cs.run_id
            WHERE COALESCE(cs.packet_json->>'task', r.task) = %s)"""
        scope_args = (task,)
    try:
        with connector(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        section_name,
                        embedding <=> %s::VECTOR AS distance,
                        current_state_hash,
                        source_text
                    FROM yare_memory_vectors
                    {('WHERE ' + scope_sql) if scope_sql else ''}
                    ORDER BY embedding <=> %s::VECTOR
                    LIMIT %s
                    """,
                    (query_vector, *scope_args, query_vector, candidate_limit),
                )
                rows = list(cur.fetchall())
                matches = " OR ".join("LOWER(section_name || ' ' || source_text) LIKE %s" for _ in terms)
                cur.execute(
                    f"""SELECT section_name, embedding <=> %s::VECTOR AS distance,
                               current_state_hash, source_text
                        FROM yare_memory_vectors WHERE ({matches})
                        {('AND ' + scope_sql) if scope_sql else ''}
                        ORDER BY created_at DESC, current_state_hash DESC LIMIT %s""",
                    (query_vector, *(f"%{term}%" for term in sorted(terms)), *scope_args, candidate_limit),
                )
                rows.extend(cur.fetchall())
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"memory_search_failed: {e}") from e

    def rank(row: Any) -> tuple[int, int, int, float, str]:
        section_terms = set(_tokens(str(row[0]))) - SEARCH_STOP_WORDS
        text_terms = set(_tokens(str(row[3]))) - SEARCH_STOP_WORDS
        return (-int(str(row[0]).lower() in preferred_sections),
                -len(terms & section_terms), -len(terms & text_terms), float(row[1]), str(row[2]))

    unique = {}
    for row in sorted(rows, key=rank):
        section_match, section_overlap, text_overlap, _, _ = rank(row)
        if section_match == 0 and section_overlap == 0 and text_overlap == 0:
            continue
        key = (str(row[0]), str(row[3]).strip().casefold())
        unique.setdefault(key, row)
    selected = list(unique.values())[:limit]
    return [
        {
            "section_name": str(row[0]),
            "distance": float(row[1]),
            "current_state_hash": str(row[2]),
            "source_text": str(row[3]),
        }
        for row in selected
    ]


def memory_timeline(
    limit: int = 25,
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
    task: str | None = None,
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
                        current_state_hash, created_at, task, run_id, receipt_hash,
                        packet_json->'current_state'
                    FROM yare_events
                    WHERE (%s::TEXT IS NULL OR task = %s)
                    ORDER BY created_at DESC, receipt_hash DESC
                    LIMIT %s
                    """,
                    (task, task, limit),
                )
                rows = cur.fetchall()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"memory_timeline_failed: {e}") from e

    return [timeline_entry(row) for row in reversed(rows)]


def latest_memory_diff(
    database_url: str | None = None,
    connect_func: Callable[[str], Any] | None = None,
    task: str | None = None,
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
                        current_state_hash, created_at, task, run_id, receipt_hash,
                        packet_json->'current_state'
                    FROM yare_events
                    WHERE task = COALESCE(%s::TEXT, (
                        SELECT task FROM yare_events
                        ORDER BY created_at DESC, receipt_hash DESC LIMIT 1
                    ))
                    ORDER BY created_at DESC, receipt_hash DESC
                    LIMIT 2
                    """, (task,)
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
