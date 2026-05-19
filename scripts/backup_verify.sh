#!/usr/bin/env bash
# Verify the latest SQLite backup by restoring to a temp path and checking integrity.
# Usage: BACKUP_DIR=data/backups DB_PATH=data/memory/fallback.db bash scripts/backup_verify.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-data/backups}"
DB_PATH="${DB_PATH:-data/memory/fallback.db}"
TMP_DB="${TMP_DB:-${DB_PATH%.db}.verify.db}"

if ! ls "$BACKUP_DIR"/sqlite_*.db.gz >/dev/null 2>&1; then
  echo "[verify] No backups found in $BACKUP_DIR"
  exit 1
fi

LATEST="$(ls -1t "$BACKUP_DIR"/sqlite_*.db.gz | head -n1)"
echo "[verify] Restoring $LATEST -> $TMP_DB"
python scripts/restore_sqlite.py --db "$TMP_DB" --from "$BACKUP_DIR"

echo "[verify] Running PRAGMA integrity_check..."
python - <<PY
import sqlite3, sys
path = sys.argv[1]
con = sqlite3.connect(path)
res = con.execute("PRAGMA integrity_check").fetchone()
print(res[0])
con.close()
PY
"$TMP_DB" | grep -q "ok" && echo "[verify] SQLite integrity OK" || { echo "[verify] Integrity check failed"; exit 2; }

rm -f "$TMP_DB"
echo "[verify] Cleaned up. Backup verified."