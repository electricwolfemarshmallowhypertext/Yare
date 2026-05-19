"""
Factory to choose SQLite or Postgres store based on env.
"""

import os
from .persistence import MemoryStore
from .persistence_pg import PostgresStore


def get_store(sqlite_path: str):
    pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if pg_url:
        return PostgresStore(pg_url)
    return MemoryStore(sqlite_path)