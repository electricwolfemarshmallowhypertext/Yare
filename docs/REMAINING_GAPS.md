# Remaining Gaps (Full Disclosure)

- Security
  - Real SSO/OAuth beyond API keys
  - Secret manager integration (HashiCorp Vault/AWS/GCP) instead of files
  - Full RBAC policy management UI and audit export

- Data
  - Postgres read/write sharding strategy (if needed at scale)
  - Background compaction/archival policies

- Testing
  - Full pen-test suite, fuzzing on all endpoints
  - Chaos testing scenarios (Redis down, DB failover)
  - Load profiles for different traffic shapes

- Observability
  - Grafana dashboards for latency per endpoint
  - SLOs and error budget policies

- Product features (roadmap)
  - Deeper self-reflection with embeddings/models
  - Rich orchestrator agent registry + sandboxing
  - Advanced ethical policy rules and explainers