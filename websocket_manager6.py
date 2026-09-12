import asyncio
from typing import Dict, Optional

from fastapi import WebSocket

from Backend.broker import broker


class WebSocketManager:

    def __init__(self):
        self.connections: Dict[WebSocket, dict] = {}
        self.running = False
        self.polling_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()

        self.connections[websocket] = {
            "symbol": "NIFTY",
            "expiry": None,
            "timeframe": "5m",
            "future": None,
            "call": None,
            "put": None,
        }

        print(
            f"[WS] Client connected. "
            f"Total clients: {len(self.connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        self.connections.pop(websocket, None)

        print(
            f"[WS] Client disconnected. "
            f"Total clients: {len(self.connections)}"
        )

    async def send_personal_message(
        self,
        message,
        websocket: WebSocket,
    ):
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)

    def set_selection(
        self,
        websocket: WebSocket,
        selection: dict,
    ):
        if websocket not in self.connections:
            return

        current = self.connections[websocket]

        for key in [
            "symbol",
            "expiry",
            "timeframe",
            "future",
            "call",
            "put",
        ]:
            if key in selection:
                current[key] = selection[key]

        print("[WS] Selection updated:", current)

    def update_selection(
        self,
        websocket: WebSocket,
        selection: dict,
    ):
        self.set_selection(
            websocket,
            selection,
        )

    async def subscribe(
        self,
        websocket: WebSocket,
        selection: dict,
    ):
        self.set_selection(
            websocket,
            selection,
        )

    def start(self):

        if self.running:
            return

        self.running = True

        try:
            loop = asyncio.get_running_loop()

            self.polling_task = loop.create_task(
                self.market_data_loop()
            )

            print("[WS] Market data loop started")

        except RuntimeError:
            print(
                "[WS] Event loop not available"
            )

    async def stop(self):

        self.running = False

        if self.polling_task:

            self.polling_task.cancel()

            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass

            self.polling_task = None

        print("[WS] Market data loop stopped")

    async def market_data_loop(self):

        while self.running:

            try:

                if not self.connections:
                    await asyncio.sleep(1)
                    continue

                clients = list(
                    self.connections.items()
                )

                for websocket, selection in clients:

                    try:

                        await self.send_live_data(
                            websocket,
                            selection,
                        )

                    except Exception as exc:

                        print(
                            f"[WS] Client update error: {exc}"
                        )

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break

            except Exception as exc:

                print(
                    f"[WS] Market loop error: {exc}"
                )

                await asyncio.sleep(2)

    async def send_live_data(
        self,
        websocket: WebSocket,
        selection: dict,
    ):

        instruments = {
            "future": selection.get("future"),
            "call": selection.get("call"),
            "put": selection.get("put"),
        }

        market_data = {}

        for name, instrument in instruments.items():

            if not instrument:
                continue

            ltp = await self.get_ltp(
                instrument
            )

            market_data[name] = {
                "ltp": ltp,
                "instrument": instrument,
            }

        if not market_data:
            return

        payload = {
            "type": "market_data",
            "symbol": selection.get(
                "symbol",
                "NIFTY",
            ),
            "expiry": selection.get("expiry"),
            "timeframe": selection.get(
                "timeframe",
                "5m",
            ),
            "data": market_data,
        }

        try:

            await websocket.send_json(
                payload
            )

        except Exception:

            self.disconnect(
                websocket
            )

    async def get_ltp(
        self,
        instrument,
    ):

        try:

            if not isinstance(
                instrument,
                dict,
            ):
                return None

            scrip_code = (
                instrument.get("scrip_code")
                or instrument.get("broker_token")
            )

            exchange = instrument.get(
                "exchange"
            )

            if not scrip_code or not exchange:
                return None

            response = await asyncio.to_thread(
                broker.get_quote,
                exchange=exchange,
                exchange_type="D",
                scrip_code=int(scrip_code),
            )

            return self.extract_ltp(
                response
            )

        except Exception as exc:

            print(
                f"[WS] LTP error: {exc}"
            )

            return None

    @staticmethod
    def extract_ltp(response):

        if response is None:
            return None

        if isinstance(
            response,
            (int, float),
        ):
            return float(response)

        if isinstance(
            response,
            dict,
        ):

            keys = [
                "LastRate",
                "last_rate",
                "LTP",
                "ltp",
                "LastPrice",
                "last_price",
                "Close",
                "close",
            ]

            for key in keys:

                if key in response:

                    try:
                        return float(
                            response[key]
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

            for value in response.values():

                result = WebSocketManager.extract_ltp(
                    value
                )

                if result is not None:
                    return result

        elif isinstance(
            response,
            list,
        ):

            for item in response:

                result = WebSocketManager.extract_ltp(
                    item
                )

                if result is not None:
                    return result

        return None


websocket_manager = WebSocketManager()
