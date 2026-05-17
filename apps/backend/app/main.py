from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import MetricsMiddleware, metrics_response
from app.core.middleware import RateLimitMiddleware, RequestIdMiddleware, SecurityHeadersMiddleware
from app.core.telemetry import configure_telemetry
from app.db.models import validate_embedding_dimensions
from app.db.session import get_engine
from app.services.events import event_publisher

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    await validate_embedding_dimensions(get_engine())
    await event_publisher.start()
    if settings.embedding_provider == "hash":
        logger.warning(
            "hash_embedding_active",
            detail="search results are not semantically meaningful — set EMBEDDING_PROVIDER to a real provider for production",
        )
    logger.info("application_started", environment=settings.environment)
    try:
        yield
    finally:
        await event_publisher.stop()
        logger.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestIdMiddleware)

configure_telemetry(app)
app.include_router(api_router)
app.add_route("/metrics", metrics_response, methods=["GET"])

