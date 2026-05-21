from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.repositories.notifications import NotificationRepository
from app.services.events import event_publisher
from app.services.websocket import websocket_manager


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = NotificationRepository(session)

    async def create(
        self,
        *,
        user_id: str,
        title: str,
        message: str,
        kind: str = "incident",
        incident_id: str | None = None,
        metadata: dict | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            kind=kind,
            incident_id=incident_id,
            notification_metadata=metadata or {},
        )
        await self.repository.add(notification)
        # Flush so the DB assigns the primary key before we broadcast the ID.
        # The caller is responsible for the final commit.
        await self.session.flush()
        await event_publisher.publish(
            "notification.events",
            {
                "event": "notification.created",
                "resource_id": notification.id,
                "user_id": user_id,
                "incident_id": incident_id,
            },
        )
        await websocket_manager.send_to_user(
            user_id,
            {
                "type": "notification.created",
                "notification": {
                    "id": notification.id,
                    "title": notification.title,
                    "message": notification.message,
                    "kind": notification.kind,
                    "incident_id": notification.incident_id,
                },
            },
        )
        return notification

    async def mark_read(self, notification_id: str, user_id: str) -> Notification:
        notification = await self.session.get(Notification, notification_id)
        if not notification or notification.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        notification.read_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

