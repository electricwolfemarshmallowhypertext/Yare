#!/usr/bin/env python3
"""
Simple migration runner for SQLite. Records applied migrations in schema_migrations.
Usage:
  python scripts/migrate.py --db ./data/memory/fallback.db --migrations ./migrations
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sqlite3


def applied(cx) -> set[str]:
    cx.execute("CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY)")
    rows = cx.execute("SELECT id FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def apply_migration(cx, mig_id: str, sql: str) -> None:
    cx.executescript(sql)
    cx.execute("INSERT INTO schema_migrations(id) VALUES (?)", (mig_id,))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--migrations", required=True)
    args = ap.parse_args()

    mig_dir = Path(args.migrations)
    cx = sqlite3.connect(args.db)
    try:
        done = applied(cx)
        for path in sorted(mig_dir.glob("*.sql")):
            mid = path.stem
            if mid in done:
                continue
            sql = path.read_text()
            apply_migration(cx, mid, sql)
            print(f"Applied migration {mid}")
        cx.commit()
    finally:
        cx.close()


if __name__ == "__main__":
    main()