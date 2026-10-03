"""
services.data_fabric.ws_bridge
==============================
WebSocket HMR (Hot Module Replacement) and Live Telemetry Bridge.
Connects Data Fabric FastAPI backend on port 8765 to Vite/UI preview clients on port 4400.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Set

logger = logging.getLogger("services.data_fabric.ws_bridge")


class WebSocketBridge:
    """Manages active browser WebSocket connections and broadcasts data/schema mutations."""

    def __init__(self):
        self._active_connections: Set[Any] = set()

    async def connect(self, websocket: Any) -> None:
        """Registers a new UI preview WebSocket client."""
        await websocket.accept()
        self._active_connections.add(websocket)
        logger.info("[WS Bridge] Client connected. Total active: %d", len(self._active_connections))

    def disconnect(self, websocket: Any) -> None:
        """Unregisters disconnected client."""
        self._active_connections.discard(websocket)
        logger.info("[WS Bridge] Client disconnected. Remaining: %d", len(self._active_connections))

    async def broadcast(self, message_type: str, payload: Dict[str, Any]) -> None:
        """Pushes structured HMR or telemetry update to all connected clients."""
        if not self._active_connections:
            return

        envelope = json.dumps({"type": message_type, "payload": payload})
        dead = []
        for ws in self._active_connections:
            try:
                await ws.send_text(envelope)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._active_connections.discard(ws)


ws_bridge = WebSocketBridge()
