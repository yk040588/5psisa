from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from Backend.broker import broker
from Backend.instruments import instrument_manager
from config.settings import settings


SUPPORTED_INTERVALS = {
    "1m",
    "5m",
    "10m",
    "15m",
    "30m",
    "60m",
    "1d",
}

OPTION_HISTORY_DAYS = 35
FUTURE_HISTORY_DAYS = 30


class MarketDataManager:

    def __init__(self):

        self.data_dir = (
            settings.HISTORICAL_DIR
        )

        self.data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ---------------------------------------------------------
    # INSTRUMENT
    # ---------------------------------------------------------

    def get_instrument(
        self,
        symbol: str,
        instrument_type: str,
        expiry: Optional[str] = None,
        strike: Optional[float] = None,
        option_type: Optional[str] = None,
    ):

        symbol = symbol.upper()
        instrument_type = instrument_type.upper()

        if instrument_type == "FUTURE":

            futures = instrument_manager.get_futures(
                symbol,
                expiry=expiry,
            )

            if not futures:
                raise ValueError(
                    f"No future found for {symbol}"
                )

            return futures[0]

        if instrument_type in {"CALL", "PUT"}:

            if not expiry:
                raise ValueError(
                    "Expiry is required for option"
                )

            if strike is None:
                raise ValueError(
                    "Strike is required for option"
                )

            instrument = instrument_manager.find_option(
                underlying=symbol,
                expiry=expiry,
                strike=float(strike),
                option_type=option_type or instrument_type,
            )

            if not instrument:
                raise ValueError(
                    f"Option not found: "
                    f"{symbol} {expiry} {strike} "
                    f"{option_type or instrument_type}"
                )

            return instrument

        raise ValueError(
            f"Unsupported instrument type: {instrument_type}"
        )

    # ---------------------------------------------------------
    # DATES
    # ---------------------------------------------------------

    def _effective_dates(
        self,
        instrument_type: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ):

        today = date.today()

        days = (
            OPTION_HISTORY_DAYS
            if instrument_type.upper() in {"CALL", "PUT"}
            else FUTURE_HISTORY_DAYS
        )

        default_start = today - timedelta(days=days)

        if end_date:
            end = datetime.strptime(
                end_date,
                "%Y-%m-%d",
            ).date()
        else:
            end = today

        if start_date:
            start = datetime.strptime(
                start_date,
                "%Y-%m-%d",
            ).date()
        else:
            start = default_start

        minimum = end - timedelta(days=days)

        if start < minimum:
            start = minimum

        return (
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

    # ---------------------------------------------------------
    # NORMALIZE
    # ---------------------------------------------------------

    def normalize_candles(self, raw):

        if raw is None:
            return []

        data = raw

        if isinstance(raw, dict):

            body = raw.get("body")

            if isinstance(body, dict):
                data = (
                    body.get("Data")
                    or body.get("data")
                    or body.get("Candles")
                    or body.get("candles")
                    or []
                )

            elif isinstance(body, list):
                data = body

            else:
                data = (
                    raw.get("Data")
                    or raw.get("data")
                    or raw.get("Candles")
                    or raw.get("candles")
                    or []
                )

        if not isinstance(data, list):
            return []

        result = []

        for item in data:

            try:

                if isinstance(item, dict):

                    timestamp = (
                        item.get("timestamp")
                        or item.get("Timestamp")
                        or item.get("Datetime")
                        or item.get("DateTime")
                        or item.get("date")
                        or item.get("Date")
                    )

                    open_price = (
                        item.get("open")
                        or item.get("Open")
                    )

                    high_price = (
                        item.get("high")
                        or item.get("High")
                    )

                    low_price = (
                        item.get("low")
                        or item.get("Low")
                    )

                    close_price = (
                        item.get("close")
                        or item.get("Close")
                    )

                    volume = (
                        item.get("volume")
                        or item.get("Volume")
                        or 0
                    )

                elif isinstance(item, list):

                    if len(item) < 5:
                        continue

                    timestamp = item[0]
                    open_price = item[1]
                    high_price = item[2]
                    low_price = item[3]
                    close_price = item[4]
                    volume = item[5] if len(item) > 5 else 0

                else:
                    continue

                if timestamp is None:
                    continue

                result.append(
                    {
                        "timestamp": str(timestamp),
                        "open": float(open_price),
                        "high": float(high_price),
                        "low": float(low_price),
                        "close": float(close_price),
                        "volume": float(volume),
                    }
                )

            except Exception:
                continue

        result.sort(
            key=lambda x: x["timestamp"]
        )

        return result

    # ---------------------------------------------------------
    # FILE
    # ---------------------------------------------------------

    def get_file_path(
        self,
        symbol,
        instrument_type,
        scrip_code,
        interval,
    ):

        filename = (
            f"{symbol.upper()}_"
            f"{instrument_type.upper()}_"
            f"{scrip_code}_"
            f"{interval}.json"
        )

        return self.data_dir / filename

    def save_candles(
        self,
        path: Path,
        candles,
    ):

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                candles,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_local_candles(
        self,
        path: Path,
    ):

        if not path.exists():
            return []

        try:
            return json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return []

    # ---------------------------------------------------------
    # FETCH
    # ---------------------------------------------------------

    def fetch_historical(
        self,
        instrument,
        interval,
        start_date,
        end_date,
    ):

        raw = broker.get_historical_data(
            exchange=instrument.exchange,
            exchange_type=instrument.exchange_type,
            scrip_code=instrument.broker_token,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )

        candles = self.normalize_candles(raw)

        return candles

    # ---------------------------------------------------------
    # GET
    # ---------------------------------------------------------

    def get_candles(
        self,
        symbol,
        instrument_type,
        interval,
        start_date=None,
        end_date=None,
        expiry=None,
        strike=None,
        option_type=None,
        refresh=False,
    ):

        interval = interval.lower()

        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(
                f"Unsupported interval {interval}"
            )

        instrument = self.get_instrument(
            symbol=symbol,
            instrument_type=instrument_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )

        start_date, end_date = (
            self._effective_dates(
                instrument_type,
                start_date,
                end_date,
            )
        )

        path = self.get_file_path(
            symbol,
            instrument_type,
            instrument.broker_token,
            interval,
        )

        if not refresh:

            local = self.load_local_candles(path)

            if local:
                return {
                    "candles": local,
                    "source": "local",
                    "instrument": instrument.to_dict(),
                }

        candles = self.fetch_historical(
            instrument,
            interval,
            start_date,
            end_date,
        )

        self.save_candles(
            path,
            candles,
        )

        return {
            "candles": candles,
            "source": "5paisa",
            "instrument": instrument.to_dict(),
        }

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def status(self):

        files = list(
            self.data_dir.glob("*.json")
        )

        return {
            "directory": str(self.data_dir),
            "files": len(files),
            "intervals": sorted(
                SUPPORTED_INTERVALS
            ),
            "option_history_days": OPTION_HISTORY_DAYS,
            "future_history_days": FUTURE_HISTORY_DAYS,
        }


market_data_manager = MarketDataManager()
