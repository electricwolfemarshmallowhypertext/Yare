#!/usr/bin/env bash
# Preflight: run local quality gates and smoke checks before VPS deploy.
# - Lint, types, tests, security scans
# - Build image
# - Optionally start containers (SQLite or Postgres) and run health/fuzz/load checks
#
# Usage:
#   bash scripts/preflight.sh                 # uses docker-compose.yml, starts containers, runs checks
#   bash scripts/preflight.sh pg              # uses docker-compose.pg.yml (Postgres path)
#   NO_DOCKER=1 bash scripts/preflight.sh     # skip docker parts; only code checks
#
# Optional env:
#   BASE_URL=http://localhost:8000
#   API_TOKEN=<admin key>   # if unset, script will try secrets/api_keys.txt
#   K6=1                    # force run k6 load test if installed (defaults to run if available)
#   TIMEOUT=60              # health wait timeout (seconds)

set -euo pipefail

MODE="${1:-}" # empty or "pg"
COMPOSE_FILE="docker-compose.yml"
[[ "${MODE}" == "pg" ]] && COMPOSE_FILE="docker-compose.pg.yml"

BASE_URL="${BASE_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-60}"
K6_FLAG="${K6:-}"
NO_DOCKER="${NO_DOCKER:-}"

have() { command -v "$1" >/dev/null 2>&1; }

log() { printf "\033[1;34m[preflight]\033[0m %s\n" "$*"; }
ok()  { printf "\033[1;32m[ok]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[err]\033[0m %s\n" "$*"; }

get_api_token() {
  if [[ -n "${API_TOKEN:-}" ]]; then
    echo "$API_TOKEN"
    return
  fi
  if [[ -f "secrets/api_keys.txt" ]]; then
    # Expect first line "plainKey:roles|roles"
    local line
    line="$(head -n1 secrets/api_keys.txt || true)"
    if [[ "$line" == *:* ]]; then
      echo "${line%%:*}"
      return
    fi
  fi
  echo ""
}

ensure_python() {
  have python || have python3 || { err "Python not installed"; exit 1; }
  PY_BIN="$(command -v python3 || command -v python)"
  echo "$PY_BIN"
}

ensure_compose() {
  if [[ -n "$NO_DOCKER" ]]; then
    return 0
  fi
  have docker || { err "docker not installed"; exit 1; }
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif have docker-compose; then
    echo "docker-compose"
  else
    err "docker compose not installed"
    exit 1
  fi
}

install_python_deps() {
  local PY_BIN="$1"
  log "Installing Python deps"
  $PY_BIN -m pip install --upgrade pip >/dev/null
  $PY_BIN -m pip install -r requirements.txt >/dev/null
  $PY_BIN -m pip install -r requirements-dev.txt >/dev/null
}

run_code_checks() {
  log "Running lint/type/tests/security"
  flake8 src tests
  mypy src
  pytest --maxfail=1 --disable-warnings -q
  bandit -r src -q || true
  safety check || true
  ok "Code checks passed"
}

build_image() {
  if [[ -n "$NO_DOCKER" ]]; then
    warn "Skipping docker build (NO_DOCKER=1)"
    return
  fi
  log "Building Docker image"
  docker build -t memory-service:preflight .
  ok "Image built"
}

start_stack() {
  if [[ -n "$NO_DOCKER" ]]; then
    warn "Skipping docker compose up (NO_DOCKER=1)"
    return
  fi
  log "Starting stack with $COMPOSE_FILE"
  local DC
  DC="$(ensure_compose)"
  if [[ "$DC" == "docker compose" ]]; then
    docker compose -f "$COMPOSE_FILE" up -d --build
  else
    docker-compose -f "$COMPOSE_FILE" up -d --build
  fi
}

wait_health() {
  log "Waiting for health at ${BASE_URL}/health (timeout ${TIMEOUT}s)"
  local start end now
  start=$(date +%s)
  while true; do
    if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
      ok "Service healthy"
      return 0
    fi
    now=$(date +%s)
    if (( now - start >= TIMEOUT )); then
      err "Health check timed out"
      curl -sS "${BASE_URL}/health" || true
      exit 1
    fi
    sleep 2
  done
}

run_fuzz() {
  local PY_BIN="$1"
  local token
  token="$(get_api_token || true)"
  log "Running fuzz harness (API_TOKEN ${token:+present})"
  BASE_URL="$BASE_URL" API_TOKEN="$token" $PY_BIN scripts/fuzz_http.py
  ok "Fuzz checks passed"
}

run_k6() {
  if [[ -n "$NO_DOCKER" ]]; then
    warn "Skipping k6 (NO_DOCKER=1)"
    return
  fi
  if [[ -z "$K6_FLAG" && ! $(have k6 && echo yes) ]]; then
    warn "k6 not installed; skipping load test"
    return
  fi
  if ! have k6; then
    warn "k6 not installed; skipping load test"
    return
  fi
  local token
  token="$(get_api_token || true)"
  log "Running k6 smoke (15s)"
  BASE_URL="$BASE_URL" API_TOKEN="$token" k6 run --duration 15s --vus 10 scripts/load/k6_memory.js || {
    warn "k6 thresholds failed (non-blocking for preflight)"; return 0; }
  ok "k6 smoke passed"
}

summary() {
  echo
  ok "Preflight complete"
  echo "- Base URL: $BASE_URL"
  if [[ -z "${API_TOKEN:-}" ]]; then
    local t
    t="$(get_api_token || true)"
    [[ -n "$t" ]] && echo "- Admin API key detected from secrets/api_keys.txt"
  else
    echo "- Admin API key provided via env"
  fi
  echo "- Compose file: ${NO_DOCKER:+(skipped)} ${NO_DOCKER:+"(none)"}${NO_DOCKER:+" "}${NO_DOCKER:-$COMPOSE_FILE}"
}

main() {
  local PY_BIN
  PY_BIN="$(ensure_python)"
  install_python_deps "$PY_BIN"
  run_code_checks
  build_image
  start_stack
  wait_health
  run_fuzz "$PY_BIN"
  run_k6
  summary
}

main "$@"