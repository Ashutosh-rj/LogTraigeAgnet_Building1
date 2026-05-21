from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# JWT blocklist — Redis-backed in production, in-process fallback for dev.
#
# Redis stores each revoked jti as:   SETEX  jti:<jti>  <ttl_seconds>  "1"
# The TTL is set to the access token's remaining lifetime, so the key
# expires automatically and no janitor job is needed.
#
# In development (no REDIS_URL), a process-local set is used.  This is
# explicitly unsafe for multi-worker deployments and will raise at startup
# if is_production is True and redis_url is absent (enforced below).
# ---------------------------------------------------------------------------

_local_blocklist: set[str] = set()
_redis_client: "redis.asyncio.Redis | None" = None  # type: ignore[name-defined]


def _get_redis() -> "redis.asyncio.Redis | None":  # type: ignore[name-defined]
    global _redis_client
    settings = get_settings()
    if not settings.redis_url:
        if settings.is_production:
            raise RuntimeError(
                "REDIS_URL is required in production for a cross-process JWT blocklist. "
                "Without it, revoked tokens remain valid after a worker restart or across replicas."
            )
        return None
    if _redis_client is None:
        import redis.asyncio as aioredis  # lazy import — not required in dev
        _redis_client = aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis_client


async def blocklist_token(jti: str, ttl_seconds: int | None = None) -> None:  # type: ignore[override]
    """Revoke a JWT by its jti claim.

    *ttl_seconds* should be set to the token's remaining lifetime so the
    Redis key expires automatically.  When omitted it defaults to twice the
    configured access-token lifetime (a safe upper bound).
    """
    settings = get_settings()
    if ttl_seconds is None:
        ttl_seconds = settings.access_token_expire_minutes * 60 * 2

    client = _get_redis()
    if client is not None:
        await client.setex(f"jti:{jti}", ttl_seconds, "1")
    else:
        _local_blocklist.add(jti)


async def is_blocked(jti: str) -> bool:  # type: ignore[override]
    """Return True if the jti has been revoked."""
    client = _get_redis()
    if client is not None:
        return bool(await client.exists(f"jti:{jti}"))
    return jti in _local_blocklist


def hash_password(password: str) -> str:
    settings = get_settings()
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode(
        "utf-8"
    )


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def create_access_token(subject: str, email: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        # Coerce to str unconditionally: the ORM may return a UUID or int
<<<<<<< HEAD
        # object instead of a str, which would produce a non-string
=======
        # object instead of a str, which would produce a non-string 
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
        # claim that later str() coercions in get_current_user would mangle.
        "sub": str(subject),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "typ": "access",
        "jti": secrets.token_hex(16),
    }
<<<<<<< HEAD
    # Always sign with the primary (current) secret
=======
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
    return jwt.encode(payload, settings.effective_jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and structurally validate an access token (sync — no blocklist check).

<<<<<<< HEAD
    Supports JWT key rotation: tries primary secret first, then falls back to
    the secondary secret if configured.  This allows zero-downtime key rotation —
    existing tokens signed with the old key remain valid during the rotation window.

=======
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
    Use ``decode_access_token_async`` in FastAPI dependency/route code so the
    Redis blocklist is consulted.  This sync variant exists for WebSocket auth
    and test helpers that run outside an async context.
    """
<<<<<<< HEAD
    settings = get_settings()
    last_exc: Exception | None = None

    for secret in settings.effective_jwt_secrets:
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            if payload.get("typ") != "access" or not payload.get("sub"):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            return payload
        except jwt.PyJWTError as exc:
            last_exc = exc
            continue  # try next key in rotation list

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
    ) from last_exc
=======
    try:
        payload = jwt.decode(token, get_settings().effective_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if payload.get("typ") != "access" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818


async def decode_access_token_async(token: str) -> dict[str, Any]:
    """Decode, validate, and blocklist-check an access token (async).

    This is the preferred function for all FastAPI route dependencies.
    """
    payload = decode_access_token(token)
    if await is_blocked(payload.get("jti", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    return payload
