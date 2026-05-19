#!/usr/bin/env bash
# One-liner deploy installer for VPS (SQLite path by default).
# Usage:
#   bash scripts/deploy.sh                 # uses docker-compose.yml (SQLite)
#   bash scripts/deploy.sh pg              # uses docker-compose.pg.yml (Postgres + migrator)

set -euo pipefail

COMPOSE="docker-compose.yml"
if [[ "${1:-}" == "pg" ]]; then
  COMPOSE="docker-compose.pg.yml"
fi

# prerequisites
command -v docker >/dev/null || { echo "docker not installed"; exit 1; }
command -v docker compose >/dev/null || command -v docker-compose >/dev/null || { echo "docker compose not installed"; exit 1; }

# secrets
mkdir -p secrets data/backups
if [[ ! -f secrets/api_keys.txt ]]; then
  echo "Generating default API key (admin|*)..."
  KEY="$(python - <<'PY'
from cryptography.fernet import Fernet
import secrets
print(secrets.token_urlsafe(32))
PY
)"
  echo "${KEY}:admin|*" > secrets/api_keys.txt
  echo "Wrote secrets/api_keys.txt (admin key printed below)"
  echo "ADMIN_API_KEY=${KEY}"
fi
if [[ ! -f secrets/fernet.key ]]; then
  python - <<'PY' > secrets/fernet.key
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
  echo "Wrote secrets/fernet.key"
fi

# build and run
if docker compose version >/dev/null 2>&1; then
  docker compose -f "${COMPOSE}" up -d --build
else
  docker-compose -f "${COMPOSE}" up -d --build
fi

# health check
echo "Waiting for service..."
sleep 5
set +e
for i in {1..30}; do
  STATUS=$(curl -fsS http://localhost:8000/health 2>/dev/null || true)
  if [[ -n "$STATUS" ]]; then
    echo "Health: $STATUS"
    break
  fi
  sleep 2
done
set -e

echo "Done. Visit:"
echo "- API:        http://YOUR_HOST:8000"
echo "- Dashboard:  http://YOUR_HOST:8000/dashboard"
echo "- Metrics:    http://YOUR_HOST:9090/metrics"