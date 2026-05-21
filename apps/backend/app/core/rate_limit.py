from __future__ import annotations

import time
import warnings
from collections import defaultdict, deque

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Rate limiter — Redis-backed sliding window in production.
#
# Redis path: uses INCR + conditional EXPIRE so the window is consistent
# across all workers and replicas without a Lua transaction.
#
# Local fallback: sliding deque, safe for a single-process dev server only.
# If REDIS_URL is absent and ENVIRONMENT != production, a one-time warning is
# emitted at first use.  In production the fallback is forbidden.
# ---------------------------------------------------------------------------

class SharedRateLimiter:
    """Cross-process sliding-window rate limiter.

    • With REDIS_URL set:   uses Redis INCR/EXPIRE — shared across workers.
    • Without REDIS_URL:    uses an in-process deque — single-worker dev only.
                            Production raises at first call if URL is absent.
    """

    def __init__(self) -> None:
        self._client: Redis | None = None
        self._local: dict[str, deque[float]] = defaultdict(deque)
        # Instance-level flag so the warning fires once per SharedRateLimiter
        # instance rather than being permanently suppressed after the first
        # import.  Module reloads (test re-imports, dev hot-reload) therefore
        # produce the warning again, which is the correct behaviour.
        self._local_warning_issued: bool = False

    def _get_client(self) -> Redis | None:
        settings = get_settings()

        if not settings.redis_url:
            if settings.is_production:
                raise RuntimeError(
                    "REDIS_URL is required in production for shared rate limiting. "
                    "Without it each worker tracks limits independently, allowing "
                    "N_workers × limit requests per window."
                )
            if not self._local_warning_issued:
                # stacklevel=1 points at this call site inside SharedRateLimiter,
                # which is the most useful location for debugging.  stacklevel=2
                # would erroneously point at Starlette's middleware dispatcher.
                warnings.warn(
                    "Rate limiter is using an in-process fallback (no REDIS_URL). "
                    "This is NOT shared across workers or replicas. "
                    "Set REDIS_URL for correct behaviour in multi-worker deployments.",
                    stacklevel=1,
                )
                self._local_warning_issued = True
            return None

        if self._client is None:
            self._client = Redis.from_url(
                settings.redis_url, encoding="utf-8", decode_responses=True
            )
        return self._client

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Increment the counter for *key* and return True if within limit."""
        client = self._get_client()

        if client is not None:
            current = await client.incr(key)
            if current == 1:
                await client.expire(key, window_seconds)
            return int(current) <= limit

        # --- in-process fallback (dev only) ---
        now = time.monotonic()
        bucket = self._local[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if within limit, without incrementing the counter."""
        client = self._get_client()
        if client is not None:
            current = await client.get(key)
            return int(current or 0) < limit

        now = time.monotonic()
        bucket = self._local[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        return len(bucket) < limit

    async def clear(self, key: str) -> None:
        """Clear the counter for a key."""
        client = self._get_client()
        if client is not None:
            await client.delete(key)
        else:
            self._local.pop(key, None)

    async def enforce(self, key: str, limit: int, window_seconds: int) -> None:
        """Raise HTTP 429 if the request exceeds the rate limit."""
        if not await self.hit(key, limit, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )


rate_limiter = SharedRateLimiter()
