"""
websocket_manager.py

Trading dashboard WebSocket manager.

Flow:

    5paisa Broker
          ↓
      get_quote()
          ↓
    WebSocket Manager
          ↓
       Browser
          ↓
   Future / Call / Put charts
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket

from Backend.broker import broker


logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages browser WebSocket connections and live market
    quote subscriptions.
    """

    def __init__(self):

        # Active browser connections
        self.connections: list[WebSocket] = []

        # Current browser/chart selection
        self.selection: Dict[str, Any] = {
            "symbol": None,
            "expiry": None,
            "future": None,
            "call": None,
            "put": None,
        }

        # Background quote polling task
        self.market_task: Optional[asyncio.Task] = None

        # Stop event for polling
        self.stop_event = asyncio.Event()

        # Polling interval
        self.poll_interval = 1.0

        # Prevent multiple polling loops
        self.market_loop_running = False

    # =========================================================
    # CONNECT
    # =========================================================

    async def connect(
        self,
        websocket: WebSocket,
    ) -> None:
        """
        Accept and register browser WebSocket.
        """

        await websocket.accept()

        if websocket not in self.connections:
            self.connections.append(websocket)

        logger.info(
            "WebSocket connected. Active connections: %d",
            len(self.connections),
        )

        await self.send_json(
            websocket,
            {
                "type": "connection",
                "status": "connected",
                "message": "Trading WebSocket connected.",
            },
        )

        # Start market polling if required
        self.start_market_loop()

    # =========================================================
    # DISCONNECT
    # =========================================================

    def disconnect(
        self,
        websocket: WebSocket,
    ) -> None:
        """
        Remove browser WebSocket.
        """

        if websocket in self.connections:
            self.connections.remove(websocket)

        logger.info(
            "WebSocket disconnected. Active connections: %d",
            len(self.connections),
        )

        # Stop polling when nobody is connected
        if not self.connections:
            self.stop_market_loop()

    # =========================================================
    # SEND ONE
    # =========================================================

    async def send_json(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
    ) -> bool:
        """
        Send JSON to one browser.
        """

        try:

            await websocket.send_json(data)

            return True

        except Exception as error:

            logger.warning(
                "WebSocket send failed: %s",
                error,
            )

            self.disconnect(websocket)

            return False

    # =========================================================
    # BROADCAST
    # =========================================================

    async def broadcast(
        self,
        data: Dict[str, Any],
    ) -> None:
        """
        Send JSON to every connected browser.
        """

        if not self.connections:
            return

        disconnected = []

        for websocket in list(self.connections):

            try:

                await websocket.send_json(data)

            except Exception as error:

                logger.warning(
                    "WebSocket broadcast failed: %s",
                    error,
                )

                disconnected.append(
                    websocket
                )

        for websocket in disconnected:

            self.disconnect(
                websocket
            )

    # =========================================================
    # BROADCAST TICK
    # =========================================================

    async def broadcast_tick(
        self,
        tick: Dict[str, Any],
    ) -> None:
        """
        Send normalized market tick.
        """

        await self.broadcast(
            {
                "type": "tick",
                "data": tick,
            }
        )

    # =========================================================
    # BROADCAST CANDLE
    # =========================================================

    async def broadcast_candle(
        self,
        chart: str,
        candle: Dict[str, Any],
    ) -> None:

        await self.broadcast(
            {
                "type": "candle",
                "chart": chart,
                "data": candle,
            }
        )

    # =========================================================
    # BROADCAST CHART UPDATE
    # =========================================================

    async def broadcast_chart_update(
        self,
        chart: str,
        data: Dict[str, Any],
    ) -> None:

        await self.broadcast(
            {
                "type": "chart_update",
                "chart": chart,
                "data": data,
            }
        )

    # =========================================================
    # BROADCAST SELECTION
    # =========================================================

    async def broadcast_selection(
        self,
        symbol: str,
        expiry: Optional[str] = None,
        future: Optional[Dict[str, Any]] = None,
        call: Optional[Dict[str, Any]] = None,
        put: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store and broadcast current Future / Call / Put
        selection.
        """

        self.selection = {
            "symbol": symbol,
            "expiry": expiry,
            "future": future,
            "call": call,
            "put": put,
        }

        await self.broadcast(
            {
                "type": "selection",
                "symbol": symbol,
                "expiry": expiry,
                "future": future,
                "call": call,
                "put": put,
            }
        )

    # =========================================================
    # SET SELECTION
    # =========================================================

    def set_selection(
        self,
        symbol: Optional[str] = None,
        expiry: Optional[str] = None,
        future: Optional[Dict[str, Any]] = None,
        call: Optional[Dict[str, Any]] = None,
        put: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update selected contracts without broadcasting.
        """

        if symbol is not None:
            self.selection["symbol"] = symbol

        if expiry is not None:
            self.selection["expiry"] = expiry

        if future is not None:
            self.selection["future"] = future

        if call is not None:
            self.selection["call"] = call

        if put is not None:
            self.selection["put"] = put

    # =========================================================
    # GET SELECTION
    # =========================================================

    def get_selection(self) -> Dict[str, Any]:
        """
        Return current selection.
        """

        return dict(
            self.selection
        )

    # =========================================================
    # STATUS
    # =========================================================

    async def broadcast_status(
        self,
        status: str,
        message: str = "",
    ) -> None:

        await self.broadcast(
            {
                "type": "status",
                "status": status,
                "message": message,
            }
        )

    # =========================================================
    # START MARKET LOOP
    # =========================================================

    def start_market_loop(self) -> None:
        """
        Start background market quote polling.
        """

        if self.market_loop_running:
            return

        if not self.connections:
            return

        self.stop_event.clear()

        self.market_task = asyncio.create_task(
            self.market_loop()
        )

        self.market_loop_running = True

        logger.info(
            "Market quote polling started."
        )

    # =========================================================
    # STOP MARKET LOOP
    # =========================================================

    def stop_market_loop(self) -> None:
        """
        Stop background market quote polling.
        """

        self.stop_event.set()

        if (
            self.market_task
            and not self.market_task.done()
        ):

            self.market_task.cancel()

        self.market_task = None

        self.market_loop_running = False

        logger.info(
            "Market quote polling stopped."
        )

    # =========================================================
    # MARKET LOOP
    # =========================================================

    async def market_loop(self) -> None:
        """
        Continuously request quotes for selected:

            Future
            Call
            Put

        and send them to the browser.

        This uses 5paisa REST market snapshot polling.
        """

        logger.info(
            "Market loop running."
        )

        while self.connections:

            try:

                if not broker.connected:

                    await self.broadcast_status(
                        "disconnected",
                        "5paisa is not connected.",
                    )

                    await asyncio.sleep(
                        self.poll_interval
                    )

                    continue

                contracts = (
                    self._get_selected_contracts()
                )

                if not contracts:

                    await asyncio.sleep(
                        self.poll_interval
                    )

                    continue

                await self._poll_quotes(
                    contracts
                )

            except asyncio.CancelledError:

                logger.info(
                    "Market loop cancelled."
                )

                break

            except Exception as error:

                logger.exception(
                    "Market loop error: %s",
                    error,
                )

                await self.broadcast_status(
                    "error",
                    str(error),
                )

            await asyncio.sleep(
                self.poll_interval
            )

        self.market_loop_running = False

        logger.info(
            "Market loop stopped."
        )

    # =========================================================
    # SELECTED CONTRACTS
    # =========================================================

    def _get_selected_contracts(self):
        """
        Build list of selected Future / Call / Put contracts.
        """

        contracts = []

        for chart_name in (
            "future",
            "call",
            "put",
        ):

            contract = self.selection.get(
                chart_name
            )

            if not contract:
                continue

            if not isinstance(
                contract,
                dict,
            ):
                continue

            scrip_code = (
                contract.get("scrip_code")
                or contract.get("broker_token")
                or contract.get("ScripCode")
                or contract.get("ScripCode")
            )

            exchange = (
                contract.get("exchange")
                or contract.get("Exchange")
            )

            exchange_type = (
                contract.get("exchange_type")
                or contract.get("ExchangeType")
                or "D"
            )

            if not scrip_code:
                continue

            if not exchange:
                continue

            try:

                scrip_code = int(
                    scrip_code
                )

            except Exception:

                continue

            contracts.append(
                {
                    "chart": chart_name,
                    "scrip_code": scrip_code,
                    "exchange": str(
                        exchange
                    ).upper(),
                    "exchange_type": str(
                        exchange_type
                    ).upper(),
                    "contract": contract,
                }
            )

        return contracts

    # =========================================================
    # POLL QUOTES
    # =========================================================

    async def _poll_quotes(
        self,
        contracts,
    ) -> None:
        """
        Request quotes from 5paisa.

        Quotes are requested one contract at a time so
        Future / Call / Put remain clearly separated.
        """

        for item in contracts:

            try:

                response = await asyncio.to_thread(
                    broker.get_quote,
                    item["exchange"],
                    item["exchange_type"],
                    item["scrip_code"],
                )

                quote = self._normalize_quote(
                    response
                )

                if quote is None:
                    continue

                ltp = self._extract_ltp(
                    quote
                )

                if ltp is None:
                    continue

                timestamp = (
                    datetime.now().isoformat()
                )

                tick = {
                    "chart":
                        item["chart"],

                    "symbol":
                        self.selection.get(
                            "symbol"
                        ),

                    "expiry":
                        self.selection.get(
                            "expiry"
                        ),

                    "scrip_code":
                        item["scrip_code"],

                    "exchange":
                        item["exchange"],

                    "exchange_type":
                        item["exchange_type"],

                    "ltp":
                        ltp,

                    "timestamp":
                        timestamp,

                    "quote":
                        quote,
                }

                await self.broadcast_tick(
                    tick
                )

            except Exception as error:

                logger.warning(
                    "Quote failed for %s %s: %s",
                    item["chart"],
                    item["scrip_code"],
                    error,
                )

    # =========================================================
    # NORMALIZE QUOTE
    # =========================================================

    def _normalize_quote(
        self,
        response: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Normalize different possible 5paisa quote
        response structures.
        """

        if response is None:
            return None

        # Direct dictionary
        if isinstance(
            response,
            dict,
        ):

            # Common containers
            for key in (
                "data",
                "Data",
                "body",
                "Body",
                "MarketSnapshot",
                "MarketSnapshotData",
            ):

                value = response.get(
                    key
                )

                if isinstance(
                    value,
                    list,
                ):

                    if value:

                        first = value[0]

                        if isinstance(
                            first,
                            dict,
                        ):

                            return first

                if isinstance(
                    value,
                    dict,
                ):

                    nested = (
                        self._normalize_quote(
                            value
                        )
                    )

                    if nested:
                        return nested

            return response

        # List response
        if isinstance(
            response,
            list,
        ):

            if not response:
                return None

            first = response[0]

            if isinstance(
                first,
                dict,
            ):

                return first

        return None

    # =========================================================
    # EXTRACT LTP
    # =========================================================

    def _extract_ltp(
        self,
        quote: Dict[str, Any],
    ) -> Optional[float]:
        """
        Extract LTP from different possible field names.
        """

        if not isinstance(
            quote,
            dict,
        ):
            return None

        possible_keys = (
            "LastRate",
            "LastTradedPrice",
            "LTP",
            "ltp",
            "LastPrice",
            "Close",
            "close",
        )

        for key in possible_keys:

            value = quote.get(
                key
            )

            if value in (
                None,
                "",
            ):
                continue

            try:

                return float(
                    value
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

        # Recursive search
        for value in quote.values():

            if isinstance(
                value,
                dict,
            ):

                result = (
                    self._extract_ltp(
                        value
                    )
                )

                if result is not None:
                    return result

            elif isinstance(
                value,
                list,
            ):

                for item in value:

                    if isinstance(
                        item,
                        dict,
                    ):

                        result = (
                            self._extract_ltp(
                                item
                            )
                        )

                        if result is not None:
                            return result

        return None

    # =========================================================
    # CONNECTION COUNT
    # =========================================================

    def connection_count(
        self,
    ) -> int:

        return len(
            self.connections
        )

    # =========================================================
    # STATUS
    # =========================================================

    def status(
        self,
    ) -> Dict[str, Any]:

        return {
            "active_connections":
                len(
                    self.connections
                ),

            "market_loop_running":
                self.market_loop_running,

            "broker_connected":
                broker.connected,

            "poll_interval":
                self.poll_interval,

            "selection":
                self.get_selection(),
        }


# =============================================================
# GLOBAL SHARED MANAGER
# =============================================================

manager = ConnectionManager()
