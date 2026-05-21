from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, analytics, auth, health, incidents, logs, notifications, search, users, ws

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/api/v1/users", tags=["users"])
api_router.include_router(incidents.router, prefix="/api/v1/incidents", tags=["incidents"])
api_router.include_router(logs.router, prefix="/api/v1/logs", tags=["logs"])
api_router.include_router(search.router, prefix="/api/v1/search", tags=["search"])
api_router.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
api_router.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
api_router.include_router(ws.router, prefix="/api/v1", tags=["websocket"])

