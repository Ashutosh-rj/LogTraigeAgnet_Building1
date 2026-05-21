from __future__ import annotations

import asyncio
import os

from app.core.security import hash_password
from app.db.models import Role
<<<<<<< HEAD
from app.db.session import get_session_factory
=======
from app.db.session import AsyncSessionLocal
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
from app.repositories.users import UserRepository


async def seed_admin() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("SEED_ADMIN_PASSWORD")
    name = os.getenv("SEED_ADMIN_NAME", "Platform Admin")
    if not email or not password:
        raise RuntimeError("SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD are required")
<<<<<<< HEAD
    async with get_session_factory()() as session:
=======
    async with AsyncSessionLocal() as session:
>>>>>>> ec9ba626b100ff3057dcc621c518b6d3104f2818
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

