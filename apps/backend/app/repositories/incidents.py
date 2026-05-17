from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select

from app.db.models import Incident, IncidentStatus, Severity
from app.repositories.base import Repository


class IncidentRepository(Repository):
    async def get(self, incident_id: str) -> Incident | None:
        result = await self.session.execute(
            select(Incident).where(
                Incident.id == incident_id,
                Incident.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, incident: Incident) -> Incident:
        self.session.add(incident)
        await self.session.flush()
        return incident

    def _filtered_query(
        self,
        *,
        status: IncidentStatus | None,
        severity: Severity | None,
        q: str | None,
    ) -> Select[tuple[Incident]]:
        query = select(Incident).where(Incident.deleted_at.is_(None))
        if status:
            query = query.where(Incident.status == status)
        if severity:
            query = query.where(Incident.severity == severity)
        if q:
            # Escape LIKE metacharacters so a search term like "50%" or "_admin"
            # is matched literally rather than acting as a wildcard pattern.
            q_escaped = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = f"%{q_escaped}%"
            query = query.where(
                or_(
                    func.lower(Incident.title).like(like, escape="\\"),
                    func.lower(Incident.description).like(like, escape="\\"),
                )
            )
        return query

    async def list(
        self,
        *,
        status: IncidentStatus | None,
        severity: Severity | None,
        q: str | None,
        limit: int,
        offset: int,
        sort: str,
    ) -> tuple[list[Incident], int]:
        query = self._filtered_query(status=status, severity=severity, q=q)
        total_result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        total = int(total_result.scalar_one())
        sort_fields = {
            "created_at": Incident.created_at,
            "updated_at": Incident.updated_at,
            "severity": Incident.severity,
            "status": Incident.status,
            "title": Incident.title,
        }
        desc = sort.startswith("-")
        key = sort[1:] if desc else sort
        sort_column = sort_fields.get(key, Incident.created_at)
        ordered = sort_column.desc() if desc else sort_column.asc()
        result = await self.session.execute(query.order_by(ordered).limit(limit).offset(offset))
        return list(result.scalars()), total

    async def soft_delete(self, incident_id: str) -> None:
        result = await self.session.execute(
            select(Incident).where(
                Incident.id == incident_id,
                Incident.deleted_at.is_(None),
            )
        )
        incident = result.scalar_one_or_none()
        if incident:
            incident.deleted_at = datetime.now(UTC)
            await self.session.flush()
