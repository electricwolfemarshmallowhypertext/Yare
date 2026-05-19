from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import json
import uuid

import structlog
from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    String, Text, Integer, DateTime, Enum, select, insert, update, and_
)
from sqlalchemy.engine import Engine

logger = structlog.get_logger("memory.orchestrator.store")

WORKFLOW_STATES = ("pending", "running", "paused", "completed", "failed", "canceled")


class OrchestratorStore:
    """
    SQL-backed workflow persistence for durability, inspection, and resume/cancel.
    Tables:
      workflows(id, name, org_id, state, spec, started_at, updated_at)
      workflow_tasks(id, workflow_id, name, state, attempts, error, result, started_at, finished_at)
      workflow_events(id, workflow_id, ts, type, data)
    """

    def __init__(self, db_url: str) -> None:
        self.engine: Engine = create_engine(db_url, pool_pre_ping=True)
        self.meta = MetaData()
        self.workflows = Table(
            "workflows", self.meta,
            Column("id", String, primary_key=True),
            Column("name", String, nullable=False),
            Column("org_id", String, nullable=True),
            Column("state", String, nullable=False),
            Column("spec", Text, nullable=False),
            Column("started_at", String, nullable=False),
            Column("updated_at", String, nullable=False),
        )
        self.workflow_tasks = Table(
            "workflow_tasks", self.meta,
            Column("id", String, primary_key=True),
            Column("workflow_id", String, nullable=False, index=True),
            Column("name", String, nullable=False),
            Column("state", String, nullable=False),
            Column("attempts", Integer, nullable=False),
            Column("error", Text, nullable=True),
            Column("result", Text, nullable=True),
            Column("started_at", String, nullable=True),
            Column("finished_at", String, nullable=True),
        )
        self.workflow_events = Table(
            "workflow_events", self.meta,
            Column("id", String, primary_key=True),
            Column("workflow_id", String, nullable=False, index=True),
            Column("ts", String, nullable=False),
            Column("type", String, nullable=False),
            Column("data", Text, nullable=False),
        )
        self.meta.create_all(self.engine)

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()

    def create_workflow(self, name: str, spec: Dict[str, Any], org_id: Optional[str]) -> str:
        wid = f"wf_{uuid.uuid4().hex}"
        now = self._now()
        with self.engine.begin() as cx:
            cx.execute(insert(self.workflows).values(
                id=wid, name=name, org_id=org_id, state="pending",
                spec=json.dumps(spec), started_at=now, updated_at=now
            ))
        self.append_event(wid, "created", {"name": name, "org_id": org_id})
        return wid

    def set_state(self, workflow_id: str, state: str) -> None:
        if state not in WORKFLOW_STATES:
            raise ValueError(f"invalid state {state}")
        with self.engine.begin() as cx:
            cx.execute(update(self.workflows)
                       .where(self.workflows.c.id == workflow_id)
                       .values(state=state, updated_at=self._now()))

    def upsert_task(self, workflow_id: str, name: str, state: str,
                    attempts: int = 0, error: Optional[str] = None,
                    result: Optional[Dict[str, Any]] = None,
                    started_at: Optional[str] = None,
                    finished_at: Optional[str] = None,
                    task_id: Optional[str] = None) -> str:
        tid = task_id or f"t_{uuid.uuid4().hex}"
        with self.engine.begin() as cx:
            # Try update existing by id, else insert
            if task_id:
                cx.execute(update(self.workflow_tasks)
                           .where(self.workflow_tasks.c.id == tid)
                           .values(
                               state=state, attempts=attempts, error=error,
                               result=json.dumps(result) if result is not None else None,
                               started_at=started_at, finished_at=finished_at
                           ))
            else:
                cx.execute(insert(self.workflow_tasks).values(
                    id=tid, workflow_id=workflow_id, name=name, state=state,
                    attempts=attempts, error=error,
                    result=json.dumps(result) if result is not None else None,
                    started_at=started_at, finished_at=finished_at
                ))
        return tid

    def append_event(self, workflow_id: str, type_: str, data: Dict[str, Any]) -> None:
        with self.engine.begin() as cx:
            cx.execute(insert(self.workflow_events).values(
                id=f"e_{uuid.uuid4().hex}",
                workflow_id=workflow_id,
                ts=self._now(),
                type=type_,
                data=json.dumps(data),
            ))

    def get_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        with self.engine.begin() as cx:
            wf = cx.execute(select(self.workflows).where(self.workflows.c.id == workflow_id)).mappings().first()
            if not wf:
                return None
            tasks = cx.execute(select(self.workflow_tasks).where(self.workflow_tasks.c.workflow_id == workflow_id)).mappings().all()
            events = cx.execute(select(self.workflow_events).where(self.workflow_events.c.workflow_id == workflow_id)).mappings().all()
        out_tasks = []
        for t in tasks:
            try:
                res = json.loads(t["result"]) if t["result"] else None
            except Exception:
                res = None
            out_tasks.append({
                "id": t["id"], "name": t["name"], "state": t["state"],
                "attempts": t["attempts"], "error": t["error"],
                "result": res, "started_at": t["started_at"], "finished_at": t["finished_at"],
            })
        out_events = [{"id": e["id"], "ts": e["ts"], "type": e["type"], "data": json.loads(e["data"])} for e in events]
        return {
            "id": wf["id"], "name": wf["name"], "org_id": wf["org_id"],
            "state": wf["state"], "started_at": wf["started_at"], "updated_at": wf["updated_at"],
            "tasks": sorted(out_tasks, key=lambda x: (x["started_at"] or "", x["id"])),
            "events": sorted(out_events, key=lambda x: x["ts"]),
            "spec": json.loads(wf["spec"]),
        }