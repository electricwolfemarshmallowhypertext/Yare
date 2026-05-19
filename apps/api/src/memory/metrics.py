from prometheus_client import Counter, Histogram, Gauge

# Cache metrics
CACHE_HITS = Counter(
    "memory_cache_hits_total",
    "Total cache hits",
    ["cache", "op"],
)
CACHE_MISSES = Counter(
    "memory_cache_misses_total",
    "Total cache misses",
    ["cache", "op"],
)
CACHE_OP_DURATION = Histogram(
    "memory_cache_operation_seconds",
    "Duration of cache operations in seconds",
    ["op"],
)

# Rate limiting
RATE_LIMIT_DECISIONS = Counter(
    "memory_rate_limit_decisions_total",
    "Rate limiting decisions (allowed/blocked/error_allow)",
    ["key", "decision"],
)

# DB metrics
DB_OPS = Counter(
    "memory_db_operations_total",
    "Database operations",
    ["op", "status"],
)
DB_OP_DURATION = Histogram(
    "memory_db_operation_seconds",
    "Duration of database operations in seconds",
    ["op"],
)

# Security
AUTH_DECISIONS = Counter(
    "memory_auth_decisions_total",
    "Authentication/authorization decisions",
    ["decision", "reason"],
)

# General gauges
STORE_SIZE_BYTES = Gauge(
    "memory_store_size_bytes",
    "Approximate size of the memory store in bytes",
)

INFLIGHT_REQUESTS = Gauge(
    "memory_inflight_requests",
    "Number of in-flight orchestrator tasks or requests",
)

# HTTP metrics (used by dashboards/alerts)
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_ERRORS = Counter(
    "http_server_errors_total",
    "Total HTTP 5xx responses",
    ["path"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)