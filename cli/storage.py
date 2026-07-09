from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable

DATABASE_URL_ENV = "YARE_DATABASE_URL"

SCHEMA_TABLES = (
    "yare_runs",
    "yare_lead_artifacts",
    "yare_current_states",
    "yare_receipts",
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
)


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
    for statement in SCHEMA_SQL:
        cur.execute(statement)


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
    receipt_hash = str(receipt.get("receipt_hash") or _hash_json(receipt))
    connector = connect_func or _connect

    try:
        with connector(url) as conn:
            with conn.cursor() as cur:
                _run_schema(cur)
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
            conn.commit()
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(f"lead_compile_persist_failed: {e}") from e

    return True
