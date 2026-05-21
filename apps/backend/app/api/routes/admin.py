from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.db.session import get_session
from app.repositories.audit import AuditRepository

router = APIRouter()


@router.get("/audit-logs")
async def audit_logs(
    _: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await AuditRepository(session).list_recent(limit)
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]

