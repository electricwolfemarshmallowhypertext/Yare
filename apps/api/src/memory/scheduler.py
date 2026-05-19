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
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def add_interval_job(self, job_id: str, interval_seconds: float, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        self._jobs[job_id] = Job(id=job_id, interval=interval_seconds, coro_factory=coro_factory, next_run=time.time() + interval_seconds)

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await asyncio.wait([self._task], timeout=5)

    async def _run_loop(self) -> None:
        logger.info("scheduler_started", jobs=len(self._jobs))
        try:
            while not self._stop.is_set():
                now = time.time()
                due = [j for j in self._jobs.values() if j.next_run <= now]
                for job in due:
                    asyncio.create_task(self._run_job(job))
                    job.next_run = now + job.interval
                await asyncio.wait([self._stop.wait()], timeout=0.5)
        finally:
            logger.info("scheduler_stopped")

    async def _run_job(self, job: Job) -> None:
        try:
            await job.coro_factory()
            logger.info("job_completed", job_id=job.id)
        except Exception as e:
            logger.warning("job_failed", job_id=job.id, error=str(e))