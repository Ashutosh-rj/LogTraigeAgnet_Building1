from __future__ import annotations

from sqlalchemy import select

from app.db.models import LogEntry
from app.repositories.base import Repository

# Keep these two constants in sync — both the API endpoint and triage generation
# should fetch the same default number of logs so behaviour is predictable.
LOG_PAGE_DEFAULT = 100
LOG_TRIAGE_LIMIT = 100


class LogRepository(Repository):
    async def add(self, log_entry: LogEntry) -> LogEntry:
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def list_for_incident(self, incident_id: str, limit: int = LOG_PAGE_DEFAULT) -> list[LogEntry]:
        result = await self.session.execute(
            select(LogEntry)
            .where(LogEntry.incident_id == incident_id)
            .order_by(LogEntry.observed_at.desc())
            .limit(limit)
        )
        return list(result.scalars())
