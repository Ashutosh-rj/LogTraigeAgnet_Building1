from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Engine and session factory are created lazily on first access so that:
#
#  1. Test suites can monkeypatch DATABASE_URL (via get_settings) before the
#     engine is instantiated — no import-time side-effects.
#  2. The engine can be replaced without restarting the process (clear the
#     lru_cache and call get_engine() again).
#
# Do NOT import `engine` or `AsyncSessionLocal` directly from this module;
# always call get_engine() / get_session_factory() so the lazy path is used.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the shared async engine (created once, cached for the process lifetime)."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory."""
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    async with get_session_factory()() as session:
        yield session


def reset_engine() -> None:
    """Clear the engine and session-factory caches.

    Call this in test teardown (or whenever DATABASE_URL changes) so the next
    call to get_engine() / get_session_factory() builds fresh objects against
    the current settings.  Using this helper is safer than calling
    get_engine.cache_clear() and get_session_factory.cache_clear()
    separately, as it guarantees both are cleared together atomically.

    Example (pytest fixture)::

        @pytest.fixture(autouse=True)
        def _reset_db_engine(monkeypatch):
            monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
            yield
            reset_engine()
    """
    get_engine.cache_clear()
    get_session_factory.cache_clear()

