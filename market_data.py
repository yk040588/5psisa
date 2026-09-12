"""
market_data.py

Market-data service for the trading dashboard.

Responsibilities:
    - Get quotes from broker.py
    - Get historical candles
    - Track Future / Call / Put subscriptions
    - Normalize broker data into one format
    - Forward live ticks to the WebSocket layer

Broker-specific API calls stay inside broker.py.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .broker import broker, BrokerError

logger = logging.getLogger(__name__)


class MarketDataError(Exception):
    """Raised when market-data processing fails."""
    pass


class MarketDataService:
    """Central market-data service."""

    def __init__(self):
        self.running = False

        # Instruments currently displayed by the website.
        self.active_instruments: dict[str, dict[str, Any]] = {
            "future": {},
            "call": {},
            "put": {},
        }

        # Latest tick for each instrument.
        self.latest_ticks: dict[str, dict[str, Any]] = {}

        # Registered callbacks for live ticks.
        self.tick_callbacks = []

    # ---------------------------------------------------------
    # Instrument selection
    # ---------------------------------------------------------

    def set_instrument(
        self,
        chart_type: str,
        instrument: dict[str, Any],
    ) -> None:
        """
        Set the instrument displayed on one of the three charts.

        chart_type:
            future
            call
            put
        """

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

    def get_active_instruments(self) -> dict[str, dict[str, Any]]:
        """Return Future, Call and Put instruments."""

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
        """
        Get historical OHLCV candles for a chart.

        The broker layer handles the actual 5paisa/Xstream request.
        """

        exchange = instrument.get("exchange")
        symbol = instrument.get("symbol")

        if not exchange or not symbol:
            raise MarketDataError(
                "Instrument must contain exchange and symbol."
            )

        try:
            raw_data = broker.get_historical_data(
                exchange=exchange,
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            return self.normalize_candles(raw_data)

        except BrokerError as exc:
            logger.exception("Historical-data request failed.")
            raise MarketDataError(str(exc)) from exc

    # ---------------------------------------------------------
    # Candle normalization
    # ---------------------------------------------------------

    @staticmethod
    def normalize_candles(
        candles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Convert broker candle data into the format expected
        by the frontend/chart engine.
        """

        normalized = []

        for candle in candles:
            normalized.append({
                "time": candle.get(
                    "time",
                    candle.get("timestamp")
                ),
                "open": _number(candle.get("open")),
                "high": _number(candle.get("high")),
                "low": _number(candle.get("low")),
                "close": _number(candle.get("close")),
                "volume": _number(candle.get("volume")),
            })

        return normalized

    # ---------------------------------------------------------
    # Quote
    # ---------------------------------------------------------

    def get_quote(
        self,
        instrument: dict[str, Any],
    ) -> dict[str, Any]:
        """Get the latest quote for an instrument."""

        exchange = instrument.get("exchange")
        symbol = instrument.get("symbol")

        if not exchange or not symbol:
            raise MarketDataError(
                "Instrument must contain exchange and symbol."
            )

        try:
            quote = broker.get_quote(
                exchange=exchange,
                symbol=symbol,
            )

            return self.normalize_tick(quote)

        except BrokerError as exc:
            logger.exception("Quote request failed.")
            raise MarketDataError(str(exc)) from exc

    # ---------------------------------------------------------
    # Tick normalization
    # ---------------------------------------------------------

    @staticmethod
    def normalize_tick(
        tick: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize one live quote/tick.
        """

        timestamp = tick.get("timestamp")

        if timestamp is None:
            timestamp = datetime.now(
                timezone.utc
            ).isoformat()

        return {
            "exchange": tick.get("exchange"),
            "symbol": tick.get("symbol"),
            "timestamp": timestamp,
            "ltp": _number(tick.get("ltp")),
            "open": _number(tick.get("open")),
            "high": _number(tick.get("high")),
            "low": _number(tick.get("low")),
            "close": _number(tick.get("close")),
            "volume": _number(tick.get("volume")),
        }

    # ---------------------------------------------------------
    # Live market data
    # ---------------------------------------------------------

    async def start(self) -> None:
        """
        Start the market-data service.

        The actual Xstream WebSocket feed will be connected
        through broker.py.
        """

        if self.running:
            return

        if not broker.is_connected():
            raise MarketDataError(
                "Broker is not connected."
            )

        self.running = True

        instruments = [
            instrument
            for instrument in self.active_instruments.values()
            if instrument
        ]

        await broker.subscribe_market_data(
            instruments
        )

        logger.info("Market-data service started.")

    async def stop(self) -> None:
        """Stop live market-data subscriptions."""

        if not self.running:
            return

        instruments = [
            instrument
            for instrument in self.active_instruments.values()
            if instrument
        ]

        await broker.unsubscribe_market_data(
            instruments
        )

        self.running = False

        logger.info("Market-data service stopped.")

    # ---------------------------------------------------------
    # Live tick processing
    # ---------------------------------------------------------

    async def process_tick(
        self,
        tick: dict[str, Any],
    ) -> None:
        """
        Process a live broker tick.

        Later this will be called directly by the Xstream
        WebSocket listener.
        """

        normalized = self.normalize_tick(tick)

        symbol = normalized.get("symbol")

        if symbol:
            self.latest_ticks[symbol] = normalized

        for callback in self.tick_callbacks:
            try:
                result = callback(normalized)

                if asyncio.iscoroutine(result):
                    await result

            except Exception:
                logger.exception(
                    "Tick callback failed."
                )

    # ---------------------------------------------------------
    # Callback registration
    # ---------------------------------------------------------

    def add_tick_callback(self, callback) -> None:
        """Register a function to receive live ticks."""

        if callback not in self.tick_callbacks:
            self.tick_callbacks.append(callback)

    def remove_tick_callback(self, callback) -> None:
        """Remove a live-tick callback."""

        if callback in self.tick_callbacks:
            self.tick_callbacks.remove(callback)

    # ---------------------------------------------------------
    # Latest data
    # ---------------------------------------------------------

    def get_latest_tick(
        self,
        symbol: str,
    ) -> Optional[dict[str, Any]]:
        """Return the most recent tick for a symbol."""

        return self.latest_ticks.get(symbol)

    def status(self) -> dict[str, Any]:
        """Return market-data service status."""

        return {
            "running": self.running,
            "active_instruments": self.active_instruments,
            "tracked_symbols": list(
                self.latest_ticks.keys()
            ),
        }


# -------------------------------------------------------------
# Utility
# -------------------------------------------------------------

def _number(value: Any) -> Optional[float]:
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# -------------------------------------------------------------
# Shared service instance
# -------------------------------------------------------------

market_data = MarketDataService()
