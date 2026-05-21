from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.core.security import (
    blocklist_token,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.db.models import RefreshToken, Role, User
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair
from app.schemas.users import UserRead
from app.services.audit import AuditService
from app.services.events import event_publisher

import structlog as _structlog

_log = _structlog.get_logger()


<<<<<<< HEAD
import structlog as _structlog

_log = _structlog.get_logger()
=======
# TODO: move counter to Redis for multi-process deployments.
# The dict is capped at _LOGIN_FAIL_COUNTER_MAX_ENTRIES to prevent unbounded
# memory growth in long-running single-process deployments.  When the cap is
# reached the oldest entry is evicted (FIFO via dict insertion order, Python 3.7+).
_LOGIN_FAIL_COUNTER_MAX_ENTRIES = 10_000
_login_fail_counter: dict[str, int] = {}
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    async def register(self, payload: RegisterRequest, request: Request | None = None) -> TokenPair:
        settings = get_settings()
        email = str(payload.email).lower()
        if not settings.allow_public_registration:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public registration is disabled; bootstrap an admin with app.seed",
            )
        existing = await self.users.get_by_email(email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
        user_count = int((await self.session.execute(select(func.count(User.id)))).scalar_one())
        role = Role.viewer
        if user_count == 0:
            # Always promote the first registered user to admin — this is intentional
            # bootstrap behaviour. Subsequent registrations always receive Role.viewer.
            role = Role.admin
            _log.warning(
                "first_admin_created",
                email=email,
                environment=settings.environment,
            )
        user = await self.users.create(
            email=email,
            name=payload.name.strip(),
            password_hash=hash_password(payload.password),
            role=role,
        )
        token_pair, _ = await self._issue_tokens(user, request)
        await self.audit.record(
            actor=user,
            action="auth.register",
            resource_type="user",
            resource_id=user.id,
            request=request,
        )
        await self.session.commit()
        await event_publisher.publish(
            "identity.events",
            {"event": "user.registered", "resource_id": user.id, "email": user.email},
        )
        return token_pair

    async def login(self, payload: LoginRequest, request: Request | None = None) -> TokenPair:
<<<<<<< HEAD
        settings = get_settings()
        email = str(payload.email).lower()
        await rate_limiter.enforce(
            f"rl:login-account:{email}",
            settings.login_account_rate_limit_requests,
            settings.rate_limit_window_seconds,
        )

        lockout_key = f"rl:lockout:{email}"
        is_locked = not await rate_limiter.check(lockout_key, settings.account_lockout_max_attempts, settings.account_lockout_duration_seconds)
        if is_locked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account locked due to too many failed attempts")

        user = await self.users.get_by_email(email)
        if not user or not verify_password(payload.password, user.password_hash):
            is_now_locked = not await rate_limiter.hit(lockout_key, settings.account_lockout_max_attempts, settings.account_lockout_duration_seconds)
            if is_now_locked:
                _log.error("excessive_login_failures", email=email)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        
        await rate_limiter.clear(lockout_key)
=======
        email = str(payload.email).lower()
        await rate_limiter.enforce(
            f"rl:login-account:{email}",
            get_settings().login_account_rate_limit_requests,
            get_settings().rate_limit_window_seconds,
        )
        user = await self.users.get_by_email(email)
        if not user or not verify_password(payload.password, user.password_hash):
            # Evict oldest entry if the counter dict has grown too large.
            if len(_login_fail_counter) >= _LOGIN_FAIL_COUNTER_MAX_ENTRIES:
                _login_fail_counter.pop(next(iter(_login_fail_counter)))
            _login_fail_counter[email] = _login_fail_counter.get(email, 0) + 1
            threshold = get_settings().login_fail_alert_threshold
            if _login_fail_counter[email] >= threshold:
                _log.error(
                    "excessive_login_failures",
                    email=email,
                    count=_login_fail_counter[email],
                )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        _login_fail_counter.pop(email, None)  # reset on successful auth
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
        user.last_login_at = datetime.now(UTC)
        token_pair, _ = await self._issue_tokens(user, request)
        await self.audit.record(
            actor=user,
            action="auth.login",
            resource_type="user",
            resource_id=user.id,
            request=request,
        )
        await self.session.commit()
        return token_pair

    async def refresh(self, refresh_token: str, request: Request | None = None) -> TokenPair:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
        )
        stored_token = result.scalar_one_or_none()
        now = datetime.now(UTC)
        # Guard: check existence and revocation before touching any column.
        if stored_token is None or stored_token.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        # Normalise expires_at to a tz-aware datetime so the comparison is
        # always apples-to-apples.  Tokens created before the UTC column
        # migration may be stored without tzinfo; treat them as UTC.
        expires_at = stored_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        user = await self.users.get_by_id(stored_token.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        stored_token.revoked_at = now
        token_pair, replacement = await self._issue_tokens(user, request)
        stored_token.replaced_by_token_id = replacement.id
        await self.audit.record(
            actor=user,
            action="auth.refresh",
            resource_type="refresh_token",
            resource_id=stored_token.id,
            request=request,
        )
        await self.session.commit()
        return token_pair

    async def logout(self, refresh_token: str, request: Request | None = None, access_token: str | None = None) -> None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
        )
        stored_token = result.scalar_one_or_none()
        if stored_token and stored_token.revoked_at is None:
            stored_token.revoked_at = datetime.now(UTC)
            if access_token:
                try:
                    at_payload = decode_access_token(access_token)
                    await blocklist_token(at_payload["jti"])
                except Exception:
                    pass  # expired or invalid tokens need not be blocklisted
            user = await self.users.get_by_id(stored_token.user_id)
            await self.audit.record(
                actor=user,
                action="auth.logout",
                resource_type="refresh_token",
                resource_id=stored_token.id,
                request=request,
            )
            await self.session.commit()

    async def _issue_tokens(self, user: User, request: Request | None) -> tuple[TokenPair, RefreshToken]:
        settings = get_settings()
        plain_refresh = new_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(plain_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
            user_agent=request.headers.get("user-agent") if request else None,
            ip_address=request.client.host if request and request.client else None,
        )
        self.session.add(refresh)
        await self.session.flush()
        await self.session.refresh(user)  # ensure all columns are loaded before Pydantic validates
        token_pair = TokenPair(
            access_token=create_access_token(user.id, user.email, user.role.value),
            refresh_token=plain_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserRead.model_validate(user),
        )
        return token_pair, refresh
