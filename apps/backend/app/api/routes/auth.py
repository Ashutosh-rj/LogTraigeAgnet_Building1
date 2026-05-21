from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_session
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.common import Message
from app.schemas.users import UserRead
from app.services.auth import AuthService

router = APIRouter()


def _set_refresh_cookie(response: Response, request: Request, token_pair: TokenPair) -> TokenPair:
    refresh_token = token_pair.refresh_token
    if refresh_token:
        from app.core.config import get_settings

        settings = get_settings()
        response.set_cookie(
            key=settings.refresh_cookie_name,
            value=refresh_token,
            httponly=True,
            secure=settings.is_production or request.url.scheme == "https",
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/api/v1/auth",
        )
    return token_pair.model_copy(update={"refresh_token": None})


def _read_refresh_token(
    request: Request, payload: RefreshRequest | LogoutRequest | None
) -> str | None:
    from app.core.config import get_settings

    return request.cookies.get(get_settings().refresh_cookie_name) or (
        payload.refresh_token if payload else None
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    tokens = await AuthService(session).register(payload, request)
    return _set_refresh_cookie(response, request, tokens)


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    tokens = await AuthService(session).login(payload, request)
    return _set_refresh_cookie(response, request, tokens)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    refresh_token = _read_refresh_token(request, payload)
    if not refresh_token:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
    tokens = await AuthService(session).refresh(refresh_token, request)
    return _set_refresh_cookie(response, request, tokens)


@router.post("/logout", response_model=Message)
async def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
) -> Message:
    refresh_token = _read_refresh_token(request, payload)
    raw_access = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or None
    if refresh_token:
        await AuthService(session).logout(refresh_token, request, access_token=raw_access)
    from app.core.config import get_settings

    response.delete_cookie(get_settings().refresh_cookie_name, path="/api/v1/auth")
    return Message(message="Logged out")


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
