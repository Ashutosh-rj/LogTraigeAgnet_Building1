from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Incident, LogEntry, User
from app.repositories.incidents import IncidentRepository
from app.repositories.logs import LogRepository
from app.schemas.common import Page
from app.schemas.incidents import IncidentCreate, IncidentFilters, IncidentRead, IncidentUpdate
from app.schemas.logs import LogCreate
from app.services.audit import AuditService
from app.services.embeddings import EmbeddingService
from app.services.events import event_publisher
from app.services.notifications import NotificationService
from app.services.triage import TriageService
from app.services.websocket import websocket_manager

import structlog as _structlog

_log = _structlog.get_logger()


class IncidentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = IncidentRepository(session)
        self.logs = LogRepository(session)
        self.audit = AuditService(session)
        self.embeddings = EmbeddingService(session)
        self.triage = TriageService(session)
        self.notifications = NotificationService(session)

    async def create(
        self, payload: IncidentCreate, actor: User, request: Request | None = None
    ) -> Incident:
        incident = Incident(**payload.model_dump(), created_by_id=actor.id)
        await self.repository.create(incident)
        await self.embeddings.upsert("incident", incident.id, self._incident_embedding_content(incident))
        await self.audit.record(
            actor=actor,
            action="incident.create",
            resource_type="incident",
            resource_id=incident.id,
            details={"severity": incident.severity.value},
            request=request,
        )
        if incident.assignee_id:
            await self.notifications.create(
                user_id=incident.assignee_id,
                title="Incident assigned",
                message=f"{incident.title} was assigned to you.",
                incident_id=incident.id,
            )
        await self.session.commit()
        await self.session.refresh(incident)
        await self._broadcast("incident.created", incident)
        return incident

    async def list(self, filters: IncidentFilters) -> Page[IncidentRead]:
        items, total = await self.repository.list(**filters.model_dump())
        return Page[IncidentRead](
            items=[IncidentRead.model_validate(item) for item in items],
            total=total,
            limit=filters.limit,
            offset=filters.offset,
        )

    async def get_or_404(self, incident_id: str) -> Incident:
        incident = await self.repository.get(incident_id)
        if not incident:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
        return incident

    async def update(
        self,
        incident_id: str,
        payload: IncidentUpdate,
        actor: User,
        request: Request | None = None,
    ) -> Incident:
        incident = await self.get_or_404(incident_id)
        changes = payload.model_dump(exclude_unset=True)

        # Capture assignee before mutation to detect reassignment (FIX F2).
        old_assignee_id = incident.assignee_id

        for key, value in changes.items():
            setattr(incident, key, value)

        # Send notification when assignee changes to a new (non-None) user.
        # Use new_assignee_id from the payload (captured before or after setattr
        # is equivalent here) rather than incident.assignee_id, which has already
        # been mutated by the setattr loop.  This avoids sending a notification
        # to user_id=None when assignee_id is being cleared.
        new_assignee_id = changes.get("assignee_id")
        if (
            "assignee_id" in changes
            and new_assignee_id is not None
            and new_assignee_id != old_assignee_id
        ):
            await self.notifications.create(
                user_id=new_assignee_id,
                title="Incident assigned",
                message=f"{incident.title} was assigned to you.",
                incident_id=incident.id,
            )

        await self.embeddings.upsert("incident", incident.id, self._incident_embedding_content(incident))
        await self.audit.record(
            actor=actor,
            action="incident.update",
            resource_type="incident",
            resource_id=incident.id,
            details={"fields": sorted(changes.keys())},
            request=request,
        )
        await self.session.commit()
        await self.session.refresh(incident)
        await self._broadcast("incident.updated", incident)
        return incident

    async def delete(
        self,
        incident_id: str,
        actor: User,
        request: Request | None = None,
    ) -> None:
        incident = await self.get_or_404(incident_id)
        await self.repository.soft_delete(incident_id)
        await self.audit.record(
            actor=actor,
            action="incident.delete",
            resource_type="incident",
            resource_id=incident.id,
            details={"title": incident.title},
            request=request,
        )
        await self.session.commit()
        await self._broadcast("incident.deleted", incident)

    async def ingest_log(
        self,
        incident_id: str,
        payload: LogCreate,
        actor: User,
        request: Request | None = None,
    ) -> LogEntry:
        incident = await self.get_or_404(incident_id)
        log_entry = LogEntry(
            incident_id=incident.id,
            level=payload.level,
            message=payload.message,
            source=payload.source,
            observed_at=payload.observed_at or datetime.now(UTC),
            attributes=payload.attributes,
        )
        await self.logs.add(log_entry)
        await self.embeddings.upsert(
            "log",
            log_entry.id,
            f"{payload.level.value} {payload.source} {payload.message} {payload.attributes}",
        )
        await self.audit.record(
            actor=actor,
            action="log.ingest",
            resource_type="incident",
            resource_id=incident.id,
            details={"log_id": log_entry.id, "level": payload.level.value},
            request=request,
        )
        await self.session.commit()
        await self.session.refresh(log_entry)
        await event_publisher.publish(
            "log.events",
            {
                "event": "log.ingested",
                "resource_id": log_entry.id,
                "incident_id": incident.id,
                "level": payload.level.value,
            },
        )
        await websocket_manager.broadcast(
            {
                "type": "log.ingested",
                "incident_id": incident.id,
                "log": {
                    "id": log_entry.id,
                    "level": log_entry.level.value,
                    "message": log_entry.message,
                    "source": log_entry.source,
                },
            }
        )
        return log_entry

    async def generate_triage(
        self, incident_id: str, actor: User, request: Request | None = None
    ):
        incident = await self.get_or_404(incident_id)
        
        from app.core.config import get_settings
        settings = get_settings()
        if settings.triage_mode == "claude_pipeline":
            from app.services.ai_triage import AITriageService
            triage_engine = AITriageService(self.session)
        else:
            triage_engine = self.triage
            
        report, was_regenerated = await triage_engine.generate(incident)

        if was_regenerated:
            _log.info("triage.regenerated", incident_id=incident_id, report_id=report.id)
        else:
            _log.info("triage.generated", incident_id=incident_id, report_id=report.id)

        await self.embeddings.upsert(
            "triage",
            report.id,
            f"{report.summary}\n{report.root_cause}\n{' '.join(report.recommendations)}",
        )
        await self.audit.record(
            actor=actor,
            action="triage.generate",
            resource_type="incident",
            resource_id=incident.id,
            details={
                "triage_report_id": report.id,
                "confidence": report.confidence,
                "regenerated": was_regenerated,
            },
            request=request,
        )
        await self.session.commit()
        await self.session.refresh(report)
        await self._broadcast("triage.generated", incident)
        return report

    async def _broadcast(self, event_name: str, incident: Incident) -> None:
        # Refresh incident so all columns are loaded before Pydantic validates outside a greenlet.
        try:
            await self.session.refresh(incident)
        except Exception:
            pass
        payload = {
            "event": event_name,
            "resource_id": incident.id,
            "incident": IncidentRead.model_validate(incident).model_dump(mode="json"),
        }
        await event_publisher.publish("incident.events", payload)
        await websocket_manager.broadcast({"type": event_name, "incident": payload["incident"]})

    def _incident_embedding_content(self, incident: Incident) -> str:
        return " ".join(
            [
                incident.title,
                incident.description,
                incident.severity.value,
                incident.status.value,
                incident.source,
                " ".join(incident.tags or []),
            ]
        )
