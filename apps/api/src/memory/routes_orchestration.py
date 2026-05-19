from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional
import os
import structlog

from .orchestrator import Orchestrator, TaskGraph
from .orchestrator_store import OrchestratorStore
from .ethics import PolicyEngine
from .config import settings

logger = structlog.get_logger("memory.routes.orchestration")

router = APIRouter(prefix="/orchestrations", tags=["orchestrations"])


def _db_url() -> str:
    # Compute same way as server
    sqlite_path = settings.SQLITE_PATH
    return settings.DATABASE_URL or f"sqlite:///{os.path.abspath(sqlite_path)}"


def get_orchestrator(request: Request) -> Orchestrator:
    store = OrchestratorStore(db_url=_db_url())
    # Concurrency and timeouts configurable via env if desired
    return Orchestrator(
        store=store,
        max_concurrency=int(os.getenv("ORCH_MAX_CONCURRENCY", "8")),
        default_timeout_sec=int(os.getenv("ORCH_TASK_TIMEOUT_SEC", "120")),
        default_retries=int(os.getenv("ORCH_DEFAULT_RETRIES", "2")),
        default_backoff_base=float(os.getenv("ORCH_BACKOFF_BASE", "0.5")),
    )


@router.post("")
async def start_orchestration(payload: Dict[str, Any], request: Request):
    """
    Start a workflow.
    payload: { "name": "...", "tasks": [...], "shared": {...}, "org_id": "..." }
    """
    try:
        orch = get_orchestrator(request)
        graph = TaskGraph.from_spec(payload)
        wid = await orch.start(graph, name=(payload.get("name") or "workflow"), org_id=payload.get("org_id"), shared_seed=payload.get("shared"))
        return {"workflow_id": wid, "status": "running"}
    except Exception as e:
        logger.error("orchestration_start_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workflow_id}")
async def get_orchestration(workflow_id: str, request: Request):
    orch = get_orchestrator(request)
    st = await orch.get_status(workflow_id)
    if not st:
        raise HTTPException(status_code=404, detail="Not found")
    return st


@router.post("/{workflow_id}/cancel")
async def cancel_orchestration(workflow_id: str, request: Request):
    orch = get_orchestrator(request)
    ok = await orch.cancel(workflow_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot cancel")
    return {"workflow_id": workflow_id, "status": "canceled"}