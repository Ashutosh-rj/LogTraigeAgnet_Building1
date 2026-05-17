from __future__ import annotations

from sqlalchemy import select

from app.db.models import Role, User
from app.repositories.base import Repository


class UserRepository(Repository):
    async def get_by_id(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def create(self, email: str, name: str, password_hash: str, role: Role = Role.viewer) -> User:
        user = User(email=email.lower(), name=name, password_hash=password_hash, role=role)
        self.session.add(user)
        await self.session.flush()
        return user

    async def list(self, limit: int, offset: int) -> list[User]:
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars())

