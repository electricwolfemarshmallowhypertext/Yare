from __future__ import annotations

from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta
import json
import structlog

from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    String, Text, select, insert
)
from sqlalchemy.engine import Engine

from .utils import calculate_memory_stats

logger = structlog.get_logger("memory.analytics")

_ANALYZERS: Dict[str, Callable[[Any], Dict[str, Any]]] = {}


def register_analyzer(name: str):
    def deco(fn: Callable[[Any], Dict[str, Any]]):
        _ANALYZERS[name] = fn
        return fn
    return deco


class AnalyticsStore:
    def __init__(self, db_url: str) -> None:
        self.engine: Engine = create_engine(db_url, pool_pre_ping=True)
        self.meta = MetaData()
        self.analytics = Table(
            "analytics_results", self.meta,
            Column("id", String, primary_key=True),
            Column("name", String, nullable=False),
            Column("data", Text, nullable=False),
            Column("created_at", String, nullable=False),
        )
        self.meta.create_all(self.engine)

    def write(self, name: str, data: Dict[str, Any]) -> None:
        with self.engine.begin() as cx:
            cx.execute(insert(self.analytics).values(
                id=f"an_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
                name=name,
                data=json.dumps(data),
                created_at=datetime.utcnow().isoformat(),
            ))


class AnalyticsEngine:
    """
    Pluggable analytics pipeline.
    Default analyzers:
      - memory_stats: distribution, size, counts by type/persona
      - recent_activity: last 24h counts
    Extend via @register_analyzer.
    """

    def __init__(self, store, db_url: str, interval_seconds: int = 900):
        self.store = store
        self.interval = interval_seconds
        self.a_store = AnalyticsStore(db_url=db_url)

    async def run_once(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, fn in _ANALYZERS.items():
            try:
                res = fn(self.store)
                out[name] = res
                self.a_store.write(name, res)
            except Exception as e:
                logger.warning("analyzer_failed", name=name, error=str(e))
        return out

    async def _analyze_recent(self) -> Dict[str, Any]:
        return await self.run_once()


@register_analyzer("memory_stats")
def analyze_memory_stats(store) -> Dict[str, Any]:
    mems = store.query(limit=2000)
    return calculate_memory_stats(mems)

@register_analyzer("recent_activity")
def analyze_recent_activity(store) -> Dict[str, Any]:
    mems = store.query(limit=2000)
    now = datetime.utcnow()
    last_24h = sum(1 for m in mems if str(m.get("created_at","")).startswith(str(now.date())))
    return {"last_24h": last_24h}