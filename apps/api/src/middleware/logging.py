from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import logging
import json
import time
import uuid
from typing import Optional, Set

# Middleware metadata
MIDDLEWARE_METADATA = {
    "created_at": "2025-11-02 18:49:16",
    "created_by": "electricwolfemarshmallowhypertext",
    "version": "1.0.0"
}

class JSONLogFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        
        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
            
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
            
        # Add error information
        if record.exc_info:
            log_data["error"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
            
        # Add any extra attributes
        if hasattr(record, "extra"):
            log_data.update(record.extra)
            
        return json.dumps(log_data)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Logging middleware with structured output"""
    
    def __init__(
        self,
        app,
        logger_name: str = "sticky.api",
        log_level: str = "INFO",
        exclude_paths: Optional[Set[str]] = None,
        created_at: str = MIDDLEWARE_METADATA["created_at"],
        created_by: str = MIDDLEWARE_METADATA["created_by"]
    ):
        super().__init__(app)
        
        # Configure logger
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, log_level))
        
        # Add JSON formatter if not already present
        if not any(isinstance(h.formatter, JSONLogFormatter) for h in self.logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(JSONLogFormatter())
            self.logger.addHandler(handler)
            
        self.exclude_paths = exclude_paths or {"/health"}
        self._created_at = created_at
        self._created_by = created_by
        
        # Configure sensitive headers
        self.sensitive_headers = {
            "authorization",
            "x-api-key",
            "cookie",
            "session"
        }
        
    async def dispatch(
        self,
        request: Request,
        call_next
    ) -> Response:
        """Process request and log details"""
        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Skip detailed logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
            
        start_time = time.time()
        
        # Log request start
        self.logger.info(
            json.dumps({
                "event": "request_start",
                "timestamp": datetime.utcnow().isoformat(),
                "request": {
                    "id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "headers": self._sanitize_headers(dict(request.headers)),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent")
                }
            })
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Log request completion
            self.logger.info(
                json.dumps({
                    "event": "request_complete",
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": request_id,
                    "response": {
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "headers": self._sanitize_headers(dict(response.headers))
                    }
                })
            )
            
            # Add response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Log error
            self.logger.error(
                json.dumps({
                    "event": "request_error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": request_id,
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "duration_ms": duration_ms
                    }
                }),
                exc_info=True
            )
            raise
            
    def _sanitize_headers(self, headers: dict) -> dict:
        """Remove sensitive information from headers"""
        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in self.sensitive_headers:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized