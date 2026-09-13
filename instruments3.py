from __future__ import annotations

import csv
import io
from dataclasses import dataclass, asdict
from datetime import datetime

import requests

from config.settings import settings


SCRIP_MASTER_URL = (
    "https://Openapi.5paisa.com/"
    "VendorsAPI/Service1.svc/"
    "ScripMaster/segment/all"
)


SUPPORTED_UNDERLYINGS = {
    "NIFTY": {
        "exchange": "N",
        "exchange_type": "D"
    },
    "BANKNIFTY": {
        "exchange": "N",
        "exchange_type": "D"
    },
    "SENSEX": {
        "exchange": "B",
        "exchange_type": "D"
    },
    "CRUDEOIL": {
        "exchange": "M",
        "exchange_type": "D"
    },
    "NATURALGAS": {
        "exchange": "M",
        "exchange_type": "D"
    }
}


@dataclass
class Instrument:

    underlying: str
    symbol: str
    exchange: str
    exchange_type: str
    instrument_type: str

    expiry: str | None = None
    strike: float | None = None
    option_type: str | None = None

    broker_token: int | None = None

    lot_size: int = 1
    tick_size: float = 0.05

    scrip_data: dict | None = None

    def to_dict(self):

        data = asdict(self)

        data["scrip_code"] = self.broker_token

        return data


