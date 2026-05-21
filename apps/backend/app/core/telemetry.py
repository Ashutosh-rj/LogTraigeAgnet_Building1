from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import get_settings


def configure_telemetry(app: FastAPI) -> None:
    settings = get_settings()
    if settings.otel_exporter_otlp_endpoint:
        resource = Resource.create({"service.name": "logiq-backend", "environment": settings.environment})
        provider = TracerProvider(resource=resource)
        
        # Configure OTLP Exporter
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        
        trace.set_tracer_provider(provider)
        
        FastAPIInstrumentor.instrument_app(app)

def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
