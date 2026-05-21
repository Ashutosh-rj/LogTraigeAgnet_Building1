from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token_async
from app.db.models import WebSocketSession
from app.db.session import get_session
from app.repositories.users import UserRepository
from app.services.websocket import websocket_manager

router = APIRouter()

_AUTH_TIMEOUT_SECONDS = 10


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session: AsyncSession = Depends(get_session)) -> None:
    # Accept the connection first so we can send a proper close code on auth failure.
    await websocket.accept()

    # Expect the first message to be {"type": "auth", "token": "<jwt>"} within 10 s.
    try:
        raw = await asyncio.wait_for(websocket.receive_json(), timeout=_AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, Exception):
        await websocket.close(code=4401)
        return

    if not isinstance(raw, dict) or raw.get("type") != "auth" or not raw.get("token"):
        await websocket.close(code=4401)
        return

    try:
        payload = await decode_access_token_async(raw["token"])
    except Exception:
        await websocket.close(code=4401)
        return

    user = await UserRepository(session).get_by_id(str(payload["sub"]))
    if not user or not user.is_active:
        await websocket.close(code=4401)
        return

    ws_session = WebSocketSession(
        user_id=user.id,
        client_host=websocket.client.host if websocket.client else None,
    )
    session.add(ws_session)
    # Register the socket in the in-memory manager *before* committing the DB
    # row.  This removes the window where the session exists in the DB but is
    # not yet tracked in memory (e.g. if the commit raises after connect).
    await websocket_manager.connect(websocket, user.id)
    try:
        await session.commit()
    except Exception:
        websocket_manager.disconnect(websocket, user.id)
        await websocket.close(code=4500)
        return
    try:
        await websocket.send_json({"type": "connected", "session_id": ws_session.id})
        while True:
            message = await websocket.receive_json()
            ws_session.last_seen_at = datetime.now(UTC)
            await session.commit()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        websocket_manager.disconnect(websocket, user.id)
        ws_session.disconnected_at = datetime.now(UTC)
        await session.commit()
