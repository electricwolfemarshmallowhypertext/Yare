#!/usr/bin/env bash
# Lightweight local dev runner: starts Redis (Docker) if needed and runs uvicorn with SQLite.
set -euo pipefail

PORT="${PORT:-8000}"
METRICS_PORT="${METRICS_PORT:-9090}"

if ! redis-cli -u redis://localhost:6379 ping >/dev/null 2>&1; then
  echo "[dev] Starting Redis via Docker..."
  docker run --name sticky-redis -p 6379:6379 -d --rm redis:7-alpine >/dev/null
fi

export ENV="${ENV:-development}"
export LOG_LEVEL="${LOG_LEVEL:-DEBUG}"
export SQLITE_PATH="${SQLITE_PATH:-data/memory/fallback.db}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export ALLOWED_ORIGINS="*"
export TRUSTED_HOSTS="*"

mkdir -p "$(dirname "$SQLITE_PATH")"

echo "[dev] Running server on :$PORT (metrics :$METRICS_PORT)"
python -m uvicorn src.memory.server:app --reload --host 0.0.0.0 --port "$PORT"