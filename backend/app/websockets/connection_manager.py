import asyncio
from typing import Dict, List, Any
from fastapi import WebSocket

class ConnectionManager:
    """
    Manages active WebSocket connections grouped by class_session_id.
    Broadcasts real-time attendance changes and vision events to connected dashboards.
    """
    def __init__(self):
        # Map session_id -> list of connected WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, session_id: int, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        print(f"[WebSocket] Client connected to session #{session_id}. Total active: {len(self.active_connections[session_id])}")

    def disconnect(self, session_id: int, websocket: WebSocket):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        print(f"[WebSocket] Client disconnected from session #{session_id}.")

    async def broadcast(self, session_id: int, message: Dict[str, Any]):
        """Asynchronously broadcasts a JSON message to all clients connected to a session."""
        if session_id not in self.active_connections:
            return

        dead_connections = []
        for connection in list(self.active_connections[session_id]):
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] Failed to send message to client: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(session_id, dead)

    def broadcast_sync(self, session_id: int, message: Dict[str, Any]):
        """Synchronous wrapper to broadcast messages from sync route handlers."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.broadcast(session_id, message))
        except RuntimeError:
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(session_id, message), self._loop)

ws_manager = ConnectionManager()
