"""
websocket_manager.py

WebSocket connection manager for the trading dashboard.

Data flow:

    5paisa/Xstream
          ↓
      broker.py
          ↓
    market_data.py
          ↓
 websocket_manager.py
          ↓
       Browser
          ↓
   Future / Call / Put charts
"""

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages all active browser WebSocket connections.
    """

    def __init__(self):

        self.connections: list[WebSocket] = []

    # ---------------------------------------------------------
    # Connect
    # ---------------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
    ) -> None:
        """Accept and register a browser connection."""

        await websocket.accept()

        if websocket not in self.connections:
            self.connections.append(websocket)

        logger.info(
            "WebSocket connected. Active connections: %d",
            len(self.connections),
        )

    # ---------------------------------------------------------
    # Disconnect
    # ---------------------------------------------------------

    def disconnect(
        self,
        websocket: WebSocket,
    ) -> None:
        """Remove a browser connection."""

        if websocket in self.connections:
            self.connections.remove(websocket)

        logger.info(
            "WebSocket disconnected. Active connections: %d",
            len(self.connections),
        )

    # ---------------------------------------------------------
    # Send to one browser
    # ---------------------------------------------------------

    async def send_json(
        self,
        websocket: WebSocket,
        data: dict[str, Any],
    ) -> bool:
        """Send JSON data to one connected browser."""

        try:

            await websocket.send_json(data)
            return True

        except Exception:

            logger.exception(
                "Failed to send WebSocket message."
            )

            self.disconnect(websocket)

            return False

    # ---------------------------------------------------------
    # Broadcast
    # ---------------------------------------------------------

    async def broadcast(
        self,
        data: dict[str, Any],
    ) -> None:
        """
        Send data to every connected browser.

        Used for live market ticks.
        """

        disconnected = []

        for websocket in list(self.connections):

            try:

                await websocket.send_json(data)

            except Exception:

                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)

    # ---------------------------------------------------------
    # Broadcast tick
    # ---------------------------------------------------------

    async def broadcast_tick(
        self,
        tick: dict[str, Any],
    ) -> None:
        """
        Send a normalized market tick to the browser.

        Example message:

        {
            "type": "tick",
            "symbol": "NIFTY",
            "ltp": 25000.50
        }
        """

        await self.broadcast({
            "type": "tick",
            "data": tick,
        })

    # ---------------------------------------------------------
    # Broadcast candle
    # ---------------------------------------------------------

    async def broadcast_candle(
        self,
        chart: str,
        candle: dict[str, Any],
    ) -> None:
        """
        Send a completed/updated candle to the browser.

        chart:
            future
            call
            put
        """

        await self.broadcast({
            "type": "candle",
            "chart": chart,
            "data": candle,
        })

    # ---------------------------------------------------------
    # Broadcast chart update
    # ---------------------------------------------------------

    async def broadcast_chart_update(
        self,
        chart: str,
        data: dict[str, Any],
    ) -> None:
        """
        Send a chart-specific update.
        """

        await self.broadcast({
            "type": "chart_update",
            "chart": chart,
            "data": data,
        })

    # ---------------------------------------------------------
    # Broadcast selection change
    # ---------------------------------------------------------

    async def broadcast_selection(
        self,
        symbol: str,
        expiry: str | None = None,
        call: dict[str, Any] | None = None,
        put: dict[str, Any] | None = None,
    ) -> None:
        """
        Notify the browser that the Future/Call/Put selection
        has changed.
        """

        await self.broadcast({
            "type": "selection",
            "symbol": symbol,
            "expiry": expiry,
            "call": call,
            "put": put,
        })

    # ---------------------------------------------------------
    # Broadcast status
    # ---------------------------------------------------------

    async def broadcast_status(
        self,
        status: str,
        message: str = "",
    ) -> None:
        """
        Send application status to all browsers.

        Examples:
            connected
            disconnected
            reconnecting
            error
        """

        await self.broadcast({
            "type": "status",
            "status": status,
            "message": message,
        })

    # ---------------------------------------------------------
    # Number of connections
    # ---------------------------------------------------------

    def connection_count(self) -> int:
        """Return number of active browser connections."""

        return len(self.connections)

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    def status(self) -> dict[str, Any]:

        return {
            "active_connections": len(
                self.connections
            )
        }


# =============================================================
# Shared WebSocket manager
# =============================================================

manager = ConnectionManager()
