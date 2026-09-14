from __future__ import annotations

import csv
import io
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests

from config.settings import settings


logger = logging.getLogger(__name__)


# ============================================================
# 5PAISA XSTREAM - OFFICIAL SCRIP MASTER
# ============================================================

SCRIP_MASTER_URL = (
    "https://Openapi.5paisa.com/"
    "VendorsAPI/Service1.svc/"
    "ScripMaster/segment/all"
)


# ============================================================
# PHASE 1 SUPPORTED UNDERLYINGS
# ============================================================

SUPPORTED_UNDERLYINGS = {
    "NIFTY": {
        "exchange": "N",
        "exchange_type": "D",
    },
    "BANKNIFTY": {
        "exchange": "N",
        "exchange_type": "D",
    },
    "SENSEX": {
        "exchange": "B",
        "exchange_type": "D",
    },
    "CRUDEOIL": {
        "exchange": "M",
        "exchange_type": "D",
    },
    "NATURALGAS": {
        "exchange": "M",
        "exchange_type": "D",
    },
}


OTM_CALL_COUNT = 15
OTM_PUT_COUNT = 15


# ============================================================
# INSTRUMENT MODEL
# ============================================================

@dataclass
class Instrument:
    """
    Normalized 5paisa instrument.

    Internal instrument types:
        FUTURE
        CALL
        PUT

    Xstream subscription uses:
        exchange
        exchange_type
        broker_token / scrip_code
    """

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

    @property
    def scrip_code(self) -> int | None:
        return self.broker_token

    def to_dict(self) -> dict:
        data = asdict(self)

        data["scrip_code"] = self.broker_token

        return data


# ============================================================
# INSTRUMENT MANAGER
# ============================================================

