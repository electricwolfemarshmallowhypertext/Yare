# Observability

## Metrics
- Prometheus endpoint on `:9090/metrics`
- Key metrics:
  - memory_cache_hits_total / memory_cache_misses_total
  - memory_db_operations_total{op,status}
  - memory_db_operation_seconds_bucket
  - memory_rate_limit_decisions_total
  - memory_auth_decisions_total

## Tracing
- Set `OTLP_ENDPOINT` to enable OTEL gRPC export.

## Logging
- JSON via structlog (stdout). Ingest with your log shipper (e.g., Vector, Fluent Bit).
- Include request context (client_ip) in logs.

## Alerts (examples)
- High 5xx rate
- Rate limiting spikes
- DB operation errors
- Health degraded