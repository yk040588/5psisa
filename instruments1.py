from __future__ import annotations

import csv
import io
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from config.settings import settings


SCRIP_MASTER_URL = (
    "https://Openapi.5paisa.com/VendorsAPI/Service1.svc/ScripMaster/segment/all"
)

SUPPORTED_UNDERLYINGS = {
    "NIFTY": {"exchange": "N", "exchange_type": "D"},
    "BANKNIFTY": {"exchange": "N", "exchange_type": "D"},
    "SENSEX": {"exchange": "B", "exchange_type": "D"},
    "CRUDEOIL": {"exchange": "M", "exchange_type": "D"},
    "NATURALGAS": {"exchange": "M", "exchange_type": "D"},
}


@dataclass
class Instrument:
    underlying: str
    symbol: str
    exchange: str
    exchange_type: str
    instrument_type: str
    expiry: Optional[str]
    strike: Optional[float]
    option_type: Optional[str]
    broker_token: int
    lot_size: int
    tick_size: float
    scrip_data: str

    def to_dict(self):
        data = asdict(self)
        data["scrip_code"] = self.broker_token
        return data


class InstrumentManager:

    def __init__(self):
        self.master_file = settings.DATA_DIR / "scrip_master.csv"
        self.instruments: list[Instrument] = []
        self.loaded = False

        if self.master_file.exists():
            try:
                self._load_csv()
            except Exception as exc:
                print(f"[INSTRUMENTS] Local master load failed: {exc}")

    # ---------------------------------------------------------
    # DOWNLOAD
    # ---------------------------------------------------------

    def update(self):
        print("[INSTRUMENTS] Downloading scrip master...")

        response = requests.get(
            SCRIP_MASTER_URL,
            timeout=60,
        )
        response.raise_for_status()

        self.master_file.write_bytes(response.content)

        self._load_csv()

        print(
            f"[INSTRUMENTS] Loaded {len(self.instruments)} instruments"
        )

        return self.status()

    # ---------------------------------------------------------
    # LOAD CSV
    # ---------------------------------------------------------

    def _load_csv(self):
        raw = self.master_file.read_bytes()

        text = raw.decode("utf-8-sig", errors="ignore")

        reader = csv.DictReader(io.StringIO(text))

        rows = list(reader)

        if not rows:
            raise RuntimeError("Scrip master is empty")

        headers = [str(h).strip() for h in reader.fieldnames or []]

        def find_key(*names):
            lower_map = {
                h.lower().replace(" ", "").replace("_", ""): h
                for h in headers
            }

            for name in names:
                key = name.lower().replace(" ", "").replace("_", "")
                if key in lower_map:
                    return lower_map[key]

            return None

        exchange_key = find_key("Exch", "Exchange")
        exchange_type_key = find_key("ExchType", "ExchangeType")
        name_key = find_key("Name", "Symbol", "ScripName")
        scrip_code_key = find_key("ScripCode", "ScripCode")
        expiry_key = find_key("Expiry", "ExpiryDate")
        strike_key = find_key("StrikeRate", "Strike", "StrikePrice")
        scrip_type_key = find_key("ScripType")
        lot_key = find_key("LotSize")
        tick_key = find_key("TickSize", "TickSize")
        scrip_data_key = find_key("ScripData")

        parsed = []

        for row in rows:
            try:
                exchange = str(row.get(exchange_key, "")).strip()
                exchange_type = str(row.get(exchange_type_key, "")).strip()

                name = str(row.get(name_key, "")).strip()

                if not name:
                    continue

                scrip_type = str(row.get(scrip_type_key, "")).strip().upper()

                if scrip_type not in {"CE", "PE", "XX"}:
                    continue

                underlying = self._detect_underlying(name)

                if not underlying:
                    continue

                instrument_type = {
                    "CE": "CALL",
                    "PE": "PUT",
                    "XX": "FUTURE",
                }[scrip_type]

                scrip_code = int(float(row.get(scrip_code_key, 0) or 0))

                if scrip_code <= 0:
                    continue

                expiry = self._normalize_expiry(
                    row.get(expiry_key)
                )

                strike = None

                if instrument_type in {"CALL", "PUT"}:
                    try:
                        strike = float(row.get(strike_key, 0) or 0)
                    except Exception:
                        strike = None

                try:
                    lot_size = int(float(row.get(lot_key, 1) or 1))
                except Exception:
                    lot_size = 1

                try:
                    tick_size = float(row.get(tick_key, 0.05) or 0.05)
                except Exception:
                    tick_size = 0.05

                scrip_data = str(
                    row.get(scrip_data_key, "")
                ).strip()

                parsed.append(
                    Instrument(
                        underlying=underlying,
                        symbol=name,
                        exchange=exchange,
                        exchange_type=exchange_type,
                        instrument_type=instrument_type,
                        expiry=expiry,
                        strike=strike,
                        option_type=(
                            "CALL"
                            if instrument_type == "CALL"
                            else "PUT"
                            if instrument_type == "PUT"
                            else None
                        ),
                        broker_token=scrip_code,
                        lot_size=lot_size,
                        tick_size=tick_size,
                        scrip_data=scrip_data,
                    )
                )

            except Exception:
                continue

        self.instruments = parsed
        self.loaded = True

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _detect_underlying(name: str):

        upper = name.upper()

        for underlying in SUPPORTED_UNDERLYINGS:
            if underlying in upper:
                return underlying

        return None

    @staticmethod
    def _normalize_expiry(value):

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y%m%d",
            "%d %b %Y",
            "%d %B %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).strftime(
                    "%Y-%m-%d"
                )
            except Exception:
                pass

        return text

    # ---------------------------------------------------------
    # FUTURES
    # ---------------------------------------------------------

    def get_futures(
        self,
        underlying: str,
        expiry: Optional[str] = None,
    ):

        underlying = underlying.upper()

        result = [
            x
            for x in self.instruments
            if x.underlying == underlying
            and x.instrument_type == "FUTURE"
        ]

        if expiry:
            result = [
                x
                for x in result
                if x.expiry == expiry
            ]

        result.sort(
            key=lambda x: (
                x.expiry or "",
                x.symbol,
            )
        )

        return result

    # ---------------------------------------------------------
    # OPTIONS
    # ---------------------------------------------------------

    def get_options(
        self,
        underlying: str,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
    ):

        underlying = underlying.upper()

        result = [
            x
            for x in self.instruments
            if x.underlying == underlying
            and x.instrument_type in {"CALL", "PUT"}
        ]

        if expiry:
            result = [
                x for x in result
                if x.expiry == expiry
            ]

        if option_type:
            result = [
                x for x in result
                if x.instrument_type == option_type.upper()
            ]

        result.sort(
            key=lambda x: (
                x.strike if x.strike is not None else 0
            )
        )

        return result

    # ---------------------------------------------------------
    # EXPIRIES
    # ---------------------------------------------------------

    def get_expiries(self, underlying: str):

        values = set()

        for x in self.instruments:
            if (
                x.underlying == underlying.upper()
                and x.expiry
            ):
                values.add(x.expiry)

        return sorted(values)

    # ---------------------------------------------------------
    # STRIKES
    # ---------------------------------------------------------

    def get_strikes(
        self,
        underlying: str,
        expiry: str,
        option_type: Optional[str] = None,
    ):

        options = self.get_options(
            underlying=underlying,
            expiry=expiry,
            option_type=option_type,
        )

        return sorted(
            {
                x.strike
                for x in options
                if x.strike is not None
            }
        )

    # ---------------------------------------------------------
    # FIND OPTION
    # ---------------------------------------------------------

    def find_option(
        self,
        underlying: str,
        expiry: str,
        strike: float,
        option_type: str,
    ):

        option_type = option_type.upper()

        candidates = self.get_options(
            underlying=underlying,
            expiry=expiry,
            option_type=option_type,
        )

        for instrument in candidates:

            if instrument.strike is None:
                continue

            if abs(float(instrument.strike) - float(strike)) < 0.001:
                return instrument

        return None

    # ---------------------------------------------------------
    # TOKEN
    # ---------------------------------------------------------

    def find_by_token(self, token: int):

        for instrument in self.instruments:
            if instrument.broker_token == int(token):
                return instrument

        return None

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def status(self):

        counts = {}

        for x in self.instruments:
            key = f"{x.underlying}_{x.instrument_type}"
            counts[key] = counts.get(key, 0) + 1

        return {
            "loaded": self.loaded,
            "total": len(self.instruments),
            "file": str(self.master_file),
            "counts": counts,
        }


instrument_manager = InstrumentManager()
