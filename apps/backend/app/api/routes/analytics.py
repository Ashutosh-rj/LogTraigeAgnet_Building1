from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ViewerUser
from app.db.session import get_session
from app.schemas.analytics import IncidentAnalytics
from app.services.analytics import AnalyticsService

router = APIRouter()


@router.get("/incidents", response_model=IncidentAnalytics)
async def incident_analytics(
    user: ViewerUser,
    session: AsyncSession = Depends(get_session),
) -> IncidentAnalytics:
    _ = user
    return await AnalyticsService(session).incident_summary()

