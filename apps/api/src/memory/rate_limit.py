from __future__ import annotations

import time
from typing import Optional

import redis
from redis.client import Script
import structlog

from .retry import retry

logger = structlog.get_logger("memory.rate_limit")


LUA_FIXED_WINDOW = """
-- KEYS[1] -> rate limit key
-- ARGV[1] -> limit (integer)
-- ARGV[2] -> window_ms (integer)
local current = redis.call("INCR", KEYS[1])
if current == 1 then
  redis.call("PEXPIRE", KEYS[1], ARGV[2])
end
if current > tonumber(ARGV[1]) then
  return {0, current}
else
  return {1, current}
end
"""


class LocalFallback:
    """
    Simple in-process fixed-window limiter as a fallback if Redis is unavailable.
    Not distributed; only prevents total unthrottled flood during an outage window.
    """
    def __init__(self):
        self._buckets = {}  # key -> (count, reset_ts)

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        count, reset = self._buckets.get(key, (0, 0.0))
        if now >= reset:
            count, reset = 0, now + window_seconds
        count += 1
        self._buckets[key] = (count, reset)
        return count <= limit


class RateLimiter:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = redis.from_url(redis_url, decode_responses=False)
        # Preload script
        try:
            self.lua: Script = self.redis.register_script(LUA_FIXED_WINDOW)
        except Exception as e:
            logger.warning("rate_limit_lua_register_failed", error=str(e))
            self.lua = None  # type: ignore
        self.local = LocalFallback()

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Fixed-window limiter with atomic Redis script and local fallback.
        """
        window_ms = int(window_seconds * 1000)

        def _call():
            if self.lua:
                try:
                    res = self.lua(keys=[key], args=[limit, window_ms])
                    # res is [allowed, current]
                    return bool(res and int(res[0]) == 1)
                except Exception as e:
                    logger.warning("rate_limit_lua_failed", error=str(e))
            # Pipeline fallback
            with self.redis.pipeline() as pipe:
                pipe.incr(key)
                pipe.pexpire(key, window_ms)
                inc, _ = pipe.execute()
                return int(inc) <= limit

        try:
            return retry(_call, retries=3, base=0.01, factor=2.0)
        except Exception as e:
            logger.error("rate_limit_redis_down_fallback_local", error=str(e))
            # Fallback local short-circuit
            return self.local.allow(key, limit, window_seconds)