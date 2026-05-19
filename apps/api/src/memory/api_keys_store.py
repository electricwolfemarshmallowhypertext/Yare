from __future__ import annotations

from typing import Optional, Dict, Any, List, Set
from datetime import datetime
import json
import secrets

import structlog
from sqlalchemy import create_engine, Table, Column, MetaData, String, Text, select, insert, update

from .security import ApiKeyAuth

logger = structlog.get_logger("memory.api_keys_store")


class ApiKeyStore:
    """
    API key storage and management using SQLAlchemy Core.
    Schema:
      api_keys(
        key_hash TEXT PRIMARY KEY,
        roles TEXT (JSON array),
        tier TEXT,
        org_id TEXT,
        created_at TEXT,
        revoked_at TEXT NULL
      )
    """

    def __init__(self, db_url: str) -> None:
        self.engine = create_engine(db_url, pool_pre_ping=True)
        self.meta = MetaData()
        self.api_keys = Table(
            "api_keys",
            self.meta,
            Column("key_hash", String, primary_key=True),
            Column("roles", Text, nullable=False),
            Column("tier", String, nullable=False),
            Column("org_id", String, nullable=True),
            Column("created_at", String, nullable=False),
            Column("revoked_at", String, nullable=True),
        )
        self.meta.create_all(self.engine)

    def create_key(self, roles: Set[str], tier: str, org_id: Optional[str] = None) -> Dict[str, Any]:
        api_key = secrets.token_urlsafe(32)
        key_hash = ApiKeyAuth.hash_key(api_key)
        doc = {
            "key_hash": key_hash,
            "roles": json.dumps(sorted(list(roles))),
            "tier": tier,
            "org_id": org_id,
            "created_at": datetime.utcnow().isoformat(),
            "revoked_at": None,
        }
        with self.engine.begin() as cx:
            cx.execute(insert(self.api_keys).values(**doc))
        logger.info("api_key_created", tier=tier, roles=sorted(list(roles)), org_id=org_id)
        return {"api_key": api_key, "tier": tier, "roles": sorted(list(roles)), "key_hash": key_hash, "org_id": org_id}

    def revoke_key(self, key_hash: str) -> bool:
        with self.engine.begin() as cx:
            res = cx.execute(
                update(self.api_keys).where(self.api_keys.c.key_hash == key_hash).values(revoked_at=datetime.utcnow().isoformat())
            )
            return res.rowcount > 0

    def list_keys(self, include_revoked: bool = False) -> List[Dict[str, Any]]:
        stmt = select(self.api_keys)
        with self.engine.begin() as cx:
            rows = cx.execute(stmt).mappings().all()
        out: List[Dict[str, Any]] = []
        for r in rows:
            if not include_revoked and r.get("revoked_at"):
                continue
            out.append(
                {
                    "key_hash": r["key_hash"],
                    "roles": json.loads(r["roles"]),
                    "tier": r["tier"],
                    "org_id": r["org_id"],
                    "created_at": r["created_at"],
                    "revoked_at": r["revoked_at"],
                }
            )
        return out

    def upgrade_tier(self, key_hash: str, tier: str) -> bool:
        with self.engine.begin() as cx:
            res = cx.execute(update(self.api_keys).where(self.api_keys.c.key_hash == key_hash).values(tier=tier))
            return res.rowcount > 0

    def get_roles_and_tier_by_plain(self, api_key: str) -> Optional[Dict[str, Any]]:
        key_hash = ApiKeyAuth.hash_key(api_key)
        return self.get_roles_and_tier_by_hash(key_hash)

    def get_roles_and_tier_by_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        stmt = select(self.api_keys).where(self.api_keys.c.key_hash == key_hash).limit(1)
        with self.engine.begin() as cx:
            row = cx.execute(stmt).mappings().first()
        if not row or row.get("revoked_at"):
            return None
        return {"roles": set(json.loads(row["roles"])), "tier": row["tier"], "key_hash": row["key_hash"], "org_id": row["org_id"]}