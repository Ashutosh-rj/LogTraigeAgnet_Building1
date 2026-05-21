from __future__ import annotations

from sqlalchemy import select

from app.db.models import AuditLog
from app.repositories.base import Repository


class AuditRepository(Repository):
    async def add(self, audit_log: AuditLog) -> AuditLog:
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def list_recent(self, limit: int) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars())

