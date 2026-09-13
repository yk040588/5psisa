from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from Backend.broker import broker


class MarketDataManager:

    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.last_update: Optional[datetime] = None

    # ---------------------------------------------------------dvs
    # STATUSdasasdasdasdasdd
    # ---------------------------------------------------------dsfsdfdsfdf

    def status(self) -> Dict[str, Any]:
        return {
            "connected": bool(broker.access_token),
            "token_available": bool(broker.access_token),
            "last_update": (
                self.last_update.isoformat()
                if self.last_update
                else None
            ),
            "cached_symbols": list(self.cache.keys()),
        }

    # ---------------------------------------------------------
    # QUOTE
    # ---------------------------------------------------------

    def get_quote(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
    ):

        data = broker.get_quote(
            exchange=exchange,
            exchange_type=exchange_type,
            scrip_code=scrip_code,
        )

        self.last_update = datetime.now()

        return data

    # ---------------------------------------------------------
    # SAFE QUOTE
    # ---------------------------------------------------------

    def get_quote_safe(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
    ):

        try:

            data = self.get_quote(
                exchange=exchange,
                exchange_type=exchange_type,
                scrip_code=scrip_code,
            )

            return {
                "success": True,
                "data": data,
                "error": None,
            }

        except Exception as exc:

            return {
                "success": False,
                "data": None,
                "error": str(exc),
            }

    # ---------------------------------------------------------
    # HISTORICAL DATA
    # ---------------------------------------------------------

    def get_historical_data(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        interval: str = "5m",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):

        if not end_date:
            end_date = datetime.now().strftime(
                "%Y-%m-%d"
            )

        if not start_date:

            start = datetime.now() - timedelta(
                days=7
            )

            start_date = start.strftime(
                "%Y-%m-%d"
            )

        data = broker.get_historical_data(
            exchange=exchange,
            exchange_type=exchange_type,
            scrip_code=scrip_code,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )

        self.last_update = datetime.now()

        return data

    # ---------------------------------------------------------
    # SAFE HISTORICAL DATA
    # ---------------------------------------------------------

    def get_historical_data_safe(
        self,
        exchange: str,
        exchange_type: str,
        scrip_code: int,
        interval: str = "5m",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):

        try:

            data = self.get_historical_data(
                exchange=exchange,
                exchange_type=exchange_type,
                scrip_code=scrip_code,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            return {
                "success": True,
                "data": data,
                "error": None,
            }

        except Exception as exc:

            return {
                "success": False,
                "data": None,
                "error": str(exc),
            }

    # ---------------------------------------------------------
    # MARKET FEED
    # ---------------------------------------------------------

    def get_market_feed(
        self,
        instruments: List[Dict[str, Any]],
    ):

        data = broker.get_market_feed(
            instruments
        )

        self.last_update = datetime.now()

        return data

    # ---------------------------------------------------------
    # CACHE
    # ---------------------------------------------------------

    def set_cache(
        self,
        key: str,
        value: Any,
    ):

        self.cache[key] = {
            "data": value,
            "updated_at": datetime.now().isoformat(),
        }

        self.last_update = datetime.now()

    def get_cache(
        self,
        key: str,
    ):

        item = self.cache.get(key)

        if not item:
            return None

        return item.get("data")

    def clear_cache(self):

        self.cache.clear()

    # ---------------------------------------------------------
    # SYMBOL DATA
    # ---------------------------------------------------------

    def update_symbol(
        self,
        symbol: str,
        data: Any,
    ):

        self.set_cache(
            symbol,
            data,
        )

    def get_symbol(
        self,
        symbol: str,
    ):

        return self.get_cache(symbol)

    # ---------------------------------------------------------
    # LAST UPDATE
    # ---------------------------------------------------------

    def get_last_update(self):

        if not self.last_update:
            return None

        return self.last_update.isoformat()


# -------------------------------------------------------------
# GLOBAL MANAGER
# -------------------------------------------------------------

market_data_manager = MarketDataManager()
