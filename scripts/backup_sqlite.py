#!/usr/bin/env python3
"""
SQLite snapshot, rotation, and integrity verification.
Usage:
  python scripts/backup_sqlite.py --db ./data/memory/fallback.db --out ./backups --retention 7
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
from datetime import datetime
import shutil
import hashlib
import gzip
import sqlite3
import sys


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sqlite(db_path: Path) -> None:
    cx = sqlite3.connect(str(db_path))
    try:
        cx.execute("PRAGMA integrity_check;").fetchone()
    finally:
        cx.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--retention", type=int, default=7)
    args = ap.parse_args()

    db = Path(args.db)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if not db.exists():
        print(f"DB not found: {db}", file=sys.stderr)
        sys.exit(1)

    # Integrity check before snapshot
    verify_sqlite(db)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    snap = out / f"sqlite_{ts}.db"
    shutil.copy2(db, snap)

    # Integrity check after copy
    verify_sqlite(snap)

    # Compress
    gz_path = out / f"{snap.name}.gz"
    with open(snap, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    os.remove(snap)

    # Write checksum
    sha = checksum(gz_path)
    (out / f"{gz_path.name}.sha256").write_text(f"{sha}  {gz_path.name}\n")

    # Rotation
    gz_files = sorted(out.glob("sqlite_*.db.gz"), reverse=True)
    for f in gz_files[args.retention:]:
        chk = out / f"{f.name}.sha256"
        if chk.exists():
            chk.unlink()
        f.unlink()

    print(f"Backup completed: {gz_path} (sha256 {sha})")


if __name__ == "__main__":
    main()