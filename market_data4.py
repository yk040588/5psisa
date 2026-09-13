
from __future__ import annotations

from datetime import datetime, timedelta

from Backend.broker import broker
from Backend.instruments import instrument_manager


class MarketDataManager:

    def __init__(self):
        pass

    # -------------------------------------------------   vbvxcv
    # HISTORICAL CANDLESfddsf
    # -------------------------------------------------

    def get_candles(
        self,
        symbol: str,
        instrument_type: str,
        expiry: str | None = None,
        strike: float | None = None,
        option_type: str | None = None,
        timeframe: str = "5m"
    ):

        instrument = self._find_instrument(
            symbol=symbol,
            instrument_type=instrument_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type
        )

        if not instrument:
            return []

        end_date = datetime.now()
        start_date = (
            end_date - timedelta(days=5)
        )

        response = broker.get_historical_data(
            exchange=instrument.exchange,
            exchange_type=instrument.exchange_type,
            scrip_code=instrument.broker_token,
            interval=self._normalize_interval(
                timeframe
            ),
            from_date=start_date.strftime(
                "%Y-%m-%d"
            ),
            end_date=end_date.strftime(
                "%Y-%m-%d"
            )
        )

        return self._normalize_response(
            response
        )

    # -------------------------------------------------
    # FIND INSTRUMENT
    # -------------------------------------------------

    def _find_instrument(
        self,
        symbol,
        instrument_type,
        expiry=None,
        strike=None,
        option_type=None
    ):

        symbol = str(symbol).upper()
        instrument_type = (
            str(instrument_type).upper()
        )

        if instrument_type == "FUTURE":

            futures = (
                instrument_manager.get_futures(
                    symbol,
                    expiry
                )
            )

            return (
                futures[0]
                if futures
                else None
            )

        if instrument_type == "CALL":

            option_type = "CE"

        elif instrument_type == "PUT":

            option_type = "PE"

        else:
            option_type = (
                option_type.upper()
                if option_type
                else None
            )

        if (
            expiry is not None
            and strike is not None
            and option_type
        ):

            return (
                instrument_manager.find_option(
                    symbol,
                    expiry,
                    strike,
                    option_type
                )
            )

        options = (
            instrument_manager.get_options(
                symbol,
                expiry,
                option_type
            )
        )

        if not options:
            return None

        if strike is not None:

            options.sort(
                key=lambda item:
                abs(
                    (item.strike or 0)
                    - float(strike)
                )
            )

        return options[0]

    # -------------------------------------------------
    # NORMALIZE INTERVAL
    # -------------------------------------------------

    @staticmethod
    def _normalize_interval(
        timeframe
    ):

        mapping = {
            "1m": "1m",
            "3m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "60m",
            "4h": "60m",
            "1d": "1d"
        }

        return mapping.get(
            timeframe,
            "5m"
        )

    # -------------------------------------------------
    # NORMALIZE API RESPONSE
    # -------------------------------------------------

    def _normalize_response(
        self,
        response
    ):

        if not response:
            return []

        rows = []

        body = response.get(
            "body",
            response
        )

        if isinstance(body, dict):

            for key in (
                "Data",
                "data",
                "Candles",
                "candles"
            ):

                if isinstance(
                    body.get(key),
                    list
                ):
                    rows = body[key]
                    break

        elif isinstance(body, list):

            rows = body

        if not rows:
            return []

        candles = []

        for row in rows:

            try:

                if isinstance(row, dict):

                    timestamp = (
                        row.get("Datetime")
                        or row.get("Date")
                        or row.get("datetime")
                        or row.get("timestamp")
                    )

                    open_price = (
                        row.get("Open")
                        or row.get("open")
                    )

                    high_price = (
                        row.get("High")
                        or row.get("high")
                    )

                    low_price = (
                        row.get("Low")
                        or row.get("low")
                    )

                    close_price = (
                        row.get("Close")
                        or row.get("close")
                    )

                    volume = (
                        row.get("Volume")
                        or row.get("volume")
                        or 0
                    )

                elif isinstance(row, list):

                    if len(row) < 5:
                        continue

                    timestamp = row[0]
                    open_price = row[1]
                    high_price = row[2]
                    low_price = row[3]
                    close_price = row[4]

                    volume = (
                        row[5]
                        if len(row) > 5
                        else 0
                    )

                else:
                    continue

                candles.append(
                    {
                        "timestamp": timestamp,
                        "open": float(open_price),
                        "high": float(high_price),
                        "low": float(low_price),
                        "close": float(close_price),
                        "volume": float(volume or 0)
                    }
                )

            except Exception:
                continue

        return candles


market_data_manager = MarketDataManager()
