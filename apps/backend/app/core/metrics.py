from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

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

