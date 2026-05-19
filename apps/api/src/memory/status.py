from __future__ import annotations

from typing import Dict, Any, Optional
from prometheus_client import REGISTRY


def _metric_value(name: str, labels: Optional[Dict[str, str]] = None) -> float:
    total = 0.0
    for metric in REGISTRY.collect():
        if metric.name != name:
            continue
        for s in metric.samples:
            if labels:
                match = True
                for k, v in labels.items():
                    if s.labels.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            try:
                total += float(s.value)
            except Exception:
                pass
    return total


def snapshot() -> Dict[str, Any]:
    """
    Returns a small JSON-friendly snapshot derived from Prometheus metrics.
    Note: For rates (like 5m), use Prometheus itself; here we expose totals.
    """
    return {
        "requests_total": _metric_value("http_requests_total"),
        "errors_5xx_total": _metric_value("http_server_errors_total"),
        "rate_limited_total": _metric_value("memory_rate_limit_decisions_total", {"decision": "block"}),
        "auth_denies_total": _metric_value("memory_auth_decisions_total", {"decision": "deny"}),
    }