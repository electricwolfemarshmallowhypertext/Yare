#!/usr/bin/env bash
set -euo pipefail

echo "[1/6] Install deps"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov flake8 mypy bandit safety

echo "[2/6] Lint"
flake8 src tests

echo "[3/6] Type-check"
mypy src

echo "[4/6] Tests"
pytest --maxfail=1 --disable-warnings -q

echo "[5/6] Security"
bandit -r src -q || true
safety check || true

echo "[6/6] Build image"
docker build -t memory-service:local .
echo "OK"