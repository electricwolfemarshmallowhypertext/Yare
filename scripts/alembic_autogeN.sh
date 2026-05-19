#!/usr/bin/env bash
# Complete Alembic autogenerate example.
# Usage:
#   export DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
#   bash scripts/alembic_autogen.sh "add priority column"

set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set"; exit 1
fi

MSG="${1:-schema update}"

# Ensure deps
python -m pip install --upgrade pip >/dev/null
pip install alembic sqlalchemy psycopg2-binary >/dev/null

# Create new autogen revision
alembic revision --autogenerate -m "$MSG"

# Apply migrations
alembic upgrade head

echo "Alembic autogenerate complete."