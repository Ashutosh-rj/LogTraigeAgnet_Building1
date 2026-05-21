from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, User
from app.repositories.audit import AuditRepository
from app.services.events import event_publisher


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AuditRepository(session)

    async def record(
        self,
        *,
        actor: User | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        details: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            details=details or {},
        )
        await self.repository.add(audit_log)
        await event_publisher.publish(
            "audit.events",
            {
                "event": "audit.recorded",
                "resource_id": audit_log.id,
                "action": action,
                "actor_id": audit_log.actor_id,
                "resource_type": resource_type,
            },
        )
        return audit_log

