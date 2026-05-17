from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ResponderUser
from app.db.session import get_session
from app.schemas.logs import LogCreate, LogRead
from app.services.incidents import IncidentService

router = APIRouter()


class LogIngestRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    log: LogCreate


@router.post("/ingest", response_model=LogRead, status_code=201)
async def ingest_log(
    payload: LogIngestRequest,
    request: Request,
    user: ResponderUser,
    session: AsyncSession = Depends(get_session),
) -> LogRead:
    log_entry = await IncidentService(session).ingest_log(payload.incident_id, payload.log, user, request)
    return LogRead.model_validate(log_entry)

