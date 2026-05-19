from __future__ import annotations

import os
import time
import structlog
from typing import Optional

logger = structlog.get_logger("memory.watchdog")

# Optional psutil; we fall back to /proc/self/status on Linux
try:
    import psutil  # type: ignore
except Exception:
    psutil = None  # type: ignore


def _rss_bytes_psutil() -> Optional[int]:
    try:
        p = psutil.Process(os.getpid())  # type: ignore
        return int(p.memory_info().rss)
    except Exception:
        return None


def _rss_bytes_proc() -> Optional[int]:
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    # VmRSS:   123456 kB
                    kb = int(parts[1])
                    return kb * 1024
    except Exception:
        return None
    return None


def rss_bytes() -> int:
    val = _rss_bytes_psutil()
    if val is not None:
        return val
    val = _rss_bytes_proc()
    return val or 0


def report(cache_stats: dict | None = None) -> None:
    """
    Log RSS and optional cache stats. Call from a background scheduler.
    """
    logger.info(
        "watchdog",
        rss=rss_bytes(),
        cache_stats=cache_stats or {},
        ts=int(time.time()),
    )