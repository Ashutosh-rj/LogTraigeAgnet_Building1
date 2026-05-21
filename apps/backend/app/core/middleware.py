from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from fastapi import Request, Response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        # Attach request_id and route to the active OTEL span for trace correlation
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("http.request_id", request_id)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", str(request.url.path))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
        response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["content-security-policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "connect-src 'self' ws: wss:; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none';"
        )
        if get_settings().environment.lower() != "development":
            # Apply HSTS on staging and production — omit only in local dev where
            # HTTPS is typically not configured and the header would break HTTP.
            response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
        return response


_AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    # NOTE: This rate limiter is process-local. In a multi-worker or
    # multi-replica deployment, replace the in-process store inside rate_limiter
    # with a shared Redis-backed store (e.g. redis-py with a sliding-window
    # Lua script). Single-node, single-worker deployments are fully protected.
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in {"/health/live", "/health/ready", "/metrics"}:
            return await call_next(request)
        settings = get_settings()
        client = request.client.host if request.client else "unknown"
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        try:
            if request.url.path in _AUTH_PATHS:
                # Tighter per-IP limit for login and register endpoints, tracked
                # in a separate bucket so auth attempts don't consume the global quota.
                await rate_limiter.enforce(
                    f"rl:auth:{client}",
                    settings.auth_rate_limit_requests,
                    settings.rate_limit_window_seconds,
                )
            if request.url.path == "/api/v1/auth/login":
                # Use a distinct prefix (rl:login-ip) so this IP-keyed bucket
                # does not collide with the per-email bucket (rl:login-account)
                # enforced inside AuthService.login().  Both limits apply
                # independently: exceeding either one results in a 429.
                await rate_limiter.enforce(
                    f"rl:login-ip:{client}",
                    settings.login_rate_limit_requests,
                    settings.rate_limit_window_seconds,
                )
            await rate_limiter.enforce(
                f"rl:req:{client}:{route_path}",
                settings.rate_limit_requests,
                settings.rate_limit_window_seconds,
            )
        except HTTPException:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Body size limit — reject oversized payloads before the body is read.
# Prevents slow-loris-style memory exhaustion attacks on log ingest endpoints.
# ---------------------------------------------------------------------------

_SQL_INJECTION_PATTERNS = [
    r"(?i)(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bCREATE\b|\bALTER\b)",
    r"(?i)(-{2}|/\*|\*/|;\s*(--|#))",  # SQL comment sequences
    r"(?i)(\bOR\b\s+\d+=\d+|\bAND\b\s+\d+=\d+)",  # classic tautologies
    r"(?i)(\bEXEC\b|\bEXECUTE\b|\bXP_\w+)",  # stored proc injection
    r"'\s*(;|--|OR|AND)",  # quote + terminator sequences
]

import re
_SQL_COMPILED = [re.compile(p) for p in _SQL_INJECTION_PATTERNS]

_SEARCH_PARAMS = {"q", "query", "search", "filter", "keyword"}


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length header exceeds the configured limit.

    Note: this checks the *declared* Content-Length only.  For chunked-encoded
    requests without a Content-Length header the body is read by the route
    handler, which should apply its own size guard via Pydantic field limits.
    """
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > settings.max_request_body_size_bytes:
                    return JSONResponse(
                        {"detail": f"Request body too large (max {settings.max_request_body_size_bytes // 1024 // 1024} MB)"},
                        status_code=413,
                    )
            except ValueError:
                pass  # malformed Content-Length; let the handler deal with it
        return await call_next(request)


class SearchSanitizationMiddleware(BaseHTTPMiddleware):
    """Detect SQL injection patterns in query parameters on search endpoints.

    Blocks requests where search/query params contain common SQL injection
    sequences.  This is a defence-in-depth layer — the ORM's parameterised
    queries already prevent injection, but this catches it at the HTTP boundary
    and returns an explicit 400 with no stack trace exposed.
    """
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in {"GET", "POST"} and any(
            seg in request.url.path for seg in ("/search", "/incidents", "/logs")
        ):
            for param_name, param_value in request.query_params.items():
                if param_name.lower() in _SEARCH_PARAMS:
                    for pattern in _SQL_COMPILED:
                        if pattern.search(param_value):
                            return JSONResponse(
                                {"detail": "Invalid characters in search query"},
                                status_code=400,
                            )
        return await call_next(request)