class InstrumentManager:

    def __init__(self):

        self.instruments = []

        self.master_file = (
            settings.DATA_DIR /
            "scrip_master.csv"
        )

        self.loaded = False

        self.last_update = None

        self._load_local()

    # -------------------------------------------------
    # LOAD LOCAL MASTER
    # -------------------------------------------------

    def _load_local(self):

        if not self.master_file.exists():
            return

        try:
            with open(
                self.master_file,
                "rb"
            ) as file:

                content = file.read()

            self._load_csv(content)

        except Exception as error:

            print(
                "Instrument local load error:",
                error
            )

    # -------------------------------------------------
    # UPDATE MASTER
    # -------------------------------------------------

    def update(self):

        try:

            response = requests.get(
                SCRIP_MASTER_URL,
                timeout=30
            )

            response.raise_for_status()

            content = response.content

            self.master_file.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            with open(
                self.master_file,
                "wb"
            ) as file:

                file.write(content)

            self._load_csv(content)

            self.last_update = datetime.now()

            return True

        except Exception as error:

            print(
                "Instrument master update error:",
                error
            )

            return False

    # -------------------------------------------------
    # CSV LOAD
    # -------------------------------------------------

    def _load_csv(self, content):

        text = content.decode(
            "utf-8-sig",
            errors="ignore"
        )

        reader = csv.DictReader(
            io.StringIO(text)
        )

        rows = list(reader)

        self.instruments = []

        for row in rows:

            try:

                exchange = self._value(
                    row,
                    "Exch",
                    "Exchange"
                )

                exchange_type = self._value(
                    row,
                    "ExchType",
                    "ExchangeType"
                )

                symbol = self._value(
                    row,
                    "Name",
                    "Symbol",
                    "ScripName"
                )

                scrip_code = self._value(
                    row,
                    "ScripCode"
                )

                if not exchange or not symbol:
                    continue

                try:
                    scrip_code = int(
                        float(scrip_code)
                    )
                except Exception:
                    continue

                underlying = (
                    self._detect_underlying(
                        symbol
                    )
                )

                if not underlying:
                    continue

                scrip_type = self._value(
                    row,
                    "ScripType"
                ).upper()

                if scrip_type not in {
                    "CE",
                    "PE",
                    "XX"
                }:
                    continue

                expiry = self._normalize_expiry(
                    self._value(
                        row,
                        "Expiry",
                        "ExpiryDate"
                    )
                )

                strike = self._float_value(
                    self._value(
                        row,
                        "StrikeRate",
                        "Strike",
                        "StrikePrice"
                    )
                )

                lot_size = self._int_value(
                    self._value(
                        row,
                        "LotSize"
                    ),
                    1
                )

                tick_size = self._float_value(
                    self._value(
                        row,
                        "TickSize"
                    )
                )

                if not tick_size:
                    tick_size = 0.05

                if scrip_type == "CE":

                    instrument_type = "CALL"
                    option_type = "CE"

                elif scrip_type == "PE":

                    instrument_type = "PUT"
                    option_type = "PE"

                else:

                    instrument_type = "FUTURE"
                    option_type = None

                instrument = Instrument(
                    underlying=underlying,
                    symbol=symbol,
                    exchange=exchange,
                    exchange_type=exchange_type,
                    instrument_type=instrument_type,
                    expiry=expiry,
                    strike=strike,
                    option_type=option_type,
                    broker_token=scrip_code,
                    lot_size=lot_size,
                    tick_size=tick_size,
                    scrip_data=row
                )

                self.instruments.append(
                    instrument
                )

            except Exception:
                continue

        self.loaded = True

        print(
            f"Loaded {len(self.instruments)} instruments"
        )

    # -------------------------------------------------
    # HELPERS
    # -------------------------------------------------

    @staticmethod
    def _value(row, *keys):

        for key in keys:

            value = row.get(key)

            if value is not None:

                value = str(value).strip()

                if value:
                    return value

        return ""

    @staticmethod
    def _float_value(value):

        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _int_value(value, default=1):

        try:
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def _normalize_expiry(value):

        if not value:
            return None

        value = str(value).strip()

        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d-%b-%Y",
            "%d%b%Y",
            "%Y%m%d"
        ]

        for fmt in formats:

            try:

                date = datetime.strptime(
                    value,
                    fmt
                )

                return date.strftime(
                    "%Y-%m-%d"
                )

            except Exception:
                pass

        return value

    @staticmethod
    def _detect_underlying(symbol):

        text = str(symbol).upper()

        for underlying in (
            SUPPORTED_UNDERLYINGS
        ):

            if underlying in text:
                return underlying

        return None

    # -------------------------------------------------
    # QUERIES
    # -------------------------------------------------

    def get_futures(
        self,
        underlying,
        expiry=None
    ):

        result = [
            item
            for item in self.instruments
            if item.underlying == underlying
            and item.instrument_type == "FUTURE"
        ]

        if expiry:

            result = [
                item
                for item in result
                if item.expiry == expiry
            ]

        return result

    def get_options(
        self,
        underlying,
        expiry=None,
        option_type=None
    ):

        result = [
            item
            for item in self.instruments
            if item.underlying == underlying
            and item.instrument_type
            in {"CALL", "PUT"}
        ]

        if expiry:

            result = [
                item
                for item in result
                if item.expiry == expiry
            ]

        if option_type:

            option_type = option_type.upper()

            result = [
                item
                for item in result
                if item.option_type == option_type
            ]

        return result

    def get_expiries(
        self,
        underlying
    ):

        expiries = {
            item.expiry
            for item in self.instruments
            if item.underlying == underlying
            and item.expiry
        }

        return sorted(expiries)

    def get_strikes(
        self,
        underlying,
        expiry,
        option_type=None
    ):

        options = self.get_options(
            underlying,
            expiry,
            option_type
        )

        strikes = {
            item.strike
            for item in options
            if item.strike is not None
        }

        return sorted(strikes)

    def find_option(
        self,
        underlying,
        expiry,
        strike,
        option_type
    ):

        option_type = option_type.upper()

        for item in self.instruments:

            if (
                item.underlying == underlying
                and item.expiry == expiry
                and item.strike == float(strike)
                and item.option_type == option_type
            ):
                return item

        return None

    def find_by_token(
        self,
        token
    ):

        try:
            token = int(token)
        except Exception:
            return None

        for item in self.instruments:

            if item.broker_token == token:
                return item

        return None

    def find_by_symbol(
        self,
        symbol
    ):

        if not symbol:
            return None

        symbol = str(symbol).upper()

        for item in self.instruments:

            if item.symbol.upper() == symbol:
                return item

        return None

    def status(self):

        return {
            "loaded": self.loaded,
            "count": len(self.instruments),
            "master_file": str(
                self.master_file
            ),
            "last_update": (
                self.last_update.isoformat()
                if self.last_update
                else None
            )
        }


instrument_manager = InstrumentManager()
