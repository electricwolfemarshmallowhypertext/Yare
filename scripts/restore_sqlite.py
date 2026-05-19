#!/usr/bin/env python3
"""
Restore SQLite from latest backup produced by backup_sqlite.py.
Usage:
  python scripts/restore_sqlite.py --db ./data/memory/fallback.db --from ./data/backups
"""

from __future__ import annotations
import argparse
from pathlib import Path
import gzip
import shutil
import re


def latest_backup(dirpath: Path) -> Path:
    files = sorted(dirpath.glob("sqlite_*.db.gz"), reverse=True)
    if not files:
        raise FileNotFoundError("No backups found")
    return files[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Destination DB path to restore to")
    ap.add_argument("--from", dest="src", required=True, help="Backup directory containing .gz files")
    args = ap.parse_args()

    src_dir = Path(args.src)
    dst = Path(args.db)
    src_gz = latest_backup(src_dir)

    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".restoring.db")

    with gzip.open(src_gz, "rb") as f_in, open(tmp, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    if dst.exists():
        dst.unlink()
    tmp.rename(dst)
    print(f"Restored {dst} from {src_gz}")

if __name__ == "__main__":
    main()