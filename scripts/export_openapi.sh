#!/usr/bin/env bash
# Export OpenAPI spec and a minimal Postman collection.

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
OUT_DIR="${OUT_DIR:-docs}"
mkdir -p "$OUT_DIR"

echo "[openapi] Fetching $BASE_URL/openapi.json ..."
curl -fsS "$BASE_URL/openapi.json" -o "$OUT_DIR/openapi.json"

# Minimal Postman collection wrapper
echo "[openapi] Generating minimal Postman collection ..."
python - <<'PY'
import json, sys, os
out = {
  "info": {"name": "Memory Service", "_postman_id": "memory-service", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
  "item": [
    {"name": "Health", "request": {"method": "GET", "url": "{{base_url}}/health"}},
    {"name": "Status", "request": {"method": "GET", "url": "{{base_url}}/status"}},
    {"name": "List Personas", "request": {"method": "GET", "header":[{"key":"Authorization","value":"Bearer {{api_token}}"}], "url": "{{base_url}}/persona"}},
  ],
  "variable": [{"key":"base_url","value":"http://localhost:8000"},{"key":"api_token","value":""}]
}
p=os.environ.get("OUT_DIR","docs")
open(os.path.join(p,"postman_collection.json"),"w").write(json.dumps(out, indent=2))
print("[openapi] Wrote docs/postman_collection.json")
PY