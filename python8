import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from Backend.broker import broker
from Backend.instruments import instrument_manager
from config.settings import settings


logger = logging.getLogger(__name__)


class MarketDataManager:

    # 5paisa supported historical intervals
    SUPPORTED_INTERVALS = {
        "1m",
        "5m",
        "10m",
        "15m",
        "30m",
        "60m",
        "1d",
    }

    # Options CALL/PUT historical data limit
    OPTION_HISTORY_DAYS = 35

    # Default historical range for futures
    FUTURE_HISTORY_DAYS = 30

    def __init__(self):

        self.data_dir = (
            settings.DATA_DIR / "historical"
        )

        self.data_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    # ---------------------------------------------------------
    # Instrument
    # ---------------------------------------------------------

    def get_instrument(
        self,
        symbol: str,
        instrument_type: str,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
        strike: Optional[float] = None,
    ):

        symbol = symbol.upper()
        instrument_type = instrument_type.upper()

        if instrument_type == "FUTURE":

            futures = instrument_manager.get_futures(
                symbol
            )

            if not futures:
                raise ValueError(
                    f"No futures found for {symbol}"
                )

            # If expiry supplied, use exact expiry
            if expiry:

                expiry = str(expiry)

                for instrument in futures:

                    if str(
                        instrument.expiry
                    ) == expiry:

                        return instrument

                raise ValueError(
                    f"No future found for "
                    f"{symbol} expiry {expiry}"
                )

            # Otherwise nearest expiry
            today = date.today()

            valid = []

            for instrument in futures:

                try:
                    instrument_expiry = (
                        datetime.strptime(
                            str(instrument.expiry),
                            "%Y-%m-%d"
                        ).date()
                    )

                    if instrument_expiry >= today:
                        valid.append(
                            (
                                instrument_expiry,
                                instrument
                            )
                        )

                except Exception:
                    continue

            if valid:

                valid.sort(
                    key=lambda x: x[0]
                )

                return valid[0][1]

            # fallback
            return futures[0]

        if instrument_type in {
            "CALL",
            "PUT",
            "OPTION",
        }:

            if instrument_type == "OPTION":

                if not option_type:
                    raise ValueError(
                        "option_type is required "
                        "for OPTION."
                    )

                instrument_type = (
                    option_type.upper()
                )

            if instrument_type not in {
                "CALL",
                "PUT",
            }:

                raise ValueError(
                    "Option type must be CALL or PUT."
                )

            if not expiry:
                raise ValueError(
                    "expiry is required "
                    "for option data."
                )

            if strike is None:
                raise ValueError(
                    "strike is required "
                    "for option data."
                )

            instrument = (
                instrument_manager.find_option(
                    symbol,
                    expiry,
                    float(strike),
                    instrument_type
                )
            )

            if not instrument:
                raise ValueError(
                    f"Option not found: "
                    f"{symbol} {expiry} "
                    f"{instrument_type} {strike}"
                )

            return instrument

        raise ValueError(
            f"Unsupported instrument type: "
            f"{instrument_type}"
        )

    # ---------------------------------------------------------
    # Date handling
    # ---------------------------------------------------------

    def _parse_date(
        self,
        value: Optional[str]
    ) -> Optional[date]:

        if not value:
            return None

        if isinstance(value, date):
            return value

        value = str(value)

        return datetime.strptime(
            value[:10],
            "%Y-%m-%d"
        ).date()

    def _format_date(
        self,
        value: date
    ) -> str:

        return value.strftime(
            "%Y-%m-%d"
        )

    def _get_effective_dates(
        self,
        instrument_type: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ):

        instrument_type = (
            instrument_type.upper()
        )

        today = date.today()

        requested_end = (
            self._parse_date(end_date)
            if end_date
            else today
        )

        if requested_end > today:
            requested_end = today

        requested_start = (
            self._parse_date(start_date)
            if start_date
            else None
        )

        # -----------------------------------------------------
        # OPTIONS = maximum 35 calendar days
        # -----------------------------------------------------

        if instrument_type in {
            "CALL",
            "PUT",
            "OPTION",
        }:

            minimum_allowed = (
                requested_end
                - timedelta(
                    days=self.OPTION_HISTORY_DAYS
                )
            )

            if (
                requested_start is None
                or requested_start < minimum_allowed
            ):

                requested_start = (
                    minimum_allowed
                )

        # -----------------------------------------------------
        # FUTURE
        # -----------------------------------------------------

        elif instrument_type == "FUTURE":

            if requested_start is None:

                requested_start = (
                    requested_end
                    - timedelta(
                        days=self.FUTURE_HISTORY_DAYS
                    )
                )

        else:

            raise ValueError(
                f"Unsupported instrument type: "
                f"{instrument_type}"
            )

        if requested_start > requested_end:

            raise ValueError(
                "start_date cannot be after "
                "end_date."
            )

        return (
            requested_start,
            requested_end
        )

    # ---------------------------------------------------------
    # Candle normalization
    # ---------------------------------------------------------

    def normalize_candles(
        self,
        response: Any
    ) -> List[Dict[str, Any]]:

        candles = []

        # 5paisa response:
        #
        # {
        #   "status": "success",
        #   "data": {
        #       "candles": [
        #           [
        #               timestamp,
        #               open,
        #               high,
        #               low,
        #               close,
        #               volume
        #           ]
        #       ]
        #   }
        # }

        if isinstance(response, dict):

            data = response.get(
                "data"
            )

            if isinstance(data, dict):

                candles = data.get(
                    "candles",
                    []
                )

            elif isinstance(data, list):

                candles = data

            if not candles:

                body = response.get(
                    "body"
                )

                if isinstance(body, dict):

                    data = body.get(
                        "Data"
                    )

                    if isinstance(data, list):
                        candles = data

        elif isinstance(response, list):

            candles = response

        normalized = []

        for candle in candles:

            try:

                if isinstance(candle, dict):

                    timestamp = (
                        candle.get("Timestamp")
                        or candle.get("timestamp")
                        or candle.get("TimeStamp")
                    )

                    open_price = (
                        candle.get("Open")
                        or candle.get("open")
                    )

                    high_price = (
                        candle.get("High")
                        or candle.get("high")
                    )

                    low_price = (
                        candle.get("Low")
                        or candle.get("low")
                    )

                    close_price = (
                        candle.get("Close")
                        or candle.get("close")
                    )

                    volume = (
                        candle.get("Volume")
                        or candle.get("volume")
                        or 0
                    )

                elif isinstance(candle, list):

                    if len(candle) < 5:
                        continue

                    timestamp = candle[0]
                    open_price = candle[1]
                    high_price = candle[2]
                    low_price = candle[3]
                    close_price = candle[4]

                    volume = (
                        candle[5]
                        if len(candle) > 5
                        else 0
                    )

                else:
                    continue

                if timestamp is None:
                    continue

                if (
                    open_price is None
                    or high_price is None
                    or low_price is None
                    or close_price is None
                ):
                    continue

                normalized.append(
                    {
                        "timestamp": str(
                            timestamp
                        ),
                        "open": float(
                            open_price
                        ),
                        "high": float(
                            high_price
                        ),
                        "low": float(
                            low_price
                        ),
                        "close": float(
                            close_price
                        ),
                        "volume": int(
                            float(volume or 0)
                        ),
                    }
                )

            except Exception as error:

                logger.warning(
                    "Unable to normalize candle: %s",
                    error
                )

        normalized.sort(
            key=lambda x: x["timestamp"]
        )

        return normalized

    # ---------------------------------------------------------
    # File path
    # ---------------------------------------------------------

    def get_file_path(
        self,
        instrument,
        interval: str
    ) -> Path:

        symbol = (
            instrument.underlying
            .upper()
        )

        instrument_type = (
            instrument.instrument_type
            .upper()
        )

        scrip_code = int(
            instrument.broker_token
        )

        filename = (
            f"{symbol}_"
            f"{instrument_type}_"
            f"{scrip_code}_"
            f"{interval}.json"
        )

        return (
            self.data_dir / filename
        )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    def save_candles(
        self,
        instrument,
        interval: str,
        candles: List[Dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> Path:

        file_path = self.get_file_path(
            instrument,
            interval
        )

        payload = {

            "instrument": {

                "underlying":
                    instrument.underlying,

                "symbol":
                    instrument.symbol,

                "exchange":
                    instrument.exchange,

                "instrument_type":
                    instrument.instrument_type,

                "expiry":
                    instrument.expiry,

                "strike":
                    instrument.strike,

                "option_type":
                    instrument.option_type,

                "scrip_code":
                    instrument.broker_token,

                "lot_size":
                    instrument.lot_size,

                "tick_size":
                    instrument.tick_size,

                "scrip_data":
                    instrument.scrip_data,
            },

            "interval": interval,

            "requested_start_date":
                start_date,

            "requested_end_date":
                end_date,

            "saved_at":
                datetime.now().isoformat(),

            "candles":
                candles,
        }

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                payload,
                file,
                indent=2
            )

        logger.info(
            "Historical data saved: %s",
            file_path
        )

        return file_path

    # ---------------------------------------------------------
    # Load local
    # ---------------------------------------------------------

    def load_local_candles(
        self,
        instrument,
        interval: str,
    ):

        file_path = self.get_file_path(
            instrument,
            interval
        )

        if not file_path.exists():
            return None

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as file:

                payload = json.load(file)

            candles = payload.get(
                "candles",
                []
            )

            # Keep options limited to 35 days
            if instrument.instrument_type in {
                "CALL",
                "PUT",
            }:

                candles = (
                    self._filter_option_candles(
                        candles
                    )
                )

                payload["candles"] = (
                    candles
                )

            return payload

        except Exception as error:

            logger.error(
                "Unable to load local candles: %s",
                error
            )

            return None

    # ---------------------------------------------------------
    # Option candle filter
    # ---------------------------------------------------------

    def _filter_option_candles(
        self,
        candles: List[Dict[str, Any]]
    ):

        minimum_date = (
            date.today()
            - timedelta(
                days=self.OPTION_HISTORY_DAYS
            )
        )

        filtered = []

        for candle in candles:

            try:

                timestamp = str(
                    candle["timestamp"]
                )

                candle_date = (
                    datetime.fromisoformat(
                        timestamp[:19]
                    ).date()
                )

                if candle_date >= minimum_date:

                    filtered.append(
                        candle
                    )

            except Exception:

                # Keep malformed timestamp
                # out of option history.
                continue

        return filtered

    # ---------------------------------------------------------
    # Historical download
    # ---------------------------------------------------------

    def fetch_historical(
        self,
        symbol: str,
        instrument_type: str,
        interval: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
        strike: Optional[float] = None,
    ):

        symbol = symbol.upper()
        instrument_type = (
            instrument_type.upper()
        )
        interval = interval.lower()

        if interval not in self.SUPPORTED_INTERVALS:

            raise ValueError(
                f"Unsupported interval "
                f"{interval}. "
                f"Supported: "
                f"{sorted(self.SUPPORTED_INTERVALS)}"
            )

        instrument = self.get_instrument(
            symbol=symbol,
            instrument_type=instrument_type,
            expiry=expiry,
            option_type=option_type,
            strike=strike,
        )

        effective_start, effective_end = (
            self._get_effective_dates(
                instrument_type=instrument_type,
                start_date=start_date,
                end_date=end_date,
            )
        )

        start_text = self._format_date(
            effective_start
        )

        end_text = self._format_date(
            effective_end
        )

        logger.info(
            "Downloading historical data: "
            "%s %s %s %s -> %s",
            symbol,
            instrument.instrument_type,
            instrument.broker_token,
            start_text,
            end_text,
        )

        response = (
            broker.get_historical_data(
                exchange=instrument.exchange,
                exchange_type="D",
                scrip_code=int(
                    instrument.broker_token
                ),
                interval=interval,
                start_date=start_text,
                end_date=end_text,
            )
        )

        candles = (
            self.normalize_candles(
                response
            )
        )

        if instrument.instrument_type in {
            "CALL",
            "PUT",
        }:

            candles = (
                self._filter_option_candles(
                    candles
                )
            )

        file_path = (
            self.save_candles(
                instrument=instrument,
                interval=interval,
                candles=candles,
                start_date=start_text,
                end_date=end_text,
            )
        )

        return {

            "success": True,

            "symbol": symbol,

            "instrument_type":
                instrument.instrument_type,

            "scrip_code":
                int(instrument.broker_token),

            "exchange":
                instrument.exchange,

            "exchange_type":
                "D",

            "expiry":
                instrument.expiry,

            "strike":
                instrument.strike,

            "option_type":
                instrument.option_type,

            "interval":
                interval,

            "start_date":
                start_text,

            "end_date":
                end_text,

            "history_days":
                (
                    self.OPTION_HISTORY_DAYS
                    if instrument.instrument_type
                    in {"CALL", "PUT"}
                    else self.FUTURE_HISTORY_DAYS
                ),

            "candle_count":
                len(candles),

            "file":
                str(file_path),

            "candles":
                candles,
        }

    # ---------------------------------------------------------
    # Get candles
    # ---------------------------------------------------------

    def get_candles(
        self,
        symbol: str,
        instrument_type: str,
        interval: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
        strike: Optional[float] = None,
        refresh: bool = False,
    ):

        instrument = self.get_instrument(
            symbol=symbol,
            instrument_type=instrument_type,
            expiry=expiry,
            option_type=option_type,
            strike=strike,
        )

        # Use local data unless refresh requested
        if not refresh:

            local = (
                self.load_local_candles(
                    instrument,
                    interval
                )
            )

            if local:

                return {
                    "success": True,
                    "source": "local",
                    **local,
                }

        # Download from 5paisa
        return self.fetch_historical(
            symbol=symbol,
            instrument_type=instrument_type,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            expiry=expiry,
            option_type=option_type,
            strike=strike,
        )

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    def status(self):

        files = list(
            self.data_dir.glob(
                "*.json"
            )
        )

        total_size = 0

        for file_path in files:

            try:
                total_size += (
                    file_path.stat().st_size
                )
            except Exception:
                pass

        return {

            "data_directory":
                str(self.data_dir),

            "file_count":
                len(files),

            "total_size_bytes":
                total_size,

            "option_history_days":
                self.OPTION_HISTORY_DAYS,

            "future_default_history_days":
                self.FUTURE_HISTORY_DAYS,

            "supported_intervals":
                sorted(
                    self.SUPPORTED_INTERVALS
                ),
        }


market_data_manager = (
    MarketDataManager()
)
