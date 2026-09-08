from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websockets.connection_manager import ws_manager

ws_router = APIRouter(tags=["WebSockets"])

@ws_router.websocket("/ws/class-sessions/{session_id}")
async def websocket_session_endpoint(websocket: WebSocket, session_id: int):
    """
    Real-time WebSocket feed for a class session.
    Streams attendance status transitions, metrics updates, and event logs.
    """
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
    except Exception:
        ws_manager.disconnect(session_id, websocket)
