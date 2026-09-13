from __future__ import annotations

import asyncio

from fastapi import WebSocket

from Backend.broker import broker
from Backend.instruments import instrument_manager


class WebSocketManager:

    def __init__(self):

        self.clients = set()

        self.selections = {}

        self.running = False

        self.task = None

    # -------------------------------------------------sssd
    # START / STOP
    # -------------------------------------------------

    async def start(self):

        if self.running:
            return

        self.running = True

        self.task = asyncio.create_task(
            self._market_loop()
        )

        print(
            "Market WebSocket manager started"
        )

    async def stop(self):

        self.running = False

        if self.task:

            self.task.cancel()

            try:
                await self.task

            except asyncio.CancelledError:
                pass

            self.task = None

        print(
            "Market WebSocket manager stopped"
        )

    # -------------------------------------------------
    # CLIENT CONNECTION
    # -------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket
    ):

        await websocket.accept()

        self.clients.add(
            websocket
        )

        self.selections[
            websocket
        ] = {
            "symbol": "NIFTY",
            "expiry": None,
            "timeframe": "5m",
            "future": None,
            "call": None,
            "put": None
        }

        await self.send(
            websocket,
            {
                "type": "connection",
                "status": "connected"
            }
        )

    async def disconnect(
        self,
        websocket: WebSocket
    ):

        self.clients.discard(
            websocket
        )

        self.selections.pop(
            websocket,
            None
        )

    # -------------------------------------------------
    # SEND
    # -------------------------------------------------

    async def send(
        self,
        websocket,
        message
    ):

        try:

            await websocket.send_json(
                message
            )

        except Exception:

            await self.disconnect(
                websocket
            )

    # -------------------------------------------------
    # SELECTION
    # -------------------------------------------------

    def update_selection(
        self,
        websocket,
        selection
    ):

        if websocket not in self.clients:
            return

        current = self.selections.get(
            websocket,
            {}
        )

        current.update(
            selection or {}
        )

        self.selections[
            websocket
        ] = current

    # -------------------------------------------------
    # MARKET LOOP
    # -------------------------------------------------

    async def _market_loop(self):

        while self.running:

            clients = list(
                self.clients
            )

            for websocket in clients:

                try:

                    selection = (
                        self.selections.get(
                            websocket,
                            {}
                        )
                    )

                    data = await asyncio.to_thread(
                        self._build_market_data,
                        selection
                    )

                    await self.send(
                        websocket,
                        {
                            "type": "market_data",
                            "data": data
                        }
                    )

                except Exception as error:

                    print(
                        "Market loop error:",
                        error
                    )

            await asyncio.sleep(2)

    # -------------------------------------------------
    # BUILD MARKET DATA
    # -------------------------------------------------

    def _build_market_data(
        self,
        selection
    ):

        symbol = (
            selection.get("symbol")
            or "NIFTY"
        )

        expiry = selection.get(
            "expiry"
        )

        future = self._get_future(
            symbol,
            expiry
        )

        call = self._get_selected(
            selection.get("call"),
            "CALL"
        )

        put = self._get_selected(
            selection.get("put"),
            "PUT"
        )

        return {
            "timestamp": (
                asyncio.get_event_loop()
                if False
                else None
            ),
            "future": self._quote(
                future
            ),
            "call": self._quote(
                call
            ),
            "put": self._quote(
                put
            )
        }

    # -------------------------------------------------
    # FUTURE
    # -------------------------------------------------

    def _get_future(
        self,
        symbol,
        expiry
    ):

        futures = (
            instrument_manager.get_futures(
                symbol,
                expiry
            )
        )

        if not futures and expiry:

            futures = (
                instrument_manager.get_futures(
                    symbol
                )
            )

        return (
            futures[0]
            if futures
            else None
        )

    # -------------------------------------------------
    # SELECTED OPTION
    # -------------------------------------------------

    def _get_selected(
        self,
        selected,
        instrument_type
    ):

        if not selected:
            return None

        token = (
            selected.get("scrip_code")
            or selected.get("broker_token")
        )

        if token:

            instrument = (
                instrument_manager
                .find_by_token(token)
            )

            if instrument:
                return instrument

        symbol = selected.get(
            "symbol"
        )

        if symbol:

            instrument = (
                instrument_manager
                .find_by_symbol(symbol)
            )

            if instrument:
                return instrument

        return None

    # -------------------------------------------------
    # QUOTE
    # -------------------------------------------------

    def _quote(
        self,
        instrument
    ):

        if not instrument:
            return None

        try:

            response = broker.get_quote(
                exchange=instrument.exchange,
                exchange_type=(
                    instrument.exchange_type
                ),
                scrip_code=(
                    instrument.broker_token
                )
            )

            ltp = self._extract_ltp(
                response
            )

            return {
                "symbol": instrument.symbol,
                "scrip_code": (
                    instrument.broker_token
                ),
                "ltp": ltp
            }

        except Exception as error:

            print(
                "Quote error:",
                error
            )

            return {
                "symbol": instrument.symbol,
                "scrip_code": (
                    instrument.broker_token
                ),
                "ltp": None
            }

    # -------------------------------------------------
    # EXTRACT LTP
    # -------------------------------------------------

    @staticmethod
    def _extract_ltp(
        response
    ):

        if not response:
            return None

        if isinstance(
            response,
            dict
        ):

            for key in (
                "LTP",
                "LastRate",
                "LastTradedPrice",
                "LastPrice"
            ):

                if key in response:

                    try:
                        return float(
                            response[key]
                        )
                    except Exception:
                        pass

            for key in (
                "body",
                "Body",
                "Data",
                "data"
            ):

                nested = response.get(key)

                value = (
                    WebSocketManager
                    ._extract_ltp(
                        nested
                    )
                )

                if value is not None:
                    return value

        elif isinstance(
            response,
            list
        ):

            for item in response:

                value = (
                    WebSocketManager
                    ._extract_ltp(
                        item
                    )
                )

                if value is not None:
                    return value

        return None


websocket_manager = WebSocketManager()
