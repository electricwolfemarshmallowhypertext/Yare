"""
SQLite persistence for memories.
- Minimal, safe schema
- Parameterized queries
- JSON serialization for embedding/metadata
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
import structlog

from .metrics import DB_OPS, DB_OP_DURATION

logger = structlog.get_logger("memory.persistence")

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    type TEXT NOT NULL,
    salience REAL NOT NULL,
    created_at TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    persona_id TEXT NOT NULL,
    embedding TEXT,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_mem_thread_persona ON memories(thread_id, persona_id);
CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id);
"""


class MemoryStore:
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as cx:
            cx.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        cx = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        try:
            cx.execute("PRAGMA journal_mode=WAL")
            cx.execute("PRAGMA synchronous=NORMAL")
            yield cx
        finally:
            cx.close()

    def upsert(self, mem: Dict[str, Any]) -> None:
        with DB_OP_DURATION.labels("upsert").time():
            try:
                payload = (
                    mem["id"],
                    mem["text"],
                    mem["type"],
                    float(mem["salience"]),
                    str(mem.get("created_at") or datetime.utcnow().isoformat()),
                    mem["thread_id"],
                    mem["user_id"],
                    mem["persona_id"],
                    json.dumps(mem.get("embedding")) if mem.get("embedding") is not None else None,
                    json.dumps(mem.get("metadata")) if mem.get("metadata") is not None else None,
                )
                with self._conn() as cx:
                    cx.execute(
                        """
                        INSERT INTO memories (id, text, type, salience, created_at, thread_id, user_id, persona_id, embedding, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            text=excluded.text,
                            type=excluded.type,
                            salience=excluded.salience,
                            created_at=excluded.created_at,
                            thread_id=excluded.thread_id,
                            user_id=excluded.user_id,
                            persona_id=excluded.persona_id,
                            embedding=excluded.embedding,
                            metadata=excluded.metadata
                        """,
                        payload,
                    )
                DB_OPS.labels(op="upsert", status="success").inc()
            except Exception as e:
                DB_OPS.labels(op="upsert", status="error").inc()
                logger.error("db_upsert_failed", error=str(e))
                raise

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        with DB_OP_DURATION.labels("get").time():
            try:
                with self._conn() as cx:
                    row = cx.execute(
                        "SELECT id, text, type, salience, created_at, thread_id, user_id, persona_id, embedding, metadata FROM memories WHERE id=?",
                        (memory_id,),
                    ).fetchone()
                if not row:
                    return None
                return self._row_to_obj(row)
            except Exception as e:
                DB_OPS.labels(op="get", status="error").inc()
                logger.error("db_get_failed", error=str(e))
                raise
            finally:
                DB_OPS.labels(op="get", status="success").inc()

    def query(
        self,
        *,
        thread_id: Optional[str] = None,
        persona_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with DB_OP_DURATION.labels("query").time():
            try:
                clauses = []
                params: List[Any] = []
                if thread_id:
                    clauses.append("thread_id = ?")
                    params.append(thread_id)
                if persona_id:
                    clauses.append("persona_id = ?")
                    params.append(persona_id)
                if user_id:
                    clauses.append("user_id = ?")
                    params.append(user_id)

                where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                sql = f"""
                    SELECT id, text, type, salience, created_at, thread_id, user_id, persona_id, embedding, metadata
                    FROM memories
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])

                with self._conn() as cx:
                    rows = cx.execute(sql, tuple(params)).fetchall()
                return [self._row_to_obj(r) for r in rows]
            except Exception as e:
                DB_OPS.labels(op="query", status="error").inc()
                logger.error("db_query_failed", error=str(e))
                raise
            finally:
                DB_OPS.labels(op="query", status="success").inc()

    def delete(self, memory_id: str) -> bool:
        with DB_OP_DURATION.labels("delete").time():
            try:
                with self._conn() as cx:
                    cur = cx.execute("DELETE FROM memories WHERE id=?", (memory_id,))
                    deleted = cur.rowcount > 0
                DB_OPS.labels(op="delete", status="success").inc()
                return deleted
            except Exception as e:
                DB_OPS.labels(op="delete", status="error").inc()
                logger.error("db_delete_failed", error=str(e))
                raise

    def vacuum_if_needed(self, threshold_bytes: int = 100 * 1024 * 1024) -> None:
        try:
            size = os.path.getsize(self.path) if os.path.exists(self.path) else 0
            if size >= threshold_bytes:
                with self._conn() as cx:
                    cx.execute("VACUUM")
                logger.info("db_vacuum_completed", size=size)
        except Exception as e:
            logger.warning("db_vacuum_failed", error=str(e))

    @staticmethod
    def _row_to_obj(row) -> Dict[str, Any]:
        (
            id_,
            text,
            type_,
            salience,
            created_at,
            thread_id,
            user_id,
            persona_id,
            embedding_json,
            metadata_json,
        ) = row
        return {
            "id": id_,
            "text": text,
            "type": type_,
            "salience": float(salience),
            "created_at": created_at,
            "thread_id": thread_id,
            "user_id": user_id,
            "persona_id": persona_id,
            "embedding": json.loads(embedding_json) if embedding_json else None,
            "metadata": json.loads(metadata_json) if metadata_json else None,
        }