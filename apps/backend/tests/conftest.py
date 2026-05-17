from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# SQLite dialect patches so pgvector's Vector and PostgreSQL's JSONB compile
# correctly when running tests against an in-memory SQLite database.
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402

SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]
SQLiteTypeCompiler.visit_VECTOR = lambda self, type_, **kw: "TEXT"  # type: ignore[attr-defined]

from app.db.models import Base  # noqa: E402 — must come after dialect patch
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services.events import event_publisher  # noqa: E402

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def test_env(monkeypatch: pytest.MonkeyPatch):  # type: ignore[return]
    """Isolate env vars and settings cache for every test."""
    get_settings.cache_clear()
    monkeypatch.setenv("KAFKA_ENABLED", "false")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-minimum-32-chars!!")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    yield
    get_settings.cache_clear()
    # Clear the lazy-engine caches so the next test gets a fresh engine.
    from app.db.session import get_engine, get_session_factory
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    # Clear the in-process JWT blocklist between tests.
    from app.core import security as _sec
    _sec._local_blocklist.clear()
    _sec._redis_client = None


@pytest_asyncio.fixture()
async def db_engine():
    """Fresh async SQLite engine per test; creates all tables, drops after."""
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine):
    """Scoped async session for direct DB assertions in tests."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture()
async def client(db_engine, monkeypatch):
    """AsyncClient wired to the FastAPI app with a fresh in-memory DB."""
    # Silence Kafka publish calls so tests never need a broker.
    monkeypatch.setattr(event_publisher, "publish", lambda *a, **kw: _noop())

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    # Reset in-process rate limiter buckets so middleware tests don't bleed into others.
    from app.core.rate_limit import rate_limiter
    rate_limiter._local.clear()  # noqa: SLF001

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    rate_limiter._local.clear()  # noqa: SLF001


async def _noop(*args, **kwargs):  # noqa: ANN001
    return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def register(client: AsyncClient, email: str = "user@example.com", name: str = "Test User") -> dict:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": "Passw0rd!secure"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def login(client: AsyncClient, email: str = "user@example.com") -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Passw0rd!secure"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Refresh token is delivered as an httpOnly cookie, not in the JSON body.
    # Expose it under "refresh_token" so tests can use it without special-casing.
    rt_cookie = resp.cookies.get("logiq_refresh")
    if rt_cookie:
        data["refresh_token"] = rt_cookie
    return data


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
