from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest
<<<<<<< HEAD
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

triage_runs_total = Counter("triage_runs_total", "Total triage pipeline executions", ["status"])
triage_retries_total = Counter("triage_retries_total", "Verifier-triggered retries")
triage_tokens_total = Counter("triage_tokens_total", "LLM tokens consumed", ["agent"])
triage_latency_seconds = Histogram("triage_latency_seconds", "End-to-end triage latency", buckets=[0.5, 1, 2, 4, 8, 16, 30])
tool_calls_total = Counter("tool_calls_total", "MCP tool invocations", ["tool_name", "status"])
tool_latency_seconds = Histogram("tool_latency_seconds", "Per-tool latency", ["tool_name"])
verifier_confidence = Histogram("verifier_confidence", "Confidence scores from Verifier", buckets=[0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95])
hallucination_events_total = Counter("hallucination_events_total", "Detected hallucinated log attributions")
triage_pipeline_latency = Histogram("triage_pipeline_latency_seconds", "Time to triage an incident", buckets=[1, 5, 10, 30, 60])
llm_cost_usd_total = Counter("llm_cost_usd_total", "LLM cost in USD", ["agent", "model"])
embedding_latency_seconds = Histogram("embedding_latency_seconds", "Embedding latency", ["provider"])
chunk_processing_latency_seconds = Histogram("chunk_processing_latency_seconds", "Time to process a single log chunk")
schema_validation_failures_total = Counter("schema_validation_failures_total", "Pydantic validation failures", ["model"])
triage_pipeline_phase_duration = Histogram("triage_pipeline_phase_duration_seconds", "Duration of triage phase", ["phase"])
from prometheus_client import Gauge
active_triage_jobs = Gauge("active_triage_jobs", "Currently active triage jobs")
=======
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
REQUEST_COUNT = Counter(
    "logiq_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "logiq_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        # Always use the route template (e.g. /api/v1/incidents/{incident_id}) so
        # Prometheus labels stay low-cardinality; fall back to "_unmatched" for
        # requests that hit no registered route.
        route = request.scope.get("route")
        path = route.path if route else "_unmatched"
        REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
        return response


def metrics_response(request: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

