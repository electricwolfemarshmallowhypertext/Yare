from __future__ import annotations

import inspect
from typing import Any


async def maybe_await(value: Any) -> Any:
    """
    Await a coroutine or return a plain value unchanged.
    Use this to call store methods that might be sync or async.
    """
    if inspect.isawaitable(value):
        return await value
    return value