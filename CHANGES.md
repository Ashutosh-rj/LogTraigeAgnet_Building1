## [Unreleased] — Critical Bug Fixes (2026-05-17)

### Fixed
- **[CRIT-1] services/auth.py refresh()** — moved null check before expires_at access to prevent AttributeError on missing token row.
- **[CRIT-2] services/websocket.py WebSocketManager.connect()** — removed duplicate websocket.accept(); route handler already accepts before auth.
- **[CRIT-3] core/middleware.py RateLimitMiddleware** — renamed per-IP login bucket to rl:login-ip:{ip}, eliminating collision with per-email rl:login-account:{email} bucket.
- **[CRIT-4] db/models.py + main.py** — added validate_embedding_dimensions() called at startup to detect DB/config dimension mismatches before the first request.


# Critical Bug Fixes

## Critical 1 — JWT blocklist moved to Redis (was in-process set)

**File:** `apps/backend/app/core/security.py`

**Problem:** The JWT revocation blocklist was a plain Python `set` stored in module memory. Any process restart, pod rollout, or worker reload silently wiped all revoked tokens, allowing them to be reused. In multi-worker deployments each worker had its own copy, so a token revoked in worker A was still accepted by worker B.

**Fix:**
- `blocklist_token(jti, ttl_seconds)` is now `async` and writes to Redis via `SETEX jti:<jti> <ttl> 1`. The TTL equals the token's remaining lifetime so the key auto-expires — no janitor job needed.
- `is_blocked(jti)` is now `async` and reads from Redis via `EXISTS`.
- A process-local `set` is retained as a fallback **for development only** (no `REDIS_URL`). Attempting to run in production without `REDIS_URL` raises `RuntimeError` at startup.
- New `decode_access_token_async(token)` function performs the full validation + blocklist check. All FastAPI route dependencies and WebSocket auth now use this async variant. The original sync `decode_access_token()` remains for contexts that cannot be async (e.g. JWT structure checks before an event loop is available).

**Affected files:** `core/security.py`, `api/deps.py`, `api/routes/ws.py`, `services/auth.py`, `tests/test_auth.py`, `tests/test_security.py`, `tests/conftest.py`

---

## Critical 2 — Rate limiter production guard + dev warning

**File:** `apps/backend/app/core/rate_limit.py`

**Problem:** The rate limiter stored sliding windows in a per-process `defaultdict`. In any multi-worker or multi-replica deployment, each process tracked limits independently — an attacker got `N_workers × limit` requests per window. The class was named `SharedRateLimiter` but shared nothing across processes.

**Fix:**
- `_get_client()` (renamed from `_redis()`) now emits a `warnings.warn` on first use when `REDIS_URL` is absent and environment is not production, making the limitation visible in dev logs.
- In production (`ENVIRONMENT=production`) without `REDIS_URL`, the limiter raises `RuntimeError` immediately on the first rate-limit check rather than silently degrading.
- Redis path unchanged (INCR + conditional EXPIRE).

**Affected files:** `core/rate_limit.py`

---

## Critical 3 — Database engine creation moved to lazy factory

**File:** `apps/backend/app/db/session.py`

**Problem:** The SQLAlchemy engine and session factory were instantiated at module import time (`engine = create_async_engine(settings.database_url, ...)`). This meant:
1. Tests that monkeypatched `DATABASE_URL` after the module was first imported got the wrong engine.
2. The engine could not be reconfigured without a process restart.

**Fix:**
- `get_engine()` and `get_session_factory()` are now `@lru_cache`-decorated functions. The engine is created on first call, after any monkeypatching has taken effect.
- `get_session()` (the FastAPI dependency) calls `get_session_factory()()` instead of using the module-level `AsyncSessionLocal`.
- The old `engine` and `AsyncSessionLocal` module-level names are removed. Code that imported them directly must be updated to call `get_engine()`.
- `tests/conftest.py` clears both caches in the `test_env` fixture teardown so each test gets a fresh engine.

**Affected files:** `db/session.py`, `tests/conftest.py`

---

## Critical 4 — Refresh token removed from sessionStorage

**File:** `apps/frontend/src/store/auth-store.ts`

**Problem:** The refresh token was stored in `sessionStorage` (the code's own `TODO` acknowledged this). `sessionStorage` is readable by any JavaScript running on the page — a single XSS vulnerability allows an attacker to exfiltrate the refresh token and maintain persistent access.

**Fix:**
- All `sessionStorage.getItem/setItem/removeItem` calls for the refresh token have been removed from the auth store.
- The store now relies entirely on the `httpOnly` cookie set by the backend (`_set_refresh_cookie` in `api/routes/auth.py`). The browser sends this cookie automatically on requests to `/api/v1/auth/*` because `credentials: "include"` is already set in `api.ts`.
- `rehydrate()` and `refresh()` no longer pass a token argument to `api.refresh()` — the cookie is the sole credential.
- `api.refresh()` in `api.ts` is unchanged (it never accepted arguments); the previously-passed-but-ignored argument is no longer passed.
- The `RT_KEY` constant and the `TODO` comment have been removed.

**Affected files:** `frontend/src/store/auth-store.ts`, `frontend/src/lib/api.ts`
