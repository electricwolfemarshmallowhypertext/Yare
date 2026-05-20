"""
Prometheus endpoint + optional OpenTelemetry tracing.
"""

from typing import Optional
import structlog
from prometheus_client import start_http_server

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    OTEL_AVAILABLE = True
except Exception:
    trace = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[assignment]
    OTLPSpanExporter = None  # type: ignore[assignment]
    BatchSpanProcessor = None  # type: ignore[assignment]
    OTEL_AVAILABLE = False

logger = structlog.get_logger("memory.monitoring")


class Monitoring:
    def __init__(self, metrics_port: int = 9090, otlp_endpoint: Optional[str] = None) -> None:
        self.metrics_port = metrics_port
        self.otlp_endpoint = otlp_endpoint

    def start(self, service_name: str = "memory-service", env: str = "production") -> None:
        try:
            start_http_server(self.metrics_port)
            logger.info("prometheus_started", port=self.metrics_port)
        except Exception as e:
            logger.warning("prometheus_start_failed", error=str(e))

        if self.otlp_endpoint:
            if not OTEL_AVAILABLE:
                logger.warning("otel_tracing_unavailable", reason="missing_opentelemetry_dependency")
                return
            try:
                resource = Resource.create({"service.name": service_name, "deployment.environment": env})
                provider = TracerProvider(resource=resource)
                exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
                processor = BatchSpanProcessor(exporter)
                provider.add_span_processor(processor)
                trace.set_tracer_provider(provider)
                logger.info("otel_tracing_initialized", endpoint=self.otlp_endpoint)
            except Exception as e:
                logger.warning("otel_tracing_failed", error=str(e))
