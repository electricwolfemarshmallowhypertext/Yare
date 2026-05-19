from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import uuid

import structlog
from sqlalchemy import create_engine, Table, Column, MetaData, String, Text, select, insert

logger = structlog.get_logger("memory.persona_store")


class PersonaStore:
    """
    Personas storage using SQLAlchemy Core.
    Schema:
      personas(
        id TEXT PRIMARY KEY,
        org_id TEXT,
        name TEXT NOT NULL,
        data TEXT (JSON),
        created_at TEXT NOT NULL
      )
    """

    def __init__(self, db_url: str) -> None:
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.meta = MetaData()
        self.personas = Table(
            "personas",
            self.meta,
            Column("id", String, primary_key=True),
            Column("org_id", String, nullable=True),
            Column("name", String, nullable=False),
            Column("data", Text, nullable=False),
            Column("created_at", String, nullable=False),
        )
        self.meta.create_all(self.engine)

    def import_persona(self, persona: Dict[str, Any], org_id: Optional[str]) -> Dict[str, Any]:
        pid = persona.get("id") or f"per_{uuid.uuid4().hex}"
        name = persona.get("name") or "persona"
        data = json.dumps(persona)
        created_at = datetime.utcnow().isoformat()
        with self.engine.begin() as cx:
            cx.execute(insert(self.personas).values(id=pid, org_id=org_id, name=name, data=data, created_at=created_at))
        logger.info("persona_imported", id=pid, name=name, org_id=org_id)
        return {"id": pid, "name": name, "org_id": org_id, "created_at": created_at}

    def export_persona(self, persona_id: str, org_id: Optional[str]) -> Optional[Dict[str, Any]]:
        stmt = select(self.personas).where(self.personas.c.id == persona_id)
        if org_id:
            stmt = stmt.where(self.personas.c.org_id == org_id)
        with self.engine.begin() as cx:
            row = cx.execute(stmt).mappings().first()
        if not row:
            return None
        try:
            return json.loads(row["data"])
        except Exception:
            return None

    def list_personas(self, org_id: Optional[str], limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        stmt = select(self.personas).order_by(self.personas.c.created_at.desc()).limit(limit).offset(offset)
        if org_id:
            stmt = stmt.where(self.personas.c.org_id == org_id)
        with self.engine.begin() as cx:
            rows = cx.execute(stmt).mappings().all()
        out = []
        for r in rows:
            out.append({"id": r["id"], "org_id": r["org_id"], "name": r["name"], "created_at": r["created_at"]})
        return out