from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    String, Integer, Text, select, insert, update, and_
)
from sqlalchemy.engine import Engine

logger = structlog.get_logger("memory.metering")


class UsageMeter:
    """
    Per-API-key usage metering (daily), by route.
    Schema:
      api_usage(
        key_hash TEXT,
        day TEXT (YYYY-MM-DD),
        route TEXT,
        count INTEGER,
        PRIMARY KEY (key_hash, day, route)
      )
    Works with SQLite and Postgres.
    """
    def __init__(self, db_url: str) -> None:
        self.engine: Engine = create_engine(db_url, pool_pre_ping=True)
        self.meta = MetaData()
        self.api_usage = Table(
            "api_usage",
            self.meta,
            Column("key_hash", String, primary_key=True),
            Column("day", String, primary_key=True),
            Column("route", String, primary_key=True),
            Column("count", Integer, nullable=False),
        )
        self.meta.create_all(self.engine)

    def record_call(self, key_hash: str, route: str) -> None:
        day = datetime.utcnow().strftime("%Y-%m-%d")
        with self.engine.begin() as cx:
            # generic upsert: try update, if no row updated then insert
            stmt_upd = (
                update(self.api_usage)
                .where(
                    and_(
                        self.api_usage.c.key_hash == key_hash,
                        self.api_usage.c.day == day,
                        self.api_usage.c.route == route,
                    )
                )
                .values(count=self.api_usage.c.count + 1)
            )
            res = cx.execute(stmt_upd)
            if res.rowcount == 0:
                cx.execute(insert(self.api_usage).values(key_hash=key_hash, day=day, route=route, count=1))

    def usage_for_key(self, key_hash: str) -> List[Dict[str, Any]]:
        stmt = select(self.api_usage).where(self.api_usage.c.key_hash == key_hash)
        with self.engine.begin() as cx:
            rows = cx.execute(stmt).mappings().all()
        return [{"day": r["day"], "route": r["route"], "count": r["count"]} for r in rows]

    def usage_summary(self, limit_days: int = 30) -> List[Dict[str, Any]]:
        stmt = select(self.api_usage)
        with self.engine.begin() as cx:
            rows = cx.execute(stmt).mappings().all()
        return [{"key_hash": r["key_hash"], "day": r["day"], "route": r["route"], "count": r["count"]} for r in rows]