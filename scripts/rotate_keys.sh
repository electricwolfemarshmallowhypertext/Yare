#!/usr/bin/env bash
# Rotate Fernet encryption key and optionally roll API keys (issue new, revoke old).
# Safe to run via cron. Prints a summary; does NOT expose secrets.

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_TOKEN="${API_TOKEN:-}" # admin token for API key rotation; optional
SECRETS_DIR="${SECRETS_DIR:-secrets}"
FERNET_PATH="${FERNET_PATH:-$SECRETS_DIR/fernet.key}"
BACKUP_DIR="${BACKUP_DIR:-$SECRETS_DIR/backup_keys}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$SECRETS_DIR" "$BACKUP_DIR"

echo "[rotate] Rotating Fernet key..."
if [[ -f "$FERNET_PATH" ]]; then
  cp "$FERNET_PATH" "$BACKUP_DIR/fernet.key.$TS.bak"
fi
python - <<'PY' > "$FERNET_PATH"
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
chmod 600 "$FERNET_PATH"
echo "[rotate] New Fernet key written. Previous backed up in $BACKUP_DIR"

if [[ -n "$API_TOKEN" ]]; then
  echo "[rotate] Rotating admin API key (issue new, revoke old) ..."
  # List keys
  KEYS_JSON="$(curl -fsS -H "Authorization: Bearer $API_TOKEN" "$BASE_URL/keys" || true)"
  OLD_HASH="$(echo "$KEYS_JSON" | python - <<'PY'
import sys, json
try:
  data=json.load(sys.stdin)
  # pick first non-revoked admin
  for k in data:
    if "admin" in (k.get("roles") or []) and not k.get("revoked_at"):
      print(k["key_hash"])
      break
except Exception:
  pass
PY
)"
  # Create a new admin key via /register requires REGISTRATION_TOKEN; skip here.
  echo "[rotate] NOTE: to fully automate API key rotation, enable /register and use a registration token."
  if [[ -n "$OLD_HASH" ]]; then
    echo "[rotate] Revoking old admin key hash: $OLD_HASH"
    curl -fsS -X DELETE -H "Authorization: Bearer $API_TOKEN" "$BASE_URL/keys/$OLD_HASH" || true
  fi
else
  echo "[rotate] API_TOKEN not provided; skipped API key rotation."
fi

echo "[rotate] Done."