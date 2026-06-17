from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.ws_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep the connection alive; clients may send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(ws)
