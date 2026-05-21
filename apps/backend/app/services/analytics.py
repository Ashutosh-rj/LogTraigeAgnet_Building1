from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Incident, IncidentStatus, Severity
from app.schemas.analytics import IncidentAnalytics


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def incident_summary(self) -> IncidentAnalytics:
        total = int((await self.session.execute(select(func.count(Incident.id)))).scalar_one())
        status_rows = (
            await self.session.execute(select(Incident.status, func.count()).group_by(Incident.status))
        ).all()
        severity_rows = (
            await self.session.execute(select(Incident.severity, func.count()).group_by(Incident.severity))
        ).all()
        open_critical = int(
            (
                await self.session.execute(
                    select(func.count(Incident.id)).where(
                        Incident.status.in_([IncidentStatus.open, IncidentStatus.investigating]),
                        Incident.severity == Severity.critical,
                    )
                )
            ).scalar_one()
        )
        resolved_rows = (
            await self.session.execute(
                select(
                    func.avg(
                        func.extract("epoch", Incident.updated_at - Incident.created_at) / 3600.0
                    )
                ).where(Incident.status.in_([IncidentStatus.resolved, IncidentStatus.closed]))
            )
        ).scalar_one()
        return IncidentAnalytics(
            total=total,
            by_status={status.value: int(count) for status, count in status_rows},
            by_severity={severity.value: int(count) for severity, count in severity_rows},
            open_critical=open_critical,
            mean_time_to_resolve_hours=round(float(resolved_rows), 2) if resolved_rows else None,
        )

