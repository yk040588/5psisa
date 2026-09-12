from __future__ import annotations

import asyncio
from typing import Dict, Optional

from fastapi import WebSocket

from Backend.broker import broker
from Backend.instruments import instrument_manager


class WebSocketManager:

    def __init__(self):

        self.clients: set[WebSocket] = set()

        self.selections: Dict[
            WebSocket,
            dict
        ] = {}

        self.running = False
        self.task: Optional[asyncio.Task] = None

    # ---------------------------------------------------------
    # START / STOP
    # ---------------------------------------------------------

    def start(self):

        if self.running:
            return

        self.running = True

        self.task = asyncio.create_task(
            self._market_loop()
        )

        print(
            "[WS] Market data loop started"
        )

    async def stop(self):

        self.running = False

        if self.task:

            try:
                await self.task
            except asyncio.CancelledError:
                pass

        self.task = None

        print(
            "[WS] Market data loop stopped"
        )

    # ---------------------------------------------------------
    # CLIENT
    # ---------------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
    ):

        await websocket.accept()

        self.clients.add(websocket)

        self.selections[websocket] = {
            "symbol": "NIFTY",
            "expiry": None,
            "timeframe": "5m",
            "call": None,
            "put": None,
            "future": None,
        }

        await self.send(
            websocket,
            {
                "type": "connection",
                "status": "connected",
            },
        )

    def disconnect(
        self,
        websocket: WebSocket,
    ):

        self.clients.discard(
            websocket
        )

        self.selections.pop(
            websocket,
            None,
        )

    # ---------------------------------------------------------
    # SEND
    # ---------------------------------------------------------

    async def send(
        self,
        websocket,
        data,
    ):

        try:
            await websocket.send_json(data)
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, data):

        clients = list(self.clients)

        for websocket in clients:
            await self.send(
                websocket,
                data,
            )

    # ---------------------------------------------------------
    # SELECTION
    # ---------------------------------------------------------

    def update_selection(
        self,
        websocket,
        selection: dict,
    ):

        current = self.selections.get(
            websocket,
            {},
        )

        current.update(selection)

        self.selections[
            websocket
        ] = current

    # ---------------------------------------------------------
    # QUOTE
    # ---------------------------------------------------------

    def _quote_ltp(
        self,
        instrument,
    ):

        if not instrument:
            return None

        try:

            raw = broker.get_quote(
                exchange=instrument.exchange,
                exchange_type=instrument.exchange_type,
                scrip_code=instrument.broker_token,
            )

            return self._extract_ltp(raw)

        except Exception as exc:

            print(
                f"[WS] Quote error "
                f"{instrument.symbol}: {exc}"
            )

            return None

    @staticmethod
    def _extract_ltp(raw):

        if raw is None:
            return None

        if isinstance(raw, dict):

            body = raw.get(
                "body",
                raw,
            )

            if isinstance(body, dict):

                for key in [
                    "Data",
                    "data",
                    "MarketSnapshotData",
                    "MarketFeedData",
                ]:

                    value = body.get(key)

                    if isinstance(value, list):
                        return (
                            WebSocketManager
                            ._extract_ltp(value)
                        )

                for key in [
                    "LTP",
                    "LastRate",
                    "LastTradedPrice",
                    "LastPrice",
                    "Close",
                ]:

                    if key in body:
                        try:
                            return float(body[key])
                        except Exception:
                            pass

            if isinstance(body, list):
                return (
                    WebSocketManager
                    ._extract_ltp(body)
                )

        if isinstance(raw, list):

            if not raw:
                return None

            for item in raw:

                if isinstance(item, dict):

                    for key in [
                        "LTP",
                        "LastRate",
                        "LastTradedPrice",
                        "LastPrice",
                        "Close",
                    ]:

                        if key in item:
                            try:
                                return float(
                                    item[key]
                                )
                            except Exception:
                                pass

        return None

    # ---------------------------------------------------------
    # MARKET LOOP
    # ---------------------------------------------------------

    async def _market_loop(self):

        while self.running:

            try:

                clients = list(
                    self.clients
                )

                for websocket in clients:

                    selection = (
                        self.selections.get(
                            websocket
                        )
                    )

                    if not selection:
                        continue

                    data = (
                        await asyncio.to_thread(
                            self._build_market_data,
                            selection,
                        )
                    )

                    await self.send(
                        websocket,
                        {
                            "type": "market_data",
                            "symbol": selection.get(
                                "symbol"
                            ),
                            "expiry": selection.get(
                                "expiry"
                            ),
                            "timeframe": selection.get(
                                "timeframe",
                                "5m",
                            ),
                            "data": data,
                        },
                    )

            except Exception as exc:

                print(
                    f"[WS] Loop error: {exc}"
                )

            await asyncio.sleep(2)

    # ---------------------------------------------------------
    # BUILD DATA
    # ---------------------------------------------------------

    def _build_market_data(
        self,
        selection,
    ):

        symbol = (
            selection.get("symbol")
            or "NIFTY"
        ).upper()

        expiry = selection.get(
            "expiry"
        )

        future = None
        call = None
        put = None

        # ---------------- FUTURE ----------------

        futures = (
            instrument_manager.get_futures(
                symbol,
                expiry=expiry,
            )
        )

        if futures:

            instrument = futures[0]

            ltp = self._quote_ltp(
                instrument
            )

            future = {
                "symbol": instrument.symbol,
                "scrip_code": instrument.broker_token,
                "ltp": ltp,
                "lot_size": instrument.lot_size,
            }

        # ---------------- CALL ----------------

        call_data = selection.get(
            "call"
        )

        if isinstance(call_data, dict):

            call_symbol = (
                call_data.get("symbol")
            )

            call_token = (
                call_data.get("scrip_code")
            )

            instrument = None

            if call_token:
                instrument = (
                    instrument_manager
                    .find_by_token(
                        int(call_token)
                    )
                )

            if instrument is None and call_symbol:

                for option in (
                    instrument_manager.get_options(
                        symbol,
                        expiry=expiry,
                        option_type="CALL",
                    )
                ):

                    if option.symbol == call_symbol:
                        instrument = option
                        break

            if instrument:

                call = {
                    "symbol": instrument.symbol,
                    "scrip_code": instrument.broker_token,
                    "strike": instrument.strike,
                    "ltp": self._quote_ltp(
                        instrument
                    ),
                }

        # ---------------- PUT ----------------

        put_data = selection.get(
            "put"
        )

        if isinstance(put_data, dict):

            put_symbol = (
                put_data.get("symbol")
            )

            put_token = (
                put_data.get("scrip_code")
            )

            instrument = None

            if put_token:
                instrument = (
                    instrument_manager
                    .find_by_token(
                        int(put_token)
                    )
                )

            if instrument is None and put_symbol:

                for option in (
                    instrument_manager.get_options(
                        symbol,
                        expiry=expiry,
                        option_type="PUT",
                    )
                ):

                    if option.symbol == put_symbol:
                        instrument = option
                        break

            if instrument:

                put = {
                    "symbol": instrument.symbol,
                    "scrip_code": instrument.broker_token,
                    "strike": instrument.strike,
                    "ltp": self._quote_ltp(
                        instrument
                    ),
                }

        return {
            "future": future,
            "call": call,
            "put": put,
        }


websocket_manager = WebSocketManager()
