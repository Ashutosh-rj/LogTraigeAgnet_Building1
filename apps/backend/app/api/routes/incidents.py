from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ResponderUser, ViewerUser
from app.core.config import get_settings
from app.db.session import get_session
from app.repositories.logs import LogRepository, LOG_PAGE_DEFAULT
from app.schemas.common import Page
from app.schemas.incidents import IncidentCreate, IncidentFilters, IncidentRead, IncidentUpdate
from app.schemas.logs import LogCreate, LogRead
from app.schemas.triage import TriageReportRead
from app.services.incidents import IncidentService

router = APIRouter()


@router.get("", response_model=Page[IncidentRead])
async def list_incidents(
    user: ViewerUser,
    filters: IncidentFilters = Depends(),
    session: AsyncSession = Depends(get_session),
) -> Page[IncidentRead]:
    _ = user
    return await IncidentService(session).list(filters)


@router.post("", response_model=IncidentRead, status_code=201)
async def create_incident(
    payload: IncidentCreate,
    request: Request,
    user: ResponderUser,
    session: AsyncSession = Depends(get_session),
) -> IncidentRead:
    incident = await IncidentService(session).create(payload, user, request)
    return IncidentRead.model_validate(incident)


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(
    incident_id: str,
    user: ViewerUser,
    session: AsyncSession = Depends(get_session),
) -> IncidentRead:
    _ = user
    incident = await IncidentService(session).get_or_404(incident_id)
    return IncidentRead.model_validate(incident)


@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    request: Request,
    user: ResponderUser,
    session: AsyncSession = Depends(get_session),
) -> IncidentRead:
    incident = await IncidentService(session).update(incident_id, payload, user, request)
    return IncidentRead.model_validate(incident)



@router.delete("/{incident_id}", status_code=204)
async def delete_incident(
    incident_id: str,
    request: Request,
    user: ResponderUser,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await IncidentService(session).delete(incident_id, user, request)
    return Response(status_code=204)


@router.post("/{incident_id}/logs", response_model=LogRead, status_code=201)
async def add_log(
    incident_id: str,
    payload: LogCreate,
    request: Request,
    user: ResponderUser,
    session: AsyncSession = Depends(get_session),
) -> LogRead:
    log_entry = await IncidentService(session).ingest_log(incident_id, payload, user, request)
    return LogRead.model_validate(log_entry)


@router.get("/{incident_id}/logs", response_model=list[LogRead])
async def list_logs(
    incident_id: str,
    user: ViewerUser,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=LOG_PAGE_DEFAULT, ge=1, le=500),
) -> list[LogRead]:
    _ = user
    await IncidentService(session).get_or_404(incident_id)
    logs = await LogRepository(session).list_for_incident(incident_id, limit=limit)
    return [LogRead.model_validate(log) for log in logs]


@router.post("/{incident_id}/triage", response_model=TriageReportRead)
async def generate_triage(
    incident_id: str,
    request: Request,
    user: ResponderUser,
    session: AsyncSession = Depends(get_session),
) -> TriageReportRead:
    report = await IncidentService(session).generate_triage(incident_id, user, request)
    return TriageReportRead.model_validate(report)
