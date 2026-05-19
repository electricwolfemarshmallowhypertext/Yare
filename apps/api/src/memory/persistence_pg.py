"""
Postgres persistence using SQLAlchemy Core.
- Env var POSTGRES_URL (e.g., postgres://user:pass@host:5432/dbname)
- Compatible API with MemoryStore (subset): upsert, get, query, delete
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import json

import structlog
from sqlalchemy import create_engine, Table, Column, MetaData, String, Float, Text, select, Index
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .metrics import DB_OPS, DB_OP_DURATION

logger = structlog.get_logger("memory.persistence_pg")


class PostgresStore:
    def __init__(self, url: str) -> None:
        self.engine = create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
        self.meta = MetaData()
        self.memories = Table(
            "memories",
            self.meta,
            Column("id", String, primary_key=True),
            Column("text", Text, nullable=False),
            Column("type", String, nullable=False),
            Column("salience", Float, nullable=False),
            Column("created_at", String, nullable=False),
            Column("thread_id", String, nullable=False),
            Column("user_id", String, nullable=False),
            Column("persona_id", String, nullable=False),
            Column("embedding", Text, nullable=True),
            Column("metadata", Text, nullable=True),
            Column("project_id", String, nullable=True),
            Index("idx_mem_thread_persona", "thread_id", "persona_id"),
            Index("idx_mem_user", "user_id"),
            Index("idx_mem_project", "project_id"),
        )
        self.meta.create_all(self.engine)

    def upsert(self, mem: Dict[str, Any]) -> None:
        with DB_OP_DURATION.labels("upsert").time():
            try:
                payload = {
                    "id": mem["id"],
                    "text": mem["text"],
                    "type": mem["type"],
                    "salience": float(mem["salience"]),
                    "created_at": str(mem.get("created_at") or datetime.utcnow().isoformat()),
                    "thread_id": mem["thread_id"],
                    "user_id": mem["user_id"],
                    "persona_id": mem["persona_id"],
                    "embedding": json.dumps(mem.get("embedding")) if mem.get("embedding") is not None else None,
                    "metadata": json.dumps(mem.get("metadata")) if mem.get("metadata") is not None else None,
                    "project_id": mem.get("project_id"),
                }
                stmt = pg_insert(self.memories).values(**payload)
                stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=payload)
                with self.engine.begin() as cx:
                    cx.execute(stmt)
                DB_OPS.labels(op="upsert", status="success").inc()
            except Exception as e:
                DB_OPS.labels(op="upsert", status="error").inc()
                logger.error("pg_upsert_failed", error=str(e))
                raise

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        with DB_OP_DURATION.labels("get").time():
            try:
                stmt = select(self.memories).where(self.memories.c.id == memory_id).limit(1)
                with self.engine.begin() as cx:
                    row = cx.execute(stmt).mappings().first()
                if not row:
                    return None
                return self._row_to_obj(dict(row))
            except Exception as e:
                DB_OPS.labels(op="get", status="error").inc()
                logger.error("pg_get_failed", error=str(e))
                raise
            finally:
                DB_OPS.labels(op="get", status="success").inc()

    def query(
        self,
        *,
        thread_id: Optional[str] = None,
        persona_id: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with DB_OP_DURATION.labels("query").time():
            try:
                stmt = select(self.memories)
                if thread_id:
                    stmt = stmt.where(self.memories.c.thread_id == thread_id)
                if persona_id:
                    stmt = stmt.where(self.memories.c.persona_id == persona_id)
                if user_id:
                    stmt = stmt.where(self.memories.c.user_id == user_id)
                if project_id:
                    stmt = stmt.where(self.memories.c.project_id == project_id)
                stmt = stmt.order_by(self.memories.c.created_at.desc()).limit(limit).offset(offset)
                with self.engine.begin() as cx:
                    rows = cx.execute(stmt).mappings().all()
                return [self._row_to_obj(dict(r)) for r in rows]
            except Exception as e:
                DB_OPS.labels(op="query", status="error").inc()
                logger.error("pg_query_failed", error=str(e))
                raise
            finally:
                DB_OPS.labels(op="query", status="success").inc()

    def delete(self, memory_id: str) -> bool:
        try:
            with self.engine.begin() as cx:
                res = cx.execute(self.memories.delete().where(self.memories.c.id == memory_id))
                return res.rowcount > 0
        except Exception as e:
            logger.error("pg_delete_failed", error=str(e))
            raise

    @staticmethod
    def _row_to_obj(row: Dict[str, Any]) -> Dict[str, Any]:
        if row.get("embedding"):
            try:
                row["embedding"] = json.loads(row["embedding"])
            except Exception:
                row["embedding"] = None
        if row.get("metadata"):
            try:
                row["metadata"] = json.loads(row["metadata"])
            except Exception:
                row["metadata"] = None
        return row