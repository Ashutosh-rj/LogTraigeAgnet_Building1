from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from fastapi import Request, Response
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
