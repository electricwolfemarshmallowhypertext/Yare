#!/usr/bin/env bash
# Persona flow (requires API token and org)
BASE=${BASE:-http://localhost:8000}
TOKEN=${TOKEN:-}
ORG=${ORG:-org-123}
set -e
echo "# List personas"
curl -s -H "Authorization: Bearer $TOKEN" -H "X-Org-Id: $ORG" "$BASE/persona" | jq .
echo "# Import persona"
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "X-Org-Id: $ORG" -H "Content-Type: application/json" \
  -d '{"name":"writer","traits":["concise","clear"]}' "$BASE/persona/import" | jq .