"""
market_data.py

Market-data service for the trading dashboard.

Responsibilities:
    - Get quotes from broker.py
    - Get historical candles
    - Track Future / Call / Put
    - Normalize broker data
    - Process live ticks
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .broker import broker

logger = logging.getLogger(__name__)


class MarketDataError(Exception):
    """Raised when market-data processing fails."""
    pass


class MarketDataService:

    def __init__(self):

        self.running = False

        self.active_instruments: dict[str, dict[str, Any]] = {
            "future": {},
            "call": {},
            "put": {},
        }

        self.latest_ticks: dict[str, dict[str, Any]] = {}

        self.tick_callbacks = []

    # ---------------------------------------------------------
    # BROKER CONNECTION
    # ---------------------------------------------------------

    def is_broker_connected(self) -> bool:

        return bool(
            getattr(broker, "connected", False)
        )

    # ---------------------------------------------------------
    # Instrument selection
    # ---------------------------------------------------------

    def set_instrument(
        self,
        chart_type: str,
        instrument: dict[str, Any],
    ) -> None:

        if chart_type not in self.active_instruments:

            raise MarketDataError(
                f"Invalid chart type: {chart_type}"
            )

        self.active_instruments[chart_type] = instrument

        logger.info(
            "%s instrument selected: %s",
            chart_type,
            instrument.get("symbol"),
        )

    def get_active_instruments(
        self,
    ) -> dict[str, dict[str, Any]]:

        return self.active_instruments

    # ---------------------------------------------------------
    # Historical candles
    # ---------------------------------------------------------

    def get_candles(
        self,
        instrument: dict[str, Any],
        interval: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:

        if not self.is_broker_connected():

            raise MarketDataError(
                "5paisa is not connected."
            )

        exchange = instrument.get("exchange")

        exchange_type = (
            instrument.get("exchange_type")
            or instrument.get("exchangeType")
            or "D"
        )

        broker_token = (
            instrument.get("broker_token")
            or instrument.get("scrip_code")
            or instrument.get("ScripCode")
            or instrument.get("Token")
        )

        if not exchange:

            raise MarketDataError(
                "Instrument is missing exchange."
            )

        if broker_token is None:

            raise MarketDataError(
                "Instrument is missing ScripCode."
            )

        try:

            raw_data = broker.get_historical_data(
                exchange=exchange,
                exchange_type=exchange_type,
                scrip_code=int(broker_token),
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            return self.normalize_candles(
                raw_data
            )

        except Exception as exc:

            logger.exception(
                "Historical-data request failed."
            )

            raise MarketDataError(
                str(exc)
            ) from exc

    # ---------------------------------------------------------
    # Candle normalization
    # ---------------------------------------------------------

    @staticmethod
    def normalize_candles(
        raw_data: Any,
    ) -> list[dict[str, Any]]:

        # 5paisa response can contain body / candles
        candles = raw_data

        if isinstance(raw_data, dict):

            body = raw_data.get(
                "body",
                raw_data
            )

            if isinstance(body, dict):

                candles = (
                    body.get("Data")
                    or body.get("data")
                    or body.get("Candle")
                    or body.get("candles")
                    or body
                )

        if isinstance(candles, dict):

            candles = (
                candles.get("Data")
                or candles.get("data")
                or []
            )

        if not isinstance(candles, list):

            return []

        normalized = []

        for candle in candles:

            if not isinstance(candle, dict):
                continue

            time_value = (
                candle.get("time")
                or candle.get("Time")
                or candle.get("timestamp")
                or candle.get("Timestamp")
            )

            open_value = (
                candle.get("open")
                or candle.get("Open")
            )

            high_value = (
                candle.get("high")
                or candle.get("High")
            )

            low_value = (
                candle.get("low")
                or candle.get("Low")
            )

            close_value = (
                candle.get("close")
                or candle.get("Close")
            )

            volume_value = (
                candle.get("volume")
                or candle.get("Volume")
            )

            normalized.append({

                "time": time_value,

                "open":
                    _number(open_value),

                "high":
                    _number(high_value),

                "low":
                    _number(low_value),

                "close":
                    _number(close_value),

                "volume":
                    _number(volume_value),
            })

        return normalized

    # ---------------------------------------------------------
    # Quote
    # ---------------------------------------------------------

    def get_quote(
        self,
        instrument: dict[str, Any],
    ) -> dict[str, Any]:

        if not self.is_broker_connected():

            raise MarketDataError(
                "5paisa is not connected."
            )

        exchange = instrument.get("exchange")

        exchange_type = (
            instrument.get("exchange_type")
            or instrument.get("exchangeType")
            or "D"
        )

        broker_token = (
            instrument.get("broker_token")
            or instrument.get("scrip_code")
            or instrument.get("ScripCode")
            or instrument.get("Token")
        )

        if not exchange:

            raise MarketDataError(
                "Instrument is missing exchange."
            )

        if broker_token is None:

            raise MarketDataError(
                "Instrument is missing ScripCode."
            )

        try:

            quote = broker.get_quote(
                exchange=exchange,
                exchange_type=exchange_type,
                scrip_code=int(broker_token),
            )

            return self.normalize_tick(
                quote
            )

        except Exception as exc:

            logger.exception(
                "Quote request failed."
            )

            raise MarketDataError(
                str(exc)
            ) from exc

    # ---------------------------------------------------------
    # Tick normalization
    # ---------------------------------------------------------

    @staticmethod
    def normalize_tick(
        tick: Any,
    ) -> dict[str, Any]:

        if not isinstance(tick, dict):
            tick = {}

        body = tick.get(
            "body",
            tick
        )

        if isinstance(body, dict):

            data = (
                body.get("Data")
                or body.get("data")
            )

            if isinstance(data, list) and data:

                body = data[0]

        timestamp = (
            body.get("timestamp")
            or body.get("Timestamp")
        )

        if timestamp is None:

            timestamp = datetime.now(
                timezone.utc
            ).isoformat()

        return {

            "exchange":
                body.get("exchange")
                or body.get("Exch"),

            "symbol":
                body.get("symbol")
                or body.get("Symbol")
                or body.get("ScripData"),

            "scrip_code":
                body.get("ScripCode")
                or body.get("Token"),

            "timestamp":
                timestamp,

            "ltp":
                _number(
                    body.get("ltp")
                    or body.get("LastRate")
                    or body.get("LTP")
                ),

            "open":
                _number(
                    body.get("open")
                    or body.get("Open")
                ),

            "high":
                _number(
                    body.get("high")
                    or body.get("High")
                ),

            "low":
                _number(
                    body.get("low")
                    or body.get("Low")
                ),

            "close":
                _number(
                    body.get("close")
                    or body.get("Close")
                ),

            "volume":
                _number(
                    body.get("volume")
                    or body.get("Volume")
                ),
        }

    # ---------------------------------------------------------
    # Live market data
    # ---------------------------------------------------------

    async def start(self) -> None:

        if self.running:
            return

        if not self.is_broker_connected():

            raise MarketDataError(
                "5paisa is not connected."
            )

        self.running = True

        instruments = [
            instrument
            for instrument
            in self.active_instruments.values()
            if instrument
        ]

        try:

            broker.subscribe_market_data(
                instruments
            )

        except Exception as exc:

            self.running = False

            raise MarketDataError(
                str(exc)
            ) from exc

        logger.info(
            "Market-data service started."
        )

    async def stop(self) -> None:

        if not self.running:
            return

        instruments = [
            instrument
            for instrument
            in self.active_instruments.values()
            if instrument
        ]

        try:

            broker.unsubscribe_market_data(
                instruments
            )

        finally:

            self.running = False

        logger.info(
            "Market-data service stopped."
        )

    # ---------------------------------------------------------
    # Live tick processing
    # ---------------------------------------------------------

    async def process_tick(
        self,
        tick: dict[str, Any],
    ) -> None:

        normalized = self.normalize_tick(
            tick
        )

        symbol = (
            normalized.get("symbol")
            or normalized.get("scrip_code")
        )

        if symbol:

            self.latest_ticks[
                str(symbol)
            ] = normalized

        for callback in self.tick_callbacks:

            try:

                result = callback(
                    normalized
                )

                if asyncio.iscoroutine(
                    result
                ):

                    await result

            except Exception:

                logger.exception(
                    "Tick callback failed."
                )

    # ---------------------------------------------------------
    # Callback registration
    # ---------------------------------------------------------

    def add_tick_callback(
        self,
        callback
    ) -> None:

        if callback not in self.tick_callbacks:

            self.tick_callbacks.append(
                callback
            )

    def remove_tick_callback(
        self,
        callback
    ) -> None:

        if callback in self.tick_callbacks:

            self.tick_callbacks.remove(
                callback
            )

    # ---------------------------------------------------------
    # Latest data
    # ---------------------------------------------------------

    def get_latest_tick(
        self,
        symbol: str,
    ) -> Optional[dict[str, Any]]:

        return self.latest_ticks.get(
            symbol
        )

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    def status(self) -> dict[str, Any]:

        return {

            "running":
                self.running,

            "broker_connected":
                self.is_broker_connected(),

            "active_instruments":
                self.active_instruments,

            "tracked_symbols":
                list(
                    self.latest_ticks.keys()
                ),
        }


# -------------------------------------------------------------
# Utility
# -------------------------------------------------------------

def _number(
    value: Any
) -> Optional[float]:

    if value is None:
        return None

    try:

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return None


# -------------------------------------------------------------
# Shared service instance
# -------------------------------------------------------------

market_data = MarketDataService()
