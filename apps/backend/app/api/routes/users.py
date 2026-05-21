from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.db.models import User
from app.db.session import get_session
from app.repositories.users import UserRepository
from app.schemas.common import Page
from app.schemas.users import UserRead, UserUpdate

router = APIRouter()


@router.get("", response_model=Page[UserRead])
async def list_users(
    _: AdminUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> Page[UserRead]:
    # Run both queries inside the same transaction so the count and the page
    # share a consistent snapshot.  A concurrent registration between two
    # separate queries could yield a total that does not match the page.
    async with session.begin_nested():
        total = int((await session.execute(select(func.count(User.id)))).scalar_one())
        users = await UserRepository(session).list(limit=limit, offset=offset)
    return Page[UserRead](
        items=[UserRead.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    _: AdminUser,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    user = await UserRepository(session).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)

