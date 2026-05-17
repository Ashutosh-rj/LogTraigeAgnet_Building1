from __future__ import annotations

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.core.config import get_settings


def configure_telemetry(app: FastAPI) -> None:
    if get_settings().otel_exporter_otlp_endpoint:
        FastAPIInstrumentor.instrument_app(app)

