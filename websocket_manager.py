from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

import websockets
from fastapi import WebSocket

try:
    from config.settings import settings
except Exception:
    settings = None

from .broker import broker
from .market_data import market_data


logger = logging.getLogger(__name__)


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_XSTREAM_WS_URL = (
    "wss://openfeed.5paisa.com/feeds/api/chat"
)

DEFAULT_RECONNECT_SECONDS = 3
DEFAULT_HEARTBEAT_SECONDS = 20


def _setting(name: str, default: Any = None) -> Any:
    if settings is not None:
        try:
            value = getattr(settings, name, None)

            if value is not None:
                return value
        except Exception:
            pass

    return default


def _get_broker_value(
    names: Iterable[str],
) -> Optional[str]:
    """
    Try to obtain a value from broker object.
    """

    for name in names:

        try:
            value = getattr(
                broker,
                name,
                None,
            )

            if value:

                if callable(value):
                    value = value()

                    if inspect.isawaitable(value):
                        continue

                if value:
                    return str(value)

        except Exception:
            continue

    return None


# ============================================================
# XSTREAM MARKET WEBSOCKET MANAGER
# ============================================================

class WebSocketManager:
    """
    5paisa Xstream MarketFeedV3 WebSocket manager.

    Architecture:

        5paisa Xstream
              |
              | MarketFeedV3
              v
        WebSocketManager
              |
              +---- market_data.process_tick()
              |
              +---- Browser WebSocket
              |
              +---- Future / Call / Put charts

    Phase 1:
        - Live market data only
        - No order placement
        - No trading logic
        - No REST quote polling
    """

    def __init__(self) -> None:

        # ----------------------------------------------------
        # Browser connections
        # ----------------------------------------------------

        self.browser_clients: set[WebSocket] = set()

        # ----------------------------------------------------
        # Xstream connection
        # ----------------------------------------------------

        self.xstream_socket = None

        self.xstream_task: Optional[asyncio.Task] = None

        self.running = False
        self.connected = False

        self.reconnect_seconds = int(
            _setting(
                "WEBSOCKET_RECONNECT_SECONDS",
                DEFAULT_RECONNECT_SECONDS,
            )
        )

        self.heartbeat_seconds = int(
            _setting(
                "WEBSOCKET_HEARTBEAT_SECONDS",
                DEFAULT_HEARTBEAT_SECONDS,
            )
        )

        # ----------------------------------------------------
        # Current subscribed instruments
        #
        # key:
        #     (Exch, ExchType, ScripCode)
        # ----------------------------------------------------

        self.subscriptions: Dict[
            tuple[str, str, int],
            Dict[str, Any],
        ] = {}

        self.subscription_lock = asyncio.Lock()

        # ----------------------------------------------------
        # Last normalized tick
        # ----------------------------------------------------

        self.latest_ticks: Dict[
            int,
            Dict[str, Any],
        ] = {}

        # ----------------------------------------------------
        # Market data callback
        # ----------------------------------------------------

        self.market_data_callback = (
            self._handle_market_tick
        )

    # ========================================================
    # CREDENTIALS
    # ========================================================

    def _get_access_token(self) -> Optional[str]:
        """
        Get access token from broker.py.

        Supports several possible broker attribute names
        so this manager remains compatible with the existing
        broker implementation.
        """

        token = _get_broker_value(
            (
                "access_token",
                "_access_token",
                "token",
                "_token",
            )
        )

        if token:
            return token

        # Try broker getter methods.
        for method_name in (
            "get_access_token",
            "get_token",
        ):

            try:

                method = getattr(
                    broker,
                    method_name,
                    None,
                )

                if not method:
                    continue

                value = method()

                if inspect.isawaitable(value):
                    continue

                if value:
                    return str(value)

            except Exception:
                continue

        return None

    def _get_client_code(self) -> Optional[str]:
        """
        Current 5paisa client/demat code.
        """

        value = _get_broker_value(
            (
                "client_code",
                "clientcode",
                "clientCode",
                "user_id",
                "ClientCode",
            )
        )

        if value:
            return value

        return _setting(
            "FIVEPAISA_CLIENT_CODE",
            None,
        ) or _setting(
            "FIVEPAISA_USER_ID",
            None,
        )

    def _build_xstream_url(self) -> str:
        """
        5paisa Xstream MarketFeedV3 connection URL.
        """

        access_token = self._get_access_token()
        client_code = self._get_client_code()

        if not access_token:
            raise RuntimeError(
                "5paisa access token is not available."
            )

        if not client_code:
            raise RuntimeError(
                "5paisa client code is not available."
            )

        base_url = str(
            _setting(
                "FIVEPAISA_WEBSOCKET_URL",
                DEFAULT_XSTREAM_WS_URL,
            )
        ).rstrip("/")

        return (
            f"{base_url}"
            f"?Value1={access_token}|{client_code}"
        )

    # ========================================================
    # XSTREAM CONNECTION
    # ========================================================

    async def start(self) -> None:
        """
        Start the background Xstream MarketFeedV3 task.
        """

        if self.running:
            return

        self.running = True

        self.xstream_task = asyncio.create_task(
            self._connection_loop()
        )

        logger.info(
            "5paisa Xstream WebSocket manager started."
        )

    async def stop(self) -> None:
        """
        Stop Xstream connection and background task.
        """

        self.running = False

        await self._close_xstream()

        task = self.xstream_task

        self.xstream_task = None

        if task:

            if task is not asyncio.current_task():

                try:
                    await task

                except asyncio.CancelledError:
                    pass

        self.connected = False

        logger.info(
            "5paisa Xstream WebSocket manager stopped."
        )

    async def _connection_loop(self) -> None:

        while self.running:

            try:

                await self._connect_xstream()

            except asyncio.CancelledError:
                break

            except Exception as exc:

                self.connected = False

                logger.exception(
                    "Xstream WebSocket error: %s",
                    exc,
                )

                await self._broadcast_status(
                    "reconnecting",
                    str(exc),
                )

            if not self.running:
                break

            await asyncio.sleep(
                self.reconnect_seconds
            )

    async def _connect_xstream(self) -> None:

        url = self._build_xstream_url()

        logger.info(
            "Connecting to 5paisa Xstream MarketFeedV3..."
        )

        await self._broadcast_status(
            "connecting",
            "Connecting to 5paisa Xstream...",
        )

        # ----------------------------------------------------
        # websockets library compatibility
        # ----------------------------------------------------

        try:

            websocket = await websockets.connect(
                url,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=5,
            )

        except TypeError:

            # Compatibility with older websockets versions.
            websocket = await websockets.connect(
                url
            )

        self.xstream_socket = websocket
        self.connected = True

        logger.info(
            "Connected to 5paisa Xstream MarketFeedV3."
        )

        await self._broadcast_status(
            "connected",
            "5paisa Xstream market feed connected.",
        )

        try:

            # Re-subscribe current instruments after
            # reconnect.
            await self._resubscribe_all()

            await self._receive_loop()

        finally:

            self.connected = False

            await self._broadcast_status(
                "disconnected",
                "5paisa Xstream market feed disconnected.",
            )

            await self._close_xstream(
                close_socket=False
            )

    # ========================================================
    # RECEIVE LOOP
    # ========================================================

    async def _receive_loop(self) -> None:

        if self.xstream_socket is None:
            return

        while (
            self.running
            and self.xstream_socket is not None
        ):

            try:

                message = await asyncio.wait_for(
                    self.xstream_socket.recv(),
                    timeout=self.heartbeat_seconds,
                )

                await self._process_xstream_message(
                    message
                )

            except asyncio.TimeoutError:

                # Keep connection alive.
                await self._send_ping()

            except asyncio.CancelledError:

                raise

            except Exception:

                raise

    async def _send_ping(self) -> None:

        socket = self.xstream_socket

        if socket is None:
            return

        try:

            ping = socket.ping()

            if inspect.isawaitable(ping):
                await ping

        except Exception:

            # Let receive loop reconnect naturally.
            raise

    # ========================================================
    # MESSAGE PROCESSING
    # ========================================================

    async def _process_xstream_message(
        self,
        message: Any,
    ) -> None:

        if message is None:
            return

        if isinstance(
            message,
            bytes,
        ):

            message = message.decode(
                "utf-8",
                errors="ignore",
            )

        if isinstance(
            message,
            str,
        ):

            try:

                payload = json.loads(
                    message
                )

            except json.JSONDecodeError:

                logger.debug(
                    "Non-JSON Xstream message: %s",
                    message,
                )

                return

        else:

            payload = message

        await self._process_payload(
            payload
        )

    async def _process_payload(
        self,
        payload: Any,
    ) -> None:

        # ----------------------------------------------------
        # Direct list
        # ----------------------------------------------------

        if isinstance(
            payload,
            list,
        ):

            for item in payload:

                await self._process_payload(
                    item
                )

            return

        # ----------------------------------------------------
        # Direct market tick
        # ----------------------------------------------------

        if isinstance(
            payload,
            dict,
        ):

            tick = market_data.normalize_tick(
                payload
            )

            if tick is not None:

                await self._handle_market_tick(
                    tick
                )

                return

            # ------------------------------------------------
            # Search nested objects/lists
            # ------------------------------------------------

            for key, value in payload.items():

                if key in (
                    "Data",
                    "data",
                    "MarketFeedData",
                    "MarketFeedV3",
                    "body",
                    "Body",
                    "response",
                ):

                    await self._process_payload(
                        value
                    )

    # ========================================================
    # MARKET TICK
    # ========================================================

    async def _handle_market_tick(
        self,
        tick: Dict[str, Any],
    ) -> None:

        token = tick.get(
            "token"
        )

        if token is None:
            return

        token = int(token)

        self.latest_ticks[token] = tick

        # Send normalized tick into market_data.
        try:

            await market_data.process_tick(
                tick
            )

        except Exception:

            logger.exception(
                "Unable to process market tick."
            )

        # Send tick to browser.
        await self.broadcast_tick(
            tick
        )

    # ========================================================
    # SUBSCRIPTION NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_instrument(
        instrument: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert final instruments.py object into exactly
        the format required by 5paisa MarketFeedV3.
        """

        if instrument is None:
            return None

        def value(
            names: Iterable[str],
            default: Any = None,
        ) -> Any:

            if isinstance(
                instrument,
                dict,
            ):

                for name in names:

                    result = instrument.get(
                        name
                    )

                    if result is not None:
                        return result

            else:

                for name in names:

                    try:

                        result = getattr(
                            instrument,
                            name,
                            None,
                        )

                        if result is not None:
                            return result

                    except Exception:
                        pass

            return default

        exchange = value(
            (
                "exchange",
                "Exchange",
                "Exch",
            )
        )

        exchange_type = value(
            (
                "exchange_type",
                "ExchangeType",
                "ExchType",
            )
        )

        scrip_code = value(
            (
                "scrip_code",
                "ScripCode",
                "broker_token",
                "BrokerToken",
                "token",
                "Token",
            )
        )

        if not exchange:
            return None

        if not exchange_type:
            return None

        if scrip_code is None:
            return None

        try:

            scrip_code = int(
                scrip_code
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if scrip_code <= 0:
            return None

        return {
            "Exch": str(
                exchange
            ).upper(),

            "ExchType": str(
                exchange_type
            ).upper(),

            "ScripCode": scrip_code,

            "symbol": value(
                (
                    "symbol",
                    "Symbol",
                )
            ),

            "instrument_type": value(
                (
                    "instrument_type",
                    "InstrumentType",
                )
            ),

            "strike": value(
                (
                    "strike",
                    "Strike",
                )
            ),

            "option_type": value(
                (
                    "option_type",
                    "OptionType",
                )
            ),

            "expiry": value(
                (
                    "expiry",
                    "Expiry",
                )
            ),
        }

    # ========================================================
    # SUBSCRIBE
    # ========================================================

    async def subscribe(
        self,
        instruments: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Subscribe one or more instruments.

        Example:
            1 Future
            15 Calls
            15 Puts

        Total:
            maximum 31 instruments.
        """

        normalized: List[
            Dict[str, Any]
        ] = []

        for instrument in instruments:

            item = self._normalize_instrument(
                instrument
            )

            if item is None:
                continue

            key = (
                item["Exch"],
                item["ExchType"],
                item["ScripCode"],
            )

            self.subscriptions[key] = item

            normalized.append(item)

        if not normalized:
            return []

        if self.connected:

            await self._send_subscription(
                "Subscribe",
                normalized,
            )

        return normalized

    async def subscribe_instruments(
        self,
        instruments: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Explicit alias used by main.py.
        """

        return await self.subscribe(
            instruments
        )

    # ========================================================
    # UNSUBSCRIBE
    # ========================================================

    async def unsubscribe(
        self,
        instruments: Iterable[Any],
    ) -> List[Dict[str, Any]]:

        normalized: List[
            Dict[str, Any]
        ] = []

        for instrument in instruments:

            item = self._normalize_instrument(
                instrument
            )

            if item is None:
                continue

            key = (
                item["Exch"],
                item["ExchType"],
                item["ScripCode"],
            )

            self.subscriptions.pop(
                key,
                None,
            )

            normalized.append(
                item
            )

        if (
            normalized
            and self.connected
        ):

            await self._send_subscription(
                "Unsubscribe",
                normalized,
            )

        return normalized

    async def unsubscribe_instruments(
        self,
        instruments: Iterable[Any],
    ) -> List[Dict[str, Any]]:

        return await self.unsubscribe(
            instruments
        )

    # ========================================================
    # RE-SUBSCRIBE
    # ========================================================

    async def _resubscribe_all(self) -> None:

        if not self.subscriptions:
            return

        instruments = list(
            self.subscriptions.values()
        )

        await self._send_subscription(
            "Subscribe",
            instruments,
        )

    # ========================================================
    # SEND SUBSCRIPTION REQUEST
    # ========================================================

    async def _send_subscription(
        self,
        operation: str,
        instruments: List[Dict[str, Any]],
    ) -> None:

        if self.xstream_socket is None:
            return

        client_code = (
            self._get_client_code()
        )

        if not client_code:
            raise RuntimeError(
                "5paisa client code is missing."
            )

        market_feed_data = []

        for item in instruments:

            market_feed_data.append(
                {
                    "Exch": item["Exch"],
                    "ExchType": item["ExchType"],
                    "ScripCode": item["ScripCode"],
                }
            )

        payload = {
            "Method": "MarketFeedV3",
            "Operation": operation,
            "ClientCode": client_code,
            "MarketFeedData": market_feed_data,
        }

        logger.info(
            "Xstream %s: %d instruments",
            operation,
            len(market_feed_data),
        )

        await self.xstream_socket.send(
            json.dumps(
                payload
            )
        )

    # ========================================================
    # REPLACE SUBSCRIPTIONS
    # ========================================================

    async def replace_subscriptions(
        self,
        instruments: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Replace existing live subscriptions.

        This is the important method for:

            Symbol change
            Expiry change
            Call/Put change
        """

        new_items: List[
            Dict[str, Any]
        ] = []

        for instrument in instruments:

            item = self._normalize_instrument(
                instrument
            )

            if item is not None:
                new_items.append(
                    item
                )

        new_keys = {
            (
                item["Exch"],
                item["ExchType"],
                item["ScripCode"],
            )
            for item in new_items
        }

        old_items = list(
            self.subscriptions.values()
        )

        old_keys = {
            (
                item["Exch"],
                item["ExchType"],
                item["ScripCode"],
            )
            for item in old_items
        }

        to_remove = [
            item
            for item in old_items
            if (
                item["Exch"],
                item["ExchType"],
                item["ScripCode"],
            ) not in new_keys
        ]

        to_add = [
            item
            for item in new_items
            if (
                item["Exch"],
                item["ExchType"],
                item["ScripCode"],
            ) not in old_keys
        ]

        # ----------------------------------------------------
        # Unsubscribe old instruments
        # ----------------------------------------------------

        if (
            to_remove
            and self.connected
        ):

            await self._send_subscription(
                "Unsubscribe",
                to_remove,
            )

        # ----------------------------------------------------
        # Replace local state
        # ----------------------------------------------------

        self.subscriptions.clear()

        for item in new_items:

            key = (
                item["Exch"],
                item["ExchType"],
                item["ScripCode"],
            )

            self.subscriptions[key] = item

        # ----------------------------------------------------
        # Subscribe new instruments
        # ----------------------------------------------------

        if (
            to_add
            and self.connected
        ):

            await self._send_subscription(
                "Subscribe",
                to_add,
            )

        return new_items

    # ========================================================
    # BROWSER WEBSOCKET
    # ========================================================

    async def connect_browser(
        self,
        websocket: WebSocket,
    ) -> None:

        await websocket.accept()

        self.browser_clients.add(
            websocket
        )

        await self.send_to_browser(
            websocket,
            {
                "type": "connection",
                "status": (
                    "connected"
                    if self.connected
                    else "waiting"
                ),
            },
        )

        logger.info(
            "Browser WebSocket connected. "
            "Clients=%d",
            len(self.browser_clients),
        )

    def disconnect_browser(
        self,
        websocket: WebSocket,
    ) -> None:

        self.browser_clients.discard(
            websocket
        )

        logger.info(
            "Browser WebSocket disconnected. "
            "Clients=%d",
            len(self.browser_clients),
        )

    async def send_to_browser(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
    ) -> bool:

        try:

            await websocket.send_json(
                data
            )

            return True

        except Exception:

            self.disconnect_browser(
                websocket
            )

            return False

    async def broadcast(
        self,
        data: Dict[str, Any],
    ) -> None:

        if not self.browser_clients:
            return

        disconnected = []

        for websocket in list(
            self.browser_clients
        ):

            try:

                await websocket.send_json(
                    data
                )

            except Exception:

                disconnected.append(
                    websocket
                )

        for websocket in disconnected:

            self.disconnect_browser(
                websocket
            )

    async def broadcast_tick(
        self,
        tick: Dict[str, Any],
    ) -> None:

        await self.broadcast(
            {
                "type": "tick",
                "data": tick,
            }
        )

    async def broadcast_status(
        self,
        status: str,
        message: str = "",
    ) -> None:

        await self._broadcast_status(
            status,
            message,
        )

    async def _broadcast_status(
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

    # ========================================================
    # COMPATIBILITY BROWSER METHODS
    # ========================================================

    async def connect(
        self,
        websocket: WebSocket,
    ) -> None:
        """
        Compatibility alias.

        IMPORTANT:
        This is the browser WebSocket, not the 5paisa
        Xstream connection.
        """

        await self.connect_browser(
            websocket
        )

    def disconnect(
        self,
        websocket: WebSocket,
    ) -> None:

        self.disconnect_browser(
            websocket
        )

    async def send_json(
        self,
        websocket: WebSocket,
        data: Dict[str, Any],
    ) -> bool:

        return await self.send_to_browser(
            websocket,
            data,
        )

    # ========================================================
    # STATUS
    # ========================================================

    def connection_count(self) -> int:
        return len(
            self.browser_clients
        )

    def subscription_count(self) -> int:
        return len(
            self.subscriptions
        )

    def status(self) -> Dict[str, Any]:

        return {
            "running": self.running,
            "connected": self.connected,
            "browser_connections": (
                len(self.browser_clients)
            ),
            "subscriptions": (
                len(self.subscriptions)
            ),
            "subscribed_instruments": [
                {
                    "Exch": item["Exch"],
                    "ExchType": item["ExchType"],
                    "ScripCode": item["ScripCode"],
                    "symbol": item.get(
                        "symbol"
                    ),
                    "instrument_type": item.get(
                        "instrument_type"
                    ),
                    "strike": item.get(
                        "strike"
                    ),
                    "option_type": item.get(
                        "option_type"
                    ),
                }
                for item in self.subscriptions.values()
            ],
        }


# ============================================================
# SHARED INSTANCE
# ============================================================

websocket_manager = WebSocketManager()

# Compatibility alias.
manager = websocket_manager
