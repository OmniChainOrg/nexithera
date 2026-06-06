# app/api/websocket.py
"""WebSocket endpoints (PR #8).

The frontend already speaks the ``/ws/program/{program_id}`` channel
contract (see ``genovate-ui/lib/types/websocket.ts``).  This router
plugs that channel into the in-process ``program_event_broadcaster``
so backend services can fan out ``ProgramEventMessage`` payloads
(notably ``candidate_status_changed`` events emitted by the pipeline
auto-advance state machine).
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.websocket_manager import program_event_broadcaster

router = APIRouter()


@router.websocket("/ws/program/{program_id}")
async def program_event_socket(websocket: WebSocket, program_id: str) -> None:
    """Subscribe to ``ProgramEventMessage`` events for a program."""
    await websocket.accept()
    await program_event_broadcaster.subscribe(program_id, websocket)
    try:
        # Keep the connection open. Inbound messages from the client are
        # currently ignored; the channel is server-push only.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await program_event_broadcaster.unsubscribe(program_id, websocket)