class InstrumentManager:

    def __init__(self):
        self.instruments: list[Instrument] = []

        self.master_file: Path = (
            settings.DATA_DIR / "scrip_master.csv"
        )

        self.loaded: bool = False
        self.last_update: datetime | None = None

        self._token_index: dict[int, Instrument] = {}
        self._symbol_index: dict[str, Instrument] = {}

        self._load_local()

    # ========================================================
    # LOCAL MASTER
    # ========================================================

    def _load_local(self) -> bool:

        if not self.master_file.exists():
            logger.info(
                "Local scrip master not found: %s",
                self.master_file,
            )
            return False

        try:
            with open(
                self.master_file,
                "rb",
            ) as file:
                content = file.read()

            self._load_csv(content)

            return self.loaded

        except Exception:
            logger.exception(
                "Instrument local load error"
            )
            return False

    # ========================================================
    # DOWNLOAD / UPDATE MASTER
    # ========================================================

    def update(self) -> bool:

        try:
            response = requests.get(
                SCRIP_MASTER_URL,
                timeout=30,
            )

            response.raise_for_status()

            content = response.content

            self.master_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with open(
                self.master_file,
                "wb",
            ) as file:
                file.write(content)

            self._load_csv(content)

            self.last_update = datetime.now()

            logger.info(
                "5paisa instrument master updated: %s instruments",
                len(self.instruments),
            )

            return True

        except Exception:
            logger.exception(
                "Instrument master update error"
            )
            return False

    # ========================================================
    # CSV PARSER
    # ========================================================

    def _load_csv(self, content: bytes | str) -> None:

        if isinstance(content, bytes):
            text = content.decode(
                "utf-8-sig",
                errors="ignore",
            )
        else:
            text = str(content)

        reader = csv.DictReader(
            io.StringIO(text)
        )

        rows = list(reader)

        instruments: list[Instrument] = []

        seen_tokens: set[int] = set()

        for row in rows:

            try:
                instrument = self._convert_row(row)

                if instrument is None:
                    continue

                token = instrument.broker_token

                if token is None:
                    continue

                # Prevent duplicate ScripCodes.
                if token in seen_tokens:
                    continue

                seen_tokens.add(token)

                instruments.append(instrument)

            except Exception:
                # A malformed row must not break the complete
                # instrument master.
                continue

        self.instruments = instruments

        self._build_indexes()

        self.loaded = True

        logger.info(
            "Loaded %s supported instruments",
            len(self.instruments),
        )

    # ========================================================
    # ROW -> INSTRUMENT
    # ========================================================

    def _convert_row(
        self,
        row: dict,
    ) -> Instrument | None:

        exchange = self._value(
            row,
            "Exch",
            "Exchange",
        ).upper()

        exchange_type = self._value(
            row,
            "ExchType",
            "ExchangeType",
        ).upper()

        if not exchange or not exchange_type:
            return None

        # ----------------------------------------------------
        # SymbolRoot is preferred.
        # ----------------------------------------------------

        symbol_root = self._value(
            row,
            "SymbolRoot",
            "Underlying",
            "UnderlyingSymbol",
        ).upper()

        symbol = self._value(
            row,
            "Name",
            "Symbol",
            "ScripName",
        )

        symbol_upper = symbol.upper()

        underlying = self._detect_underlying(
            symbol_root=symbol_root,
            symbol=symbol_upper,
        )

        if underlying is None:
            return None

        expected = SUPPORTED_UNDERLYINGS[
            underlying
        ]

        # ----------------------------------------------------
        # Exact exchange validation.
        # ----------------------------------------------------

        if exchange != expected["exchange"]:
            return None

        if exchange_type != expected["exchange_type"]:
            return None

        # ----------------------------------------------------
        # Instrument classification.
        # ----------------------------------------------------

        scrip_type = self._value(
            row,
            "ScripType",
        ).upper()

        if scrip_type == "CE":

            instrument_type = "CALL"
            option_type = "CE"

        elif scrip_type == "PE":

            instrument_type = "PUT"
            option_type = "PE"

        elif scrip_type == "XX":

            instrument_type = "FUTURE"
            option_type = None

        else:
            return None

        # ----------------------------------------------------
        # Scrip code.
        # ----------------------------------------------------

        scrip_code = self._int_value(
            self._value(
                row,
                "ScripCode",
                "Token",
            ),
            default=None,
        )

        if scrip_code is None:
            return None

        # ----------------------------------------------------
        # Expiry.
        # ----------------------------------------------------

        expiry = self._normalize_expiry(
            self._value(
                row,
                "Expiry",
                "ExpiryDate",
            )
        )

        # ----------------------------------------------------
        # Strike.
        #
        # Futures generally have no useful strike.
        # ----------------------------------------------------

        strike = self._float_value(
            self._value(
                row,
                "StrikeRate",
                "Strike",
                "StrikePrice",
            )
        )

        if instrument_type == "FUTURE":
            strike = None

        # ----------------------------------------------------
        # Lot size.
        # ----------------------------------------------------

        lot_size = self._int_value(
            self._value(
                row,
                "LotSize",
            ),
            default=1,
        )

        if lot_size is None or lot_size <= 0:
            lot_size = 1

        # ----------------------------------------------------
        # Tick size.
        # ----------------------------------------------------

        tick_size = self._float_value(
            self._value(
                row,
                "TickSize",
            )
        )

        if tick_size is None or tick_size <= 0:
            tick_size = 0.05

        return Instrument(
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
            scrip_data=dict(row),
        )

    # ========================================================
    # UNDERLYING DETECTION
    # ========================================================

    @staticmethod
    def _detect_underlying(
        symbol_root: str,
        symbol: str,
    ) -> str | None:

        # First priority: official SymbolRoot.
        if symbol_root in SUPPORTED_UNDERLYINGS:
            return symbol_root

        # Fallback only when SymbolRoot is unavailable.
        text = symbol.upper()

        # Longest names first.
        for underlying in sorted(
            SUPPORTED_UNDERLYINGS,
            key=len,
            reverse=True,
        ):
            if underlying in text:
                return underlying

        return None

    # ========================================================
    # INDEXES
    # ========================================================

    def _build_indexes(self) -> None:

        self._token_index = {}
        self._symbol_index = {}

        for instrument in self.instruments:

            if instrument.broker_token is not None:
                self._token_index[
                    instrument.broker_token
                ] = instrument

            self._symbol_index[
                instrument.symbol.upper()
            ] = instrument

    # ========================================================
    # BASIC HELPERS
    # ========================================================

    @staticmethod
    def _value(
        row: dict,
        *keys: str,
    ) -> str:

        for key in keys:

            value = row.get(key)

            if value is None:
                continue

            value = str(value).strip()

            if value:
                return value

        return ""

    @staticmethod
    def _float_value(
        value,
    ) -> float | None:

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        try:
            return float(text)

        except (TypeError, ValueError):
            return None

    @staticmethod
    def _int_value(
        value,
        default: int | None = 1,
    ) -> int | None:

        if value is None:
            return default

        text = str(value).strip()

        if not text:
            return default

        try:
            return int(float(text))

        except (TypeError, ValueError):
            return default

    # ========================================================
    # EXPIRY NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_expiry(
        value,
    ) -> str | None:

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d-%b-%Y",
            "%d%b%Y",
            "%Y%m%d",
            "%d-%B-%Y",
            "%d %b %Y",
            "%d %B %Y",
        ]

        for fmt in formats:

            try:

                parsed = datetime.strptime(
                    value,
                    fmt,
                )

                return parsed.strftime(
                    "%Y-%m-%d"
                )

            except ValueError:
                continue

        return value

    # ========================================================
    # SUPPORTED SYMBOLS
    # ========================================================

    @staticmethod
    def is_supported_underlying(
        underlying: str,
    ) -> bool:

        if not underlying:
            return False

        return (
            str(underlying).upper()
            in SUPPORTED_UNDERLYINGS
        )

    # ========================================================
    # FUTURES
    # ========================================================

    def get_futures(
        self,
        underlying: str,
        expiry: str | None = None,
    ) -> list[Instrument]:

        underlying = str(
            underlying
        ).upper()

        result = [
            item
            for item in self.instruments
            if (
                item.underlying == underlying
                and item.instrument_type == "FUTURE"
            )
        ]

        if expiry:
            expiry = self._normalize_expiry(
                expiry
            )

            result = [
                item
                for item in result
                if item.expiry == expiry
            ]

        return sorted(
            result,
            key=lambda item: (
                item.expiry or "",
                item.symbol,
            ),
        )

    # ========================================================
    # OPTIONS
    # ========================================================

    def get_options(
        self,
        underlying: str,
        expiry: str | None = None,
        option_type: str | None = None,
    ) -> list[Instrument]:

        underlying = str(
            underlying
        ).upper()

        result = [
            item
            for item in self.instruments
            if (
                item.underlying == underlying
                and item.instrument_type
                in {"CALL", "PUT"}
            )
        ]

        if expiry:
            expiry = self._normalize_expiry(
                expiry
            )

            result = [
                item
                for item in result
                if item.expiry == expiry
            ]

        if option_type:

            option_type = str(
                option_type
            ).upper()

            # Accept both internal and broker naming.
            aliases = {
                "CALL": "CE",
                "PUT": "PE",
                "CE": "CE",
                "PE": "PE",
            }

            option_type = aliases.get(
                option_type,
                option_type,
            )

            result = [
                item
                for item in result
                if item.option_type == option_type
            ]

        return sorted(
            result,
            key=lambda item: (
                item.strike
                if item.strike is not None
                else float("inf"),
                item.symbol,
            ),
        )

    # ========================================================
    # EXPIRIES
    # ========================================================

    def get_expiries(
        self,
        underlying: str,
    ) -> list[str]:

        underlying = str(
            underlying
        ).upper()

        expiries = {
            item.expiry
            for item in self.instruments
            if (
                item.underlying == underlying
                and item.expiry
            )
        }

        return sorted(expiries)

    # ========================================================
    # STRIKES
    # ========================================================

    def get_strikes(
        self,
        underlying: str,
        expiry: str,
        option_type: str | None = None,
    ) -> list[float]:

        options = self.get_options(
            underlying=underlying,
            expiry=expiry,
            option_type=option_type,
        )

        strikes = {
            item.strike
            for item in options
            if item.strike is not None
        }

        return sorted(strikes)

    # ========================================================
    # FIND OPTION
    # ========================================================

    def find_option(
        self,
        underlying: str,
        expiry: str,
        strike: float,
        option_type: str,
    ) -> Instrument | None:

        underlying = str(
            underlying
        ).upper()

        expiry = self._normalize_expiry(
            expiry
        )

        option_type = str(
            option_type
        ).upper()

        aliases = {
            "CALL": "CE",
            "PUT": "PE",
        }

        option_type = aliases.get(
            option_type,
            option_type,
        )

        try:
            target_strike = float(
                strike
            )

        except (TypeError, ValueError):
            return None

        for item in self.instruments:

            if item.underlying != underlying:
                continue

            if item.expiry != expiry:
                continue

            if item.option_type != option_type:
                continue

            if item.strike is None:
                continue

            # Small floating-point tolerance.
            if abs(
                item.strike - target_strike
            ) <= 0.0001:
                return item

        return None

    # ========================================================
    # FIND BY TOKEN / SCRIP CODE
    # ========================================================

    def find_by_token(
        self,
        token,
    ) -> Instrument | None:

        token_int = self._int_value(
            token,
            default=None,
        )

        if token_int is None:
            return None

        return self._token_index.get(
            token_int
        )

    # ========================================================
    # FIND BY SYMBOL
    # ========================================================

    def find_by_symbol(
        self,
        symbol: str,
    ) -> Instrument | None:

        if not symbol:
            return None

        return self._symbol_index.get(
            str(symbol).upper()
        )

    # ========================================================
    # NEAREST FUTURE
    # ========================================================

    def get_nearest_future(
        self,
        underlying: str,
    ) -> Instrument | None:

        futures = self.get_futures(
            underlying
        )

        if not futures:
            return None

        today = datetime.now().date()

        valid = []

        for item in futures:

            if not item.expiry:
                continue

            try:
                expiry_date = datetime.strptime(
                    item.expiry,
                    "%Y-%m-%d",
                ).date()

            except ValueError:
                continue

            if expiry_date >= today:
                valid.append(
                    (expiry_date, item)
                )

        if valid:
            valid.sort(
                key=lambda pair: pair[0]
            )

            return valid[0][1]

        return futures[0]

    # ========================================================
    # OTM-15 CALLS
    #
    # Spot/Future price:
    #
    # Calls:
    #   strike > underlying price
    #
    # Select nearest 15 OTM strikes.
    # ========================================================

    def get_otm_calls(
        self,
        underlying: str,
        expiry: str,
        underlying_price: float,
        count: int = OTM_CALL_COUNT,
    ) -> list[Instrument]:

        try:
            price = float(
                underlying_price
            )

        except (TypeError, ValueError):
            return []

        if price <= 0:
            return []

        options = self.get_options(
            underlying=underlying,
            expiry=expiry,
            option_type="CE",
        )

        otm = [
            item
            for item in options
            if (
                item.strike is not None
                and item.strike > price
            )
        ]

        otm.sort(
            key=lambda item: item.strike
        )

        return otm[:max(0, int(count))]

    # ========================================================
    # OTM-15 PUTS
    #
    # Puts:
    #   strike < underlying price
    #
    # Nearest strikes below price.
    # ========================================================

    def get_otm_puts(
        self,
        underlying: str,
        expiry: str,
        underlying_price: float,
        count: int = OTM_PUT_COUNT,
    ) -> list[Instrument]:

        try:
            price = float(
                underlying_price
            )

        except (TypeError, ValueError):
            return []

        if price <= 0:
            return []

        options = self.get_options(
            underlying=underlying,
            expiry=expiry,
            option_type="PE",
        )

        otm = [
            item
            for item in options
            if (
                item.strike is not None
                and item.strike < price
            )
        ]

        # Nearest OTM puts are highest strikes below price.
        otm.sort(
            key=lambda item: item.strike,
            reverse=True,
        )

        return otm[:max(0, int(count))]

    # ========================================================
    # OTM-15 BOTH SIDES
    # ========================================================

    def get_otm_options(
        self,
        underlying: str,
        expiry: str,
        underlying_price: float,
        call_count: int = OTM_CALL_COUNT,
        put_count: int = OTM_PUT_COUNT,
    ) -> dict:

        calls = self.get_otm_calls(
            underlying=underlying,
            expiry=expiry,
            underlying_price=underlying_price,
            count=call_count,
        )

        puts = self.get_otm_puts(
            underlying=underlying,
            expiry=expiry,
            underlying_price=underlying_price,
            count=put_count,
        )

        return {
            "calls": [
                item.to_dict()
                for item in calls
            ],
            "puts": [
                item.to_dict()
                for item in puts
            ],
            "call_count": len(calls),
            "put_count": len(puts),
        }

    # ========================================================
    # XSTREAM SUBSCRIPTION DATA
    #
    # Xstream MarketFeedV3 requires:
    #   Exch
    #   ExchType
    #   ScripCode
    # ========================================================

    @staticmethod
    def to_xstream_subscription(
        instrument: Instrument,
    ) -> dict:

        return {
            "Exch": instrument.exchange,
            "ExchType": instrument.exchange_type,
            "ScripCode": instrument.broker_token,
        }

    def build_xstream_subscriptions(
        self,
        instruments: Iterable[Instrument],
    ) -> list[dict]:

        subscriptions = []

        seen = set()

        for instrument in instruments:

            token = instrument.broker_token

            if token is None:
                continue

            key = (
                instrument.exchange,
                instrument.exchange_type,
                token,
            )

            if key in seen:
                continue

            seen.add(key)

            subscriptions.append(
                self.to_xstream_subscription(
                    instrument
                )
            )

        return subscriptions

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> dict:

        counts = {
            "FUTURE": 0,
            "CALL": 0,
            "PUT": 0,
        }

        underlying_counts = {}

        for item in self.instruments:

            if item.instrument_type in counts:
                counts[
                    item.instrument_type
                ] += 1

            underlying_counts.setdefault(
                item.underlying,
                0,
            )

            underlying_counts[
                item.underlying
            ] += 1

        return {
            "loaded": self.loaded,
            "count": len(self.instruments),
            "futures": counts["FUTURE"],
            "calls": counts["CALL"],
            "puts": counts["PUT"],
            "underlyings": underlying_counts,
            "master_file": str(
                self.master_file
            ),
            "last_update": (
                self.last_update.isoformat()
                if self.last_update
                else None
            ),
        }


# ============================================================
# SINGLE SHARED INSTANCE
# ============================================================

instrument_manager = InstrumentManager()
