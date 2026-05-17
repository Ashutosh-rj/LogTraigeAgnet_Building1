from __future__ import annotations

import asyncio
import os

from app.core.security import hash_password
from app.db.models import Role
from app.db.session import AsyncSessionLocal
from app.repositories.users import UserRepository


async def seed_admin() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("SEED_ADMIN_PASSWORD")
    name = os.getenv("SEED_ADMIN_NAME", "Platform Admin")
    if not email or not password:
        raise RuntimeError("SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD are required")
    async with AsyncSessionLocal() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(email)
        if existing:
            existing.role = Role.admin
            existing.is_active = True
        else:
            await users.create(email=email, name=name, password_hash=hash_password(password), role=Role.admin)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_admin())

