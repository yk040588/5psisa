import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from Backend.broker import broker
from Backend.instruments import instrument_manager
from config.settings import settings


logger = logging.getLogger(__name__)


class MarketDataManager:

    def __init__(self):

        self.data_dir = (
            settings.DATA_DIR / "historical"
        )

        self.data_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.latest_ticks = {}

    # =====================================================
    # BROKER STATUS
    # =====================================================

    def is_broker_connected(self):

        return broker.connected

    # =====================================================
    # GET INSTRUMENT
    # =====================================================

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

        instrument_manager.ensure_loaded()

        # -------------------------------------------------
        # FUTURE
        # -------------------------------------------------

        if instrument_type == "FUTURE":

            futures = (
                instrument_manager
                .get_futures(symbol)
            )

            if expiry:

                futures = [
                    x
                    for x in futures
                    if x.expiry == expiry
                ]

            if not futures:
                return None

            # Nearest expiry if not specified
            futures.sort(
                key=lambda x:
                x.expiry or ""
            )

            return futures[0]

        # -------------------------------------------------
        # CALL / PUT
        # -------------------------------------------------

        if instrument_type in [
            "CALL",
            "PUT"
        ]:

            option_type_value = (
                "CE"
                if instrument_type == "CALL"
                else "PE"
            )

            options = (
                instrument_manager
                .get_options(
                    symbol,
                    option_type_value,
                    expiry,
                )
            )

            if strike is not None:

                options = [
                    x
                    for x in options
                    if x.strike is not None
                    and float(x.strike)
                    == float(strike)
                ]

            if not options:
                return None

            options.sort(
                key=lambda x:
                (
                    x.strike
                    if x.strike is not None
                    else 0
                )
            )

            return options[0]

        return None

    # =====================================================
    # NORMALIZE CANDLES
    # =====================================================

    def normalize_candles(
        self,
        response: Any
    ) -> List[Dict[str, Any]]:

        candles = []

        if not response:
            return candles

        # -------------------------------------------------
        # 5PAISA RESPONSE
        # -------------------------------------------------

        if isinstance(response, dict):

            data = response.get(
                "data",
                {}
            )

            if isinstance(data, dict):

                candles_data = (
                    data.get("candles", [])
                )

            else:

                candles_data = []

            # Some responses may directly contain candles
            if not candles_data:

                candles_data = (
                    response.get(
                        "candles",
                        []
                    )
                )

        elif isinstance(response, list):

            candles_data = response

        else:

            candles_data = []

        # -------------------------------------------------
        # CONVERT EACH CANDLE
        # -------------------------------------------------

        for candle in candles_data:

            if not isinstance(
                candle,
                dict
            ):
                continue

            timestamp = (
                candle.get("Timestamp")
                or candle.get("timestamp")
                or candle.get("Time")
                or candle.get("time")
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

            if timestamp is None:
                continue

            if (
                open_price is None
                or high_price is None
                or low_price is None
                or close_price is None
            ):
                continue

            try:

                candles.append({

                    "timestamp":
                        str(timestamp),

                    "open":
                        float(open_price),

                    "high":
                        float(high_price),

                    "low":
                        float(low_price),

                    "close":
                        float(close_price),

                    "volume":
                        int(float(volume)),
                })

            except (
                ValueError,
                TypeError
            ):

                continue

        return candles

    # =====================================================
    # LOCAL FILE NAME
    # =====================================================

    def get_file_path(
        self,
        instrument,
        interval: str
    ):

        safe_symbol = (
            instrument.underlying
        )

        safe_type = (
            instrument.instrument_type
        )

        scrip_code = (
            instrument.broker_token
        )

        filename = (
            f"{safe_symbol}_"
            f"{safe_type}_"
            f"{scrip_code}_"
            f"{interval}.json"
        )

        return (
            self.data_dir / filename
        )

    # =====================================================
    # SAVE CANDLES
    # =====================================================

    def save_candles(
        self,
        instrument,
        interval: str,
        candles: List[Dict[str, Any]]
    ):

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

                "scrip_data":
                    instrument.scrip_data,
            },

            "interval":
                interval,

            "updated_at":
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

        return file_path

    # =====================================================
    # LOAD LOCAL CANDLES
    # =====================================================

    def load_local_candles(
        self,
        instrument,
        interval: str
    ):

        file_path = self.get_file_path(
            instrument,
            interval
        )

        if not file_path.exists():
            return []

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            return data.get(
                "candles",
                []
            )

        except Exception as e:

            logger.error(
                "Unable to load local candles: %s",
                e
            )

            return []

    # =====================================================
    # FETCH HISTORICAL DATA
    # =====================================================

    def fetch_historical(
        self,
        symbol: str,
        instrument_type: str,
        interval: str,
        start_date: str,
        end_date: str,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
        strike: Optional[float] = None,
    ):

        if not broker.connected:

            raise RuntimeError(
                "5paisa is not connected. "
                "Please login first."
            )

        instrument = self.get_instrument(

            symbol=symbol,

            instrument_type=
                instrument_type,

            expiry=expiry,

            option_type=option_type,

            strike=strike,
        )

        if instrument is None:

            raise ValueError(
                "Instrument not found."
            )

        if not instrument.broker_token:

            raise ValueError(
                "Instrument does not have "
                "a valid 5paisa ScripCode."
            )

        # -------------------------------------------------
        # 5PAISA HISTORICAL API
        # -------------------------------------------------

        response = (
            broker.get_historical_data(

                exchange=
                    instrument.exchange,

                exchange_type=
                    "D",

                scrip_code=
                    instrument.broker_token,

                interval=
                    interval,

                start_date=
                    start_date,

                end_date=
                    end_date,
            )
        )

        candles = (
            self.normalize_candles(
                response
            )
        )

        # -------------------------------------------------
        # SAVE LOCALLY
        # -------------------------------------------------

        file_path = (
            self.save_candles(
                instrument,
                interval,
                candles
            )
        )

        return {

            "status":
                "success",

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

                "scrip_data":
                    instrument.scrip_data,
            },

            "interval":
                interval,

            "start_date":
                start_date,

            "end_date":
                end_date,

            "candle_count":
                len(candles),

            "file":
                str(file_path),

            "candles":
                candles,
        }

    # =====================================================
    # GET LOCAL OR FETCH
    # =====================================================

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

            instrument_type=
                instrument_type,

            expiry=expiry,

            option_type=option_type,

            strike=strike,
        )

        if instrument is None:

            raise ValueError(
                "Instrument not found."
            )

        # -------------------------------------------------
        # LOCAL DATA
        # -------------------------------------------------

        if not refresh:

            local_candles = (
                self.load_local_candles(
                    instrument,
                    interval
                )
            )

            if local_candles:

                return {

                    "status":
                        "local",

                    "instrument": {

                        "underlying":
                            instrument.underlying,

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
                    },

                    "interval":
                        interval,

                    "candle_count":
                        len(local_candles),

                    "candles":
                        local_candles,
                }

        # -------------------------------------------------
        # DEFAULT DATES
        # -------------------------------------------------

        if not end_date:

            end_date = (
                datetime.now()
                .strftime("%Y-%m-%d")
            )

        if not start_date:

            start_date = (
                (
                    datetime.now()
                    - timedelta(days=30)
                )
                .strftime("%Y-%m-%d")
            )

        # -------------------------------------------------
        # FETCH FROM BROKER
        # -------------------------------------------------

        return self.fetch_historical(

            symbol=symbol,

            instrument_type=
                instrument_type,

            interval=interval,

            start_date=start_date,

            end_date=end_date,

            expiry=expiry,

            option_type=option_type,

            strike=strike,
        )

    # =====================================================
    # STATUS
    # =====================================================

    def status(self):

        files = list(
            self.data_dir.glob(
                "*.json"
            )
        )

        return {

            "broker_connected":
                broker.connected,

            "local_data_directory":
                str(self.data_dir),

            "local_files":
                len(files),
        }


market_data_manager = (
    MarketDataManager()
)
