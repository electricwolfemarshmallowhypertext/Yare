from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, Type, Iterable, Any, Optional, Tuple


def _calc_sleep(base: float, factor: float, attempt: int, jitter: Tuple[float, float]) -> float:
    sleep = base * (factor ** max(0, attempt - 1))
    jmin, jmax = jitter
    return sleep + random.uniform(jmin, jmax)


def retry(
    func: Callable[[], Any],
    retries: int = 3,
    base: float = 0.05,
    factor: float = 2.0,
    jitter: Tuple[float, float] = (0.0, 0.05),
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
) -> Any:
    """
    Synchronous retry with exponential backoff and jitter.
    """
    attempt = 0
    while True:
        try:
            return func()
        except retry_on:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(_calc_sleep(base, factor, attempt, jitter))


async def retry_async(
    func: Callable[[], Any],
    retries: int = 3,
    base: float = 0.05,
    factor: float = 2.0,
    jitter: Tuple[float, float] = (0.0, 0.05),
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
) -> Any:
    """
    Async retry with exponential backoff and jitter.
    """
    attempt = 0
    while True:
        try:
            res = func()
            if asyncio.iscoroutine(res):
                return await res
            return res
        except retry_on:
            attempt += 1
            if attempt > retries:
                raise
            await asyncio.sleep(_calc_sleep(base, factor, attempt, jitter))