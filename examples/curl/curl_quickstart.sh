#!/usr/bin/env bash
# Quickstart cURL examples
BASE=${BASE:-http://localhost:8000}
echo "# Health"
curl -s "$BASE/health" | jq .
echo "# Status"
curl -s "$BASE/status" | jq .