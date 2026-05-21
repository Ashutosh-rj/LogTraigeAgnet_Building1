from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_session
from app.repositories.notifications import NotificationRepository
from app.schemas.notifications import NotificationRead
from app.services.notifications import NotificationService

router = APIRouter()


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    user: CurrentUser,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationRead]:
    notifications = await NotificationRepository(session).list_for_user(user.id, limit, unread_only)
    return [NotificationRead.model_validate(notification) for notification in notifications]


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> NotificationRead:
    notification = await NotificationService(session).mark_read(notification_id, user.id)
    return NotificationRead.model_validate(notification)

