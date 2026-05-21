from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        # NOTE: websocket.accept() is intentionally omitted here.
        # The route handler (ws.py) calls accept() before authentication so it
        # can send a proper close code on auth failure.  Calling accept() a
        # second time on an already-accepted WebSocket raises a Starlette
        # runtime error and terminates the connection.
        self._connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        connections = self._connections.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self._connections.get(user_id, set())):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket, user_id)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        for user_id in list(self._connections):
            await self.send_to_user(user_id, payload)

    async def broadcast_to_role(
        self,
        payload: dict[str, Any],
        allowed_roles: set[str],
        role_map: dict[str, str],  # user_id -> role
    ) -> None:
        # TODO: filter by team/tenant when multi-tenancy is added.
        for user_id, role in role_map.items():
            if role in allowed_roles:
                await self.send_to_user(user_id, payload)


websocket_manager = WebSocketManager()
