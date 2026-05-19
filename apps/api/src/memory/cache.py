"""
Redis-backed cache with a correct local LRU for embeddings.
- Async-friendly wrapper around blocking redis client
- Uses centralized metrics from metrics.py
- OrderedDict for LRU with size-bound entries
"""

from typing import Any, Optional, List
import json
import asyncio
import structlog
import redis
from collections import OrderedDict
import xxhash

from .metrics import CACHE_HITS, CACHE_MISSES, CACHE_OP_DURATION

logger = structlog.get_logger("memory.cache")


class MemoryCache:
    def __init__(
        self,
        redis_url: str,
        prefix: str = "memory:",
        default_ttl: int = 3600,
        embedding_max_entries: int = 10_000,
    ) -> None:
        self.prefix = prefix
        self.default_ttl = default_ttl

        try:
            self.redis = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
        except Exception as e:
            logger.error("redis_connect_failed", error=str(e))
            raise

        self._embeddings: "OrderedDict[str, List[float]]" = OrderedDict()
        self._embeddings_max = embedding_max_entries
        self._embeddings_lock = asyncio.Lock()

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}"

    async def get(self, key: str, cache_type: str = "general") -> Optional[Any]:
        k = self._k(key)
        with CACHE_OP_DURATION.labels("get").time():
            try:
                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(None, self.redis.get, k)
                if data is None:
                    CACHE_MISSES.labels(cache=cache_type, op="get").inc()
                    return None
                CACHE_HITS.labels(cache=cache_type, op="get").inc()
                return json.loads(data)
            except Exception as e:
                logger.warning("cache_get_error", key=key, error=str(e))
                return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, cache_type: str = "general"
    ) -> bool:
        k = self._k(key)
        payload = json.dumps(value, separators=(",", ":"))
        with CACHE_OP_DURATION.labels("set").time():
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.redis.setex, k, ttl or self.default_ttl, payload)
                return True
            except Exception as e:
                logger.warning("cache_set_error", key=key, error=str(e))
                return False

    async def delete(self, key: str, cache_type: str = "general") -> bool:
        k = self._k(key)
        with CACHE_OP_DURATION.labels("delete").time():
            try:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(None, self.redis.delete, k)
                return bool(res)
            except Exception as e:
                logger.warning("cache_delete_error", key=key, error=str(e))
                return False

    # Convenience: accept raw text and hash it consistently for embedding keys.
    @staticmethod
    def _hash_text(text: str) -> str:
        return xxhash.xxh64(text.encode("utf-8")).hexdigest()

    async def get_embedding_text(self, text: str) -> Optional[List[float]]:
        return await self.get_embedding(self._hash_text(text))

    async def set_embedding_text(self, text: str, embedding: List[float], ttl: Optional[int] = None) -> bool:
        return await self.set_embedding(self._hash_text(text), embedding, ttl)

    async def get_embedding(self, text_hash: str) -> Optional[List[float]]:
        async with self._embeddings_lock:
            if text_hash in self._embeddings:
                vec = self._embeddings.pop(text_hash)
                self._embeddings[text_hash] = vec
                CACHE_HITS.labels(cache="embedding", op="local").inc()
                return vec

        val = await self.get(f"embedding:{text_hash}", cache_type="embedding")
        if val is not None:
            await self._put_embedding_local(text_hash, val)
            return val

        CACHE_MISSES.labels(cache="embedding", op="lookup").inc()
        return None

    async def set_embedding(self, text_hash: str, embedding: List[float], ttl: Optional[int] = None) -> bool:
        await self._put_embedding_local(text_hash, embedding)
        return await self.set(
            f"embedding:{text_hash}", embedding, ttl=ttl or self.default_ttl, cache_type="embedding"
        )

    async def _put_embedding_local(self, key: str, embedding: List[float]) -> None:
        async with self._embeddings_lock:
            if key in self._embeddings:
                self._embeddings.pop(key)
            self._embeddings[key] = embedding
            while len(self._embeddings) > self._embeddings_max:
                self._embeddings.popitem(last=False)

    async def cleanup(self) -> None:
        try:
            async with self._embeddings_lock:
                self._embeddings.clear()
            self.redis.close()
            try:
                self.redis.connection_pool.disconnect()
            except Exception:
                pass
        except Exception as e:
            logger.warning("cache_cleanup_error", error=str(e))