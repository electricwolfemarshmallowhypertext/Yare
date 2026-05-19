"""
ASGI middleware to collect HTTP metrics:
- http_requests_total{method,path,status}
- http_server_errors_total{path}
- http_request_duration_seconds_bucket{method,path}
"""

from __future__ import annotations

import time
from typing import Callable, Awaitable
from starlette.types import ASGIApp, Receive, Scope, Send
from urllib.parse import urlsplit

from .metrics import HTTP_REQUESTS, HTTP_ERRORS, HTTP_REQUEST_DURATION


def _normalize_path(path: str) -> str:
    # Collapse dynamic segments for cardinality control if desired.
    # Minimal version: keep as-is; can add patterns if routes cause explosion.
    return path


class HttpMetricsMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope.get("method", "GET")
        raw_path = scope.get("path", "/")
        path = _normalize_path(raw_path)
        status_code_holder = {"status": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_holder["status"] = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            dur = time.perf_counter() - start
            status = str(status_code_holder["status"])
            HTTP_REQUESTS.labels(method=method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(dur)
            if status.startswith("5"):
                HTTP_ERRORS.labels(path=path).inc()