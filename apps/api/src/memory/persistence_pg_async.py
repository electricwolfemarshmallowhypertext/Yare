from __future__ import annotations

from typing import Optional, Dict, Any, List

import json
import os

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection

logger = structlog.get_logger("memory.persistence_pg_async")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories(
  id TEXT PRIMARY KEY,
  org_id TEXT NULL,
  user_id TEXT NULL,
  persona_id TEXT NULL,
  project_id TEXT NULL,
  thread_id TEXT NULL,
  type TEXT NOT NULL,
  text TEXT NOT NULL,
  salience REAL NOT NULL,
  created_at TEXT NOT NULL,
  metadata JSONB NULL
);
CREATE INDEX IF NOT EXISTS idx_mem_created ON memories (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mem_org ON memories (org_id);
CREATE INDEX IF NOT EXISTS idx_mem_user ON memories (user_id);
CREATE INDEX IF NOT EXISTS idx_mem_persona ON memories (persona_id);
CREATE INDEX IF NOT EXISTS idx_mem_thread ON memories (thread_id);
"""

UPSERT_SQL = """
INSERT INTO memories (id, org_id, user_id, persona_id, project_id, thread_id, type, text, salience, created_at, metadata)
VALUES (:id, :org_id, :user_id, :persona_id, :project_id, :thread_id, :type, :text, :salience, :created_at, :metadata)
ON CONFLICT (id) DO UPDATE SET
  org_id=EXCLUDED.org_id,
  user_id=EXCLUDED.user_id,
  persona_id=EXCLUDED.persona_id,
  project_id=EXCLUDED.project_id,
  thread_id=EXCLUDED.thread_id,
  type=EXCLUDED.type,
  text=EXCLUDED.text,
  salience=EXCLUDED.salience,
  created_at=EXCLUDED.created_at,
  metadata=EXCLUDED.metadata
"""

GET_SQL = "SELECT * FROM memories WHERE id = :id LIMIT 1"

QUERY_SQL = """
SELECT * FROM memories
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset
"""


class AsyncPersistencePG:
    """
    Async Postgres store using SQLAlchemy AsyncEngine (asyncpg driver).
    """
    def __init__(self, db_url: str):
        if not db_url.startswith("postgresql+asyncpg://"):
            # Accept 'postgresql://' and convert
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        self.engine: AsyncEngine = create_async_engine(db_url, pool_pre_ping=True)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(SCHEMA_SQL))

    async def upsert(self, doc: Dict[str, Any]) -> None:
        payload = {
            "id": doc["id"],
            "org_id": doc.get("org_id"),
            "user_id": doc.get("user_id"),
            "persona_id": doc.get("persona_id"),
            "project_id": doc.get("project_id"),
            "thread_id": doc.get("thread_id"),
            "type": doc["type"],
            "text": doc["text"],
            "salience": float(doc["salience"]),
            "created_at": str(doc["created_at"]),
            "metadata": json.dumps(doc.get("metadata") or {}),
        }
        async with self.engine.begin() as conn:
            await conn.execute(text(UPSERT_SQL), payload)

    async def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        async with self.engine.begin() as conn:
            res = await conn.execute(text(GET_SQL), {"id": memory_id})
            row = res.mappings().first()
            return dict(row) if row else None

    async def query(self, limit: int = 100, offset: int = 0, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        # project_id is not filtered here; adjust if needed
        async with self.engine.begin() as conn:
            res = await conn.execute(text(QUERY_SQL), {"limit": int(limit), "offset": int(offset)})
            rows = res.mappings().all()
            return [dict(r) for r in rows]