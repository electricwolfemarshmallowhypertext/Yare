"""
Simple async scheduler for periodic/background tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable, Dict, Any, Optional, List
import asyncio
import time
import structlog

logger = structlog.get_logger("memory.scheduler")


@dataclass
class Job:
    id: str
    interval: float
    coro_factory: Callable[[], Awaitable[Any]]
    next_run: float


class AsyncScheduler:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._task_factories: Dict[str, Callable[[], Awaitable[Any]]] = {}
        self._bg_tasks: Dict[str, asyncio.Task] = {}
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def add_interval_job(self, job_id: str, interval_seconds: float, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        self._jobs[job_id] = Job(id=job_id, interval=interval_seconds, coro_factory=coro_factory, next_run=time.time() + interval_seconds)

    def add_task(self, job_id: str, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        self._task_factories[job_id] = coro_factory

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        for job_id, factory in self._task_factories.items():
            t = self._bg_tasks.get(job_id)
            if t and not t.done():
                continue
            self._bg_tasks[job_id] = asyncio.create_task(self._run_named_task(job_id, factory))
        if self._jobs:
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        for task in self._bg_tasks.values():
            if not task.done():
                task.cancel()
        if self._bg_tasks:
            await asyncio.gather(*self._bg_tasks.values(), return_exceptions=True)
        if self._task:
            await asyncio.wait([self._task], timeout=5)

    async def _run_named_task(self, job_id: str, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        try:
            await coro_factory()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning("job_failed", job_id=job_id, error=str(e))

    async def _run_loop(self) -> None:
        logger.info("scheduler_started", jobs=len(self._jobs))
        try:
            while not self._stop.is_set():
                now = time.time()
                due = [j for j in self._jobs.values() if j.next_run <= now]
                for job in due:
                    asyncio.create_task(self._run_job(job))
                    job.next_run = now + job.interval
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
        finally:
            logger.info("scheduler_stopped")

    async def _run_job(self, job: Job) -> None:
        try:
            await job.coro_factory()
            logger.info("job_completed", job_id=job.id)
        except Exception as e:
            logger.warning("job_failed", job_id=job.id, error=str(e))
