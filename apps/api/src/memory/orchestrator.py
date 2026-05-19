from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime
import traceback
import structlog

from .orchestrator_store import OrchestratorStore
from .metrics import INFLIGHT_REQUESTS

logger = structlog.get_logger("memory.orchestrator")

# Task registry

TaskFn = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]
_TASKS: Dict[str, TaskFn] = {}


def register_task(name: str):
    def deco(fn: TaskFn):
        _TASKS[name] = fn
        return fn
    return deco


def get_task(name: str) -> TaskFn:
    if name not in _TASKS:
        raise KeyError(f"task '{name}' is not registered")
    return _TASKS[name]


@dataclass
class TaskSpec:
    id: str
    name: str     # registry name
    args: Dict[str, Any] = field(default_factory=dict)
    needs: Set[str] = field(default_factory=set)
    timeout_sec: Optional[int] = None
    retries: int = 0
    backoff_base: float = 0.5


@dataclass
class TaskGraph:
    tasks: Dict[str, TaskSpec]

    @staticmethod
    def from_spec(spec: Dict[str, Any]) -> "TaskGraph":
        """
        Spec format:
        {
          "name": "workflow-name",
          "tasks": [
            {"id":"t1","task":"fetch","args":{...},"needs":[],"timeout_sec":60,"retries":2},
            {"id":"t2","task":"process","args":{...},"needs":["t1"]},
            {"id":"t3","task":"persist","args":{...},"needs":["t2"]}
          ]
        }
        """
        tasks: Dict[str, TaskSpec] = {}
        for t in spec.get("tasks", []):
            tid = t["id"]
            tasks[tid] = TaskSpec(
                id=tid,
                name=t["task"],
                args=t.get("args") or {},
                needs=set(t.get("needs") or []),
                timeout_sec=t.get("timeout_sec"),
                retries=int(t.get("retries", 0)),
                backoff_base=float(t.get("backoff_base", 0.5)),
            )
        return TaskGraph(tasks=tasks)

    def roots(self) -> List[TaskSpec]:
        return [t for t in self.tasks.values() if not t.needs]

    def dependents(self, tid: str) -> List[TaskSpec]:
        return [t for t in self.tasks.values() if tid in t.needs]

    def is_ready(self, tid: str, done: Set[str]) -> bool:
        return self.tasks[tid].needs.issubset(done)


