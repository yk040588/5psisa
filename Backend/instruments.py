from __future__ import annotations

import csv
import io
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


# ============================================================
# 5PAISA OFFICIAL SCRIP MASTER
# ============================================================

SCRIP_MASTER_URL = (
    "https://Openapi.5paisa.com/"
    "VendorsAPI/Service1.svc/"
    "ScripMaster/segment/all"
)


# ============================================================
# PHASE 1 - ONLY THESE 5 UNDERLYINGS
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


SUPPORTED_SCRIP_TYPES = {
    "CE",
    "PE",
    "XX",
}


# ============================================================
# PHASE 1 SETTINGS
# ============================================================

# Upcoming expiries shown in Phase 1
UPCOMING_EXPIRY_COUNT = 5

# Most recent expired expiries retained/shown in Phase 1
HISTORICAL_EXPIRY_COUNT = 20

# Automatic OTM selection
OTM_CALL_COUNT = 5
OTM_PUT_COUNT = 5


# ============================================================
# INSTRUMENT MODEL
# ============================================================

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

        self.loaded = False
        self.last_update: datetime | None = None

        self._token_index: dict[int, Instrument] = {}
        self._symbol_index: dict[str, Instrument] = {}

        self._load_local()

    # ========================================================
    # LOCAL LOAD
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
    # DOWNLOAD + PERMANENT MERGE
    # ========================================================

    def update(self) -> bool:

        try:
            response = requests.get(
                SCRIP_MASTER_URL,
                timeout=30,
            )

            response.raise_for_status()

            new_content = response.content

            new_instruments = self._parse_csv(
                new_content
            )

            old_instruments: list[Instrument] = []

            if self.master_file.exists():

                try:
                    with open(
                        self.master_file,
                        "rb",
                    ) as file:
                        old_content = file.read()

                    old_instruments = self._parse_csv(
                        old_content
                    )

                except Exception:
                    logger.exception(
                        "Unable to read existing scrip master"
                    )

            merged: dict[int, Instrument] = {}

            # Keep old instruments
            for instrument in old_instruments:

                if instrument.broker_token is not None:
                    merged[
                        instrument.broker_token
                    ] = instrument

            # New master data overrides old data
            for instrument in new_instruments:

                if instrument.broker_token is not None:
                    merged[
                        instrument.broker_token
                    ] = instrument

            instruments = list(
                merged.values()
            )

            instruments.sort(
                key=self._instrument_sort_key
            )

            self._write_csv(
                instruments
            )

            self._load_local()

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
    # PARSE CSV
    # ========================================================

    def _parse_csv(
        self,
        content: bytes | str,
    ) -> list[Instrument]:

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

        result: list[Instrument] = []

        seen_tokens: set[int] = set()

        for row in reader:

            try:
                instrument = self._convert_row(
                    row
                )

                if instrument is None:
                    continue

                token = instrument.broker_token

                if (
                    token is None
                    or token in seen_tokens
                ):
                    continue

                seen_tokens.add(token)

                result.append(
                    instrument
                )

            except Exception:
                continue

        return result

    # ========================================================
    # LOAD CSV
    # ========================================================

    def _load_csv(
        self,
        content: bytes | str,
    ) -> None:

        instruments = self._parse_csv(
            content
        )

        self.instruments = instruments

        self._build_indexes()

        self.loaded = True

        logger.info(
            "Loaded %s supported instruments",
            len(self.instruments),
        )

    # ========================================================
    # WRITE FILTERED MASTER
    # ========================================================

    def _write_csv(
        self,
        instruments: Iterable[Instrument],
    ) -> None:

        self.master_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fields = [
            "Exch",
            "ExchType",
            "SymbolRoot",
            "Name",
            "ScripType",
            "ScripCode",
            "Expiry",
            "StrikeRate",
            "LotSize",
            "TickSize",
        ]

        temp_file = self.master_file.with_suffix(
            ".tmp"
        )

        with open(
            temp_file,
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fields,
            )

            writer.writeheader()

            for instrument in instruments:

                if instrument.instrument_type == "CALL":
                    scrip_type = "CE"

                elif instrument.instrument_type == "PUT":
                    scrip_type = "PE"

                else:
                    scrip_type = "XX"

                writer.writerow({
                    "Exch": instrument.exchange,
                    "ExchType": instrument.exchange_type,
                    "SymbolRoot": instrument.underlying,
                    "Name": instrument.symbol,
                    "ScripType": scrip_type,
                    "ScripCode": (
                        instrument.broker_token
                        if instrument.broker_token is not None
                        else ""
                    ),
                    "Expiry": (
                        instrument.expiry
                        or ""
                    ),
                    "StrikeRate": (
                        instrument.strike
                        if instrument.strike is not None
                        else ""
                    ),
                    "LotSize": instrument.lot_size,
                    "TickSize": instrument.tick_size,
                })

        temp_file.replace(
            self.master_file
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
            symbol_root,
            symbol_upper,
        )

        if underlying is None:
            return None

        expected = SUPPORTED_UNDERLYINGS[
            underlying
        ]

        if exchange != expected["exchange"]:
            return None

        if exchange_type != expected["exchange_type"]:
            return None

        scrip_type = self._value(
            row,
            "ScripType",
        ).upper()

        if scrip_type not in SUPPORTED_SCRIP_TYPES:
            return None

        if scrip_type == "CE":

            instrument_type = "CALL"
            option_type = "CE"

        elif scrip_type == "PE":

            instrument_type = "PUT"
            option_type = "PE"

        else:

            instrument_type = "FUTURE"
            option_type = None

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

        expiry = self._normalize_expiry(
            self._value(
                row,
                "Expiry",
                "ExpiryDate",
            )
        )

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

        lot_size = self._int_value(
            self._value(
                row,
                "LotSize",
            ),
            default=1,
        )

        if not lot_size or lot_size <= 0:
            lot_size = 1

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
    # EXPIRY HELPERS
    # ========================================================

    @staticmethod
    def _expiry_to_date(
        expiry: str | None,
    ) -> date | None:

        if not expiry:
            return None

        value = str(expiry).strip()

        if not value:
            return None

        # Already normalized
        try:
            return datetime.strptime(
                value,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            pass

        # ISO datetime
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).date()
        except ValueError:
            pass

        # Common formats
        formats = (
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y%m%d",
            "%d-%b-%Y",
            "%d %b %Y",
            "%d-%B-%Y",
            "%d %B %Y",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S",
        )

        for fmt in formats:

            try:
                return datetime.strptime(
                    value,
                    fmt,
                ).date()

            except ValueError:
                continue

        return None

    # ========================================================
    # ALL EXPIRIES
    # ========================================================

    def get_expiries(
        self,
        underlying: str,
    ) -> list[str]:
        """
        Return all unique valid expiries.

        Sorted oldest -> newest.
        """

        underlying = underlying.upper()

        if underlying not in SUPPORTED_UNDERLYINGS:
            return []

        expiries: set[str] = set()

        for instrument in self.instruments:

            if instrument.underlying != underlying:
                continue

            if not instrument.expiry:
                continue

            expiry_date = self._expiry_to_date(
                instrument.expiry
            )

            if expiry_date is None:
                continue

            expiries.add(
                expiry_date.strftime(
                    "%Y-%m-%d"
                )
            )

        return sorted(
            expiries
        )

    # ========================================================
    # LATEST 5 UPCOMING EXPIRIES
    # ========================================================

    def get_upcoming_expiries(
        self,
        underlying: str,
        count: int = UPCOMING_EXPIRY_COUNT,
    ) -> list[str]:

        today = date.today()

        expiries = self.get_expiries(
            underlying
        )

        upcoming: list[str] = []

        for expiry in expiries:

            expiry_date = self._expiry_to_date(
                expiry
            )

            if (
                expiry_date is not None
                and expiry_date >= today
            ):
                upcoming.append(
                    expiry
                )

        upcoming.sort(
            key=lambda value:
                self._expiry_to_date(value)
                or date.max
        )

        return upcoming[:count]

    # ========================================================
    # LATEST 20 HISTORICAL / EXPIRED EXPIRIES
    # ========================================================

    def get_historical_expiries(
        self,
        underlying: str,
        count: int = HISTORICAL_EXPIRY_COUNT,
    ) -> list[str]:

        today = date.today()

        expiries = self.get_expiries(
            underlying
        )

        historical: list[str] = []

        for expiry in expiries:

            expiry_date = self._expiry_to_date(
                expiry
            )

            if (
                expiry_date is not None
                and expiry_date < today
            ):
                historical.append(
                    expiry
                )

        # Latest expired first
        historical.sort(
            key=lambda value:
                self._expiry_to_date(value)
                or date.min,
            reverse=True,
        )

        return historical[:count]

    # ========================================================
    # PHASE 1 EXPIRY SUMMARY
    # ========================================================

    def get_expiry_summary(
        self,
        underlying: str,
    ) -> dict:

        underlying = underlying.upper()

        if underlying not in SUPPORTED_UNDERLYINGS:
            return {
                "underlying": underlying,
                "upcoming": [],
                "historical": [],
            }

        upcoming = self.get_upcoming_expiries(
            underlying,
            UPCOMING_EXPIRY_COUNT,
        )

        historical = self.get_historical_expiries(
            underlying,
            HISTORICAL_EXPIRY_COUNT,
        )

        return {
            "underlying": underlying,
            "upcoming": upcoming,
            "historical": historical,
        }

    # ========================================================
    # GET INSTRUMENTS FOR EXPIRY
    # ========================================================

    def get_instruments_for_expiry(
        self,
        underlying: str,
        expiry: str,
        instrument_type: str | None = None,
    ) -> list[Instrument]:

        underlying = underlying.upper()

        normalized_expiry = (
            self._normalize_expiry(expiry)
        )

        if normalized_expiry is None:
            return []

        result: list[Instrument] = []

        for instrument in self.instruments:

            if instrument.underlying != underlying:
                continue

            if instrument.expiry != normalized_expiry:
                continue

            if instrument_type is not None:

                if (
                    instrument.instrument_type
                    != instrument_type.upper()
                ):
                    continue

            result.append(
                instrument
            )

        result.sort(
            key=lambda inst: (
                inst.strike
                if inst.strike is not None
                else 0.0
            )
        )

        return result

    # ========================================================
    # GET FUTURES
    # ========================================================

    def get_futures(
        self,
        underlying: str,
        expiry: str | None = None,
    ) -> list[Instrument]:

        underlying = underlying.upper()

        normalized_expiry = None

        if expiry:
            normalized_expiry = (
                self._normalize_expiry(expiry)
            )

        futures: list[Instrument] = []

        for instrument in self.instruments:

            if instrument.underlying != underlying:
                continue

            if instrument.instrument_type != "FUTURE":
                continue

            if (
                normalized_expiry is not None
                and instrument.expiry != normalized_expiry
            ):
                continue

            futures.append(
                instrument
            )

        futures.sort(
            key=lambda inst: (
                self._expiry_to_date(
                    inst.expiry
                )
                or date.max
            )
        )

        return futures

    # ========================================================
    # GET NEAREST FUTURE
    # ========================================================

    def get_nearest_future(
        self,
        underlying: str,
        expiry: str | None = None,
    ) -> Instrument | None:

        underlying = underlying.upper()

        futures = self.get_futures(
            underlying,
            expiry,
        )

        if expiry is not None:
            return (
                futures[0]
                if futures
                else None
            )

        today = date.today()

        valid_futures: list[Instrument] = []

        for instrument in futures:

            expiry_date = self._expiry_to_date(
                instrument.expiry
            )

            if expiry_date is None:
                continue

            if expiry_date < today:
                continue

            valid_futures.append(
                instrument
            )

        valid_futures.sort(
            key=lambda inst:
                self._expiry_to_date(
                    inst.expiry
                )
                or date.max
        )

        return (
            valid_futures[0]
            if valid_futures
            else None
        )

    # ========================================================
    # OTM CALLS
    # ========================================================

    def get_otm_calls(
        self,
        underlying: str,
        expiry: str,
        reference_price: float,
        count: int = OTM_CALL_COUNT,
    ) -> list[Instrument]:
        """
        OTM CALL:

            strike > reference price

        Returns nearest OTM strikes first.
        """

        try:
            reference_price = float(
                reference_price
            )
        except (
            TypeError,
            ValueError,
        ):
            return []

        if reference_price <= 0:
            return []

        calls = self.get_instruments_for_expiry(
            underlying,
            expiry,
            "CALL",
        )

        otm_calls = [
            instrument
            for instrument in calls
            if (
                instrument.strike is not None
                and instrument.strike > reference_price
            )
        ]

        otm_calls.sort(
            key=lambda instrument:
                instrument.strike - reference_price
                if instrument.strike is not None
                else float("inf")
        )

        return otm_calls[:count]

    # ========================================================
    # OTM PUTS
    # ========================================================

    def get_otm_puts(
        self,
        underlying: str,
        expiry: str,
        reference_price: float,
        count: int = OTM_PUT_COUNT,
    ) -> list[Instrument]:
        """
        OTM PUT:

            strike < reference price

        Returns nearest OTM strikes first.
        """

        try:
            reference_price = float(
                reference_price
            )
        except (
            TypeError,
            ValueError,
        ):
            return []

        if reference_price <= 0:
            return []

        puts = self.get_instruments_for_expiry(
            underlying,
            expiry,
            "PUT",
        )

        otm_puts = [
            instrument
            for instrument in puts
            if (
                instrument.strike is not None
                and instrument.strike < reference_price
            )
        ]

        otm_puts.sort(
            key=lambda instrument:
                reference_price - instrument.strike
                if instrument.strike is not None
                else float("inf")
        )

        return otm_puts[:count]

    # ========================================================
    # OTM OPTION SUMMARY
    # ========================================================

    def get_otm_options(
        self,
        underlying: str,
        expiry: str,
        reference_price: float,
        call_count: int = OTM_CALL_COUNT,
        put_count: int = OTM_PUT_COUNT,
    ) -> dict:
        """
        Phase 1 automatic OTM selection:

            5 OTM CALLS
            5 OTM PUTS

        Counts can be overridden internally,
        but Phase 1 defaults remain 5 + 5.
        """

        calls = self.get_otm_calls(
            underlying=underlying,
            expiry=expiry,
            reference_price=reference_price,
            count=call_count,
        )

        puts = self.get_otm_puts(
            underlying=underlying,
            expiry=expiry,
            reference_price=reference_price,
            count=put_count,
        )

        return {
            "underlying": underlying.upper(),
            "expiry": self._normalize_expiry(
                expiry
            ),
            "reference_price": reference_price,
            "calls": [
                instrument.to_dict()
                for instrument in calls
            ],
            "puts": [
                instrument.to_dict()
                for instrument in puts
            ],
            "call_count": len(calls),
            "put_count": len(puts),
        }

    # ========================================================
    # COMPLETE PHASE 1 CONTRACT SUMMARY
    # ========================================================

    def get_phase1_contracts(
        self,
        underlying: str,
        expiry: str | None = None,
        reference_price: float | None = None,
    ) -> dict:
        """
        Phase 1 structure:

            Selected symbol
                 ↓
            Selected expiry
                 ↓
            Future
              ↙   ↘
          5 CALL  5 PUT

        OTM contracts are selected automatically
        using the future/reference price.
        """

        underlying = underlying.upper()

        if underlying not in SUPPORTED_UNDERLYINGS:
            return {
                "underlying": underlying,
                "future": None,
                "expiry": None,
                "upcoming_expiries": [],
                "historical_expiries": [],
                "calls": [],
                "puts": [],
            }

        expiry_summary = self.get_expiry_summary(
            underlying
        )

        upcoming = expiry_summary[
            "upcoming"
        ]

        historical = expiry_summary[
            "historical"
        ]

        # Default = nearest upcoming expiry
        if expiry is None:

            expiry = (
                upcoming[0]
                if upcoming
                else None
            )

        else:

            expiry = self._normalize_expiry(
                expiry
            )

            # Keep explicitly selected historical
            # expiry if it exists in master.
            all_expiries = self.get_expiries(
                underlying
            )

            if expiry not in all_expiries:

                expiry = (
                    upcoming[0]
                    if upcoming
                    else None
                )

        future = self.get_nearest_future(
            underlying,
            expiry,
        )

        # Fallback to nearest active future
        # if selected expiry has no future.
        if future is None:

            future = self.get_nearest_future(
                underlying
            )

        calls: list[Instrument] = []
        puts: list[Instrument] = []

        if (
            expiry is not None
            and reference_price is not None
        ):

            try:
                price = float(
                    reference_price
                )
            except (
                TypeError,
                ValueError,
            ):
                price = 0.0

            if price > 0:

                calls = self.get_otm_calls(
                    underlying=underlying,
                    expiry=expiry,
                    reference_price=price,
                    count=OTM_CALL_COUNT,
                )

                puts = self.get_otm_puts(
                    underlying=underlying,
                    expiry=expiry,
                    reference_price=price,
                    count=OTM_PUT_COUNT,
                )

        return {
            "underlying": underlying,

            "future": (
                future.to_dict()
                if future is not None
                else None
            ),

            "expiry": expiry,

            "upcoming_expiries": upcoming,

            "historical_expiries": historical,

            "calls": [
                instrument.to_dict()
                for instrument in calls
            ],

            "puts": [
                instrument.to_dict()
                for instrument in puts
            ],

            "call_count": len(calls),

            "put_count": len(puts),
        }

    # ========================================================
    # VALUE HELPERS
    # ========================================================

    def _value(
        self,
        row: dict,
        *keys: str,
    ) -> str:

        for key in keys:

            if (
                key in row
                and row[key] is not None
            ):

                value = str(
                    row[key]
                ).strip()

                if value:
                    return value

        return ""

    # ========================================================
    # INTEGER HELPER
    # ========================================================

    def _int_value(
        self,
        val: str,
        default: int | None = None,
    ) -> int | None:

        try:
            return int(
                float(val)
            )

        except (
            ValueError,
            TypeError,
        ):
            return default

    # ========================================================
    # FLOAT HELPER
    # ========================================================

    def _float_value(
        self,
        val: str,
        default: float | None = None,
    ) -> float | None:

        try:
            return float(val)

        except (
            ValueError,
            TypeError,
        ):
            return default

    # ========================================================
    # EXPIRY NORMALIZATION
    # ========================================================

    def _normalize_expiry(
        self,
        expiry_str: str,
    ) -> str | None:

        if not expiry_str:
            return None

        value = str(
            expiry_str
        ).strip()

        if not value:
            return None

        expiry_date = self._expiry_to_date(
            value
        )

        if expiry_date is not None:
            return expiry_date.strftime(
                "%Y-%m-%d"
            )

        return value

    # ========================================================
    # DETECT UNDERLYING
    # ========================================================

    @staticmethod
    def _detect_underlying(
        symbol_root: str,
        symbol: str,
    ) -> str | None:

        symbol_root = (
            symbol_root or ""
        ).upper()

        symbol = (
            symbol or ""
        ).upper()

        if symbol_root in SUPPORTED_UNDERLYINGS:
            return symbol_root

        for underlying in sorted(
            SUPPORTED_UNDERLYINGS,
            key=len,
            reverse=True,
        ):

            if underlying in symbol:
                return underlying

        return None

    # ========================================================
    # SORT
    # ========================================================

    def _instrument_sort_key(
        self,
        inst: Instrument,
    ):

        expiry_date = self._expiry_to_date(
            inst.expiry
        )

        return (
            inst.underlying,

            expiry_date
            or date.max,

            inst.strike
            if inst.strike is not None
            else 0.0,

            inst.instrument_type,

            inst.broker_token
            if inst.broker_token is not None
            else 0,
        )

    # ========================================================
    # BUILD INDEXES
    # ========================================================

    def _build_indexes(self) -> None:

        self._token_index.clear()

        self._symbol_index.clear()

        for instrument in self.instruments:

            if instrument.broker_token is not None:

                self._token_index[
                    instrument.broker_token
                ] = instrument

            if instrument.symbol:

                self._symbol_index[
                    instrument.symbol.upper()
                ] = instrument


# ============================================================
# SHARED INSTRUMENT MANAGER
# ============================================================

instrument_manager = InstrumentManager()
