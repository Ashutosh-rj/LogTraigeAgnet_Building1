from __future__ import annotations

from sqlalchemy import select

from app.db.models import Notification
from app.repositories.base import Repository


class NotificationRepository(Repository):
    async def add(self, notification: Notification) -> Notification:
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def list_for_user(self, user_id: str, limit: int, unread_only: bool) -> list[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        result = await self.session.execute(query.order_by(Notification.created_at.desc()).limit(limit))
        return list(result.scalars())

