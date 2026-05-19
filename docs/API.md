# OpenAPI and Postman

- Export OpenAPI: bash scripts/export_openapi.sh (requires server running)
  - Outputs: docs/openapi.json
- Minimal Postman collection: docs/postman_collection.json

Import docs/postman_collection.json into Postman and set:
- base_url: http://localhost:8000
- api_token: your Bearer token (if using protected routes)