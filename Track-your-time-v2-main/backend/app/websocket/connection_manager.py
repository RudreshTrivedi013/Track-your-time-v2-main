from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    """Tracks active WS connections per user_id so task mutations can be
    broadcast to every other open tab/device for that user in real time."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = {}

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        conns = self._connections.get(user_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                self._connections.pop(user_id, None)

    async def broadcast_to_user(self, user_id: UUID, message: dict, exclude: WebSocket | None = None) -> None:
        conns = self._connections.get(user_id, set())
        dead = []
        for ws in conns:
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)


manager = ConnectionManager()
