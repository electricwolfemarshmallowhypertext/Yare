#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

import redis
from sqlalchemy import create_engine, text


def ok(msg: str):
    print(f"[OK] {msg}")


def fail(msg: str):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Yare config sanity check")
    ap.add_argument("--strict", action="store_true", help="Fail on warnings")
    args = ap.parse_args()

    # Secrets
    api_keys = os.getenv("API_KEYS") or (os.getenv("API_KEYS_FILE") and "FILE")
    fernet = os.getenv("ENCRYPTION_KEY_PATH") or os.getenv("FERNET_KEY_PATH")
    if not (api_keys or fernet):
        print("[WARN] No API keys or Fernet key configured yet (ok for local/dev)")

    # Rate plans JSON
    rp = os.getenv("RATE_PLANS")
    if rp:
        try:
            obj = json.loads(rp)
            assert isinstance(obj, dict)
            ok("RATE_PLANS parsed")
        except Exception as e:
            fail(f"RATE_PLANS invalid JSON: {e}")
    else:
        print("[WARN] RATE_PLANS not set, using defaults")

    # Redis
    rurl = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(rurl)
        r.ping()
        ok(f"Redis reachable: {rurl}")
    except Exception as e:
        fail(f"Redis not reachable: {rurl} ({e})")

    # DB
    db = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if not db:
        ok("No DATABASE_URL set (SQLite path will be used)")
    else:
        try:
            eng = create_engine(db, pool_pre_ping=True)
            with eng.begin() as cx:
                cx.execute(text("SELECT 1"))
            ok(f"DB reachable: {db}")
        except Exception as e:
            fail(f"DB not reachable: {db} ({e})")

    ok("Config check complete")


if __name__ == "__main__":
    main()
