# app/services/websocket_manager.py
"""Minimal in-process WebSocket fan-out (PR #8).

The frontend already speaks the ``/ws/program/{program_id}`` channel
contract defined in ``genovate-ui/lib/types/websocket.ts``.  This module
provides the *backend* counterpart: a simple connection registry that
buckets sockets by program id and broadcasts ``ProgramEventMessage``
payloads.

The implementation is deliberately dependency-free (no Redis, no broker)
because PR #8 only needs same-process, single-replica delivery.  All
``broadcast_*`` helpers gracefully no-op when no subscribers are
connected, so backend services can call them unconditionally.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised at runtime only
    from fastapi import WebSocket  # type: ignore
except Exception:  # pragma: no cover
    WebSocket = Any  # type: ignore


class ProgramEventBroadcaster:
    """Track WebSocket subscribers per program and fan out events."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[Any]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, program_id: str, websocket: Any) -> None:
        async with self._lock:
            self._subscribers.setdefault(program_id, set()).add(websocket)

    async def unsubscribe(self, program_id: str, websocket: Any) -> None:
        async with self._lock:
            subs = self._subscribers.get(program_id)
            if subs is None:
                return
            subs.discard(websocket)
            if not subs:
                self._subscribers.pop(program_id, None)

    def subscriber_count(self, program_id: str) -> int:
        return len(self._subscribers.get(program_id, ()))

    async def broadcast(self, program_id: str, message: Dict[str, Any]) -> int:
        """Send a JSON message to every subscriber of ``program_id``.

        Returns the number of sockets the message was successfully sent
        to.  Dead sockets are pruned silently — broadcast failures must
        never propagate into the calling service.
        """
        async with self._lock:
            subs = list(self._subscribers.get(program_id, ()))
        if not subs:
            return 0

        delivered = 0
        for ws in subs:
            try:
                await ws.send_json(message)
                delivered += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "Pruning dead websocket for program %s: %s", program_id, exc
                )
                await self.unsubscribe(program_id, ws)
        return delivered

    async def broadcast_candidate_status_changed(
        self,
        program_id: str,
        candidate_id: str,
        old_status: Optional[str],
        new_status: str,
        trigger_type: str,
        rationale: Optional[str] = None,
    ) -> int:
        """Emit a ``candidate_status_changed`` ``ProgramEventMessage``."""
        return await self.broadcast(
            program_id,
            {
                "event_type": "candidate_status_changed",
                "entity_id": candidate_id,
                "entity_type": "candidate",
                "old_status": old_status,
                "new_status": new_status,
                "payload": {
                    "trigger_type": trigger_type,
                    "rationale": rationale,
                },
            },
        )


program_event_broadcaster = ProgramEventBroadcaster()