class Orchestrator:
    """
    Asynchronous DAG executor with durable persistence, retries, and cancellation.
    - Task registry allows plugging in custom tasks without touching the engine.
    - OrchestratorStore persists workflow state, tasks, and events for inspection/resume.
    """

    def __init__(
        self,
        store: OrchestratorStore,
        max_concurrency: int = 8,
        default_timeout_sec: int = 120,
        default_retries: int = 2,
        default_backoff_base: float = 0.5,
    ) -> None:
        self.store = store
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.default_timeout = default_timeout_sec
        self.default_retries = default_retries
        self.default_backoff = default_backoff_base
        self._canceled: Set[str] = set()

    async def start(self, graph: TaskGraph, name: str, org_id: Optional[str], shared_seed: Optional[Dict[str, Any]] = None) -> str:
        spec = {
            "name": name,
            "tasks": [
                {
                    "id": t.id, "task": t.name, "args": t.args, "needs": list(t.needs),
                    "timeout_sec": t.timeout_sec, "retries": t.retries, "backoff_base": t.backoff_base
                } for t in graph.tasks.values()
            ],
            "shared": shared_seed or {},
        }
        wid = self.store.create_workflow(name=name, spec=spec, org_id=org_id)
        self.store.set_state(wid, "running")
        self.store.append_event(wid, "started", {"shared": shared_seed or {}})
        asyncio.create_task(self._run_workflow(wid, graph, shared_seed or {}))
        return wid

    async def cancel(self, workflow_id: str) -> bool:
        self._canceled.add(workflow_id)
        self.store.set_state(workflow_id, "canceled")
        self.store.append_event(workflow_id, "canceled", {})
        return True

    async def get_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        return self.store.get_status(workflow_id)

    # Internal

    async def _run_workflow(self, wid: str, graph: TaskGraph, shared: Dict[str, Any]):
        INFLIGHT_REQUESTS.inc()
        try:
            done: Set[str] = set()
            running: Dict[str, asyncio.Task] = {}
            results: Dict[str, Any] = {}

            # seed roots first
            queue: List[str] = [t.id for t in graph.roots()]

            while queue or running:
                # Schedule ready tasks
                newly_started: List[str] = []
                for tid in list(queue):
                    if self._canceled.__contains__(wid):
                        logger.info("workflow_canceled", workflow_id=wid)
                        break
                    if not graph.is_ready(tid, done):
                        continue
                    queue.remove(tid)
                    newly_started.append(tid)
                    running[tid] = asyncio.create_task(self._execute_task(wid, graph.tasks[tid], shared, results))
                # Wait for any task completion
                if not running:
                    await asyncio.sleep(0.01)
                else:
                    finished, pending = await asyncio.wait(running.values(), return_when=asyncio.FIRST_COMPLETED)
                    for task in finished:
                        # find tid by task object
                        tid = None
                        for k, v in list(running.items()):
                            if v is task:
                                tid = k
                                break
                        if tid is None:
                            continue
                        try:
                            res = task.result()
                            results[tid] = res or {}
                            done.add(tid)
                            # enqueue dependents that may become ready
                            for dep in graph.dependents(tid):
                                if dep.id not in done and dep.id not in running and dep.id not in queue:
                                    queue.append(dep.id)
                        except Exception as e:
                            # already persisted in _execute_task; mark failure and stop
                            logger.error("task_failed", workflow_id=wid, task_id=tid, error=str(e))
                            running.pop(tid, None)
                            # cancel others
                            for t in running.values():
                                t.cancel()
                            running.clear()
                            self.store.set_state(wid, "failed")
                            self.store.append_event(wid, "failed", {"error": str(e)})
                            return
                        running.pop(tid, None)

                if self._canceled.__contains__(wid):
                    # cancel any running tasks
                    for t in running.values():
                        t.cancel()
                    running.clear()
                    self.store.set_state(wid, "canceled")
                    self.store.append_event(wid, "canceled", {})
                    return

            self.store.set_state(wid, "completed")
            self.store.append_event(wid, "completed", {"completed_at": datetime.utcnow().isoformat()})
        finally:
            INFLIGHT_REQUESTS.dec()

    async def _execute_task(self, wid: str, spec: TaskSpec, shared: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        await self.semaphore.acquire()
        tid = None
        try:
            tid = self.store.upsert_task(
                workflow_id=wid, name=spec.name, state="running", attempts=0, error=None,
                result=None, started_at=datetime.utcnow().isoformat(), finished_at=None
            )
            attempts = 0
            delay = spec.backoff_base or self.default_backoff
            retries = spec.retries if spec.retries is not None else self.default_retries
            timeout = spec.timeout_sec or self.default_timeout
            task_fn = get_task(spec.name)

            while True:
                attempts += 1
                try:
                    async def run():
                        return await task_fn({"shared": shared, "results": results}, spec.args)

                    if timeout:
                        res = await asyncio.wait_for(run(), timeout=timeout)
                    else:
                        res = await run()

                    self.store.upsert_task(
                        workflow_id=wid, name=spec.name, state="completed",
                        attempts=attempts, error=None, result=res or {},
                        started_at=None, finished_at=datetime.utcnow().isoformat(), task_id=tid
                    )
                    self.store.append_event(wid, "task_completed", {"task": spec.id, "name": spec.name})
                    return res or {}
                except asyncio.CancelledError:
                    self.store.upsert_task(
                        workflow_id=wid, name=spec.name, state="canceled",
                        attempts=attempts, error="canceled", result=None,
                        started_at=None, finished_at=datetime.utcnow().isoformat(), task_id=tid
                    )
                    self.store.append_event(wid, "task_canceled", {"task": spec.id})
                    raise
                except Exception as e:
                    err = f"{type(e).__name__}: {e}"
                    tb = traceback.format_exc(limit=4)
                    self.store.upsert_task(
                        workflow_id=wid, name=spec.name, state="failed",
                        attempts=attempts, error=f"{err}\n{tb}", result=None,
                        started_at=None, finished_at=datetime.utcnow().isoformat(), task_id=tid
                    )
                    self.store.append_event(wid, "task_failed", {"task": spec.id, "error": err})
                    if attempts > retries:
                        raise
                    await asyncio.sleep(delay)
                    delay *= 2.0
        finally:
            try:
                self.semaphore.release()
            except Exception:
                pass


# Example built-in tasks (safe baselines). Extend via register_task.

@register_task("noop")
async def task_noop(ctx: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "args": args}

@register_task("merge")
async def task_merge(ctx: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    out.update(ctx.get("shared") or {})
    out.update(args or {})
    return out