import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class Instrument:
    underlying: str
    symbol: str
    exchange: str
    instrument_type: str
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None
    broker_token: Optional[int] = None
    lot_size: Optional[int] = None
    tick_size: Optional[float] = None
    scrip_data: Optional[str] = None


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


class InstrumentManager:

    SCRIP_MASTER_URL = (
        "https://Openapi.5paisa.com/"
        "VendorsAPI/Service1.svc/"
        "ScripMaster/segment/all"
    )

    def __init__(self):

        self.instruments: List[Instrument] = []

        self.data_dir = settings.DATA_DIR

        self.scrip_master_file = (
            self.data_dir / "scrip_master.csv"
        )

        self.last_updated = None

    # ---------------------------------------------------------
    # DOWNLOAD SCRIP MASTER
    # ---------------------------------------------------------

    def download_scrip_master(self):

        logger.info(
            "Downloading 5paisa Scrip Master..."
        )

        response = requests.get(
            self.SCRIP_MASTER_URL,
            timeout=120,
        )

        response.raise_for_status()

        self.scrip_master_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            self.scrip_master_file,
            "wb"
        ) as file:
            file.write(response.content)

        self.last_updated = datetime.now()

        logger.info(
            "5paisa Scrip Master downloaded: %s",
            self.scrip_master_file
        )

        return {
            "status": "ok",
            "file": str(
                self.scrip_master_file
            ),
            "size": len(response.content),
        }

    # ---------------------------------------------------------
    # LOAD SCRIP MASTER
    # ---------------------------------------------------------

    def load_scrip_master(self):

        if not self.scrip_master_file.exists():

            logger.info(
                "Scrip Master not found locally. "
                "Downloading..."
            )

            self.download_scrip_master()

        logger.info(
            "Loading local Scrip Master..."
        )

        self.instruments.clear()

        with open(
            self.scrip_master_file,
            "r",
            encoding="utf-8-sig",
            errors="ignore",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                try:
                    instrument = self._convert_row(row)

                    if instrument:
                        self.instruments.append(
                            instrument
                        )

                except Exception as e:

                    logger.debug(
                        "Skipping invalid row: %s",
                        e
                    )

        logger.info(
            "Loaded %s instruments.",
            len(self.instruments)
        )

        return len(self.instruments)

    # ---------------------------------------------------------
    # CONVERT CSV ROW
    # ---------------------------------------------------------

    def _convert_row(self, row):

        exchange = (
            row.get("Exch")
            or ""
        ).strip().upper()

        exchange_type = (
            row.get("ExchType")
            or ""
        ).strip().upper()

        symbol_root = (
            row.get("SymbolRoot")
            or ""
        ).strip().upper()

        scrip_type = (
            row.get("ScripType")
            or ""
        ).strip().upper()

        scrip_data = (
            row.get("ScripData")
            or ""
        ).strip()

        if not symbol_root:
            return None

        if symbol_root not in SUPPORTED_UNDERLYINGS:
            return None

        config = SUPPORTED_UNDERLYINGS[
            symbol_root
        ]

        if exchange != config["exchange"]:
            return None

        if exchange_type != config["exchange_type"]:
            return None

        # -----------------------------------------------------
        # Determine instrument type
        # -----------------------------------------------------

        if scrip_type == "CE":
            instrument_type = "CALL"

        elif scrip_type == "PE":
            instrument_type = "PUT"

        elif scrip_type == "XX":
            instrument_type = "FUTURE"

        else:
            return None

        # -----------------------------------------------------
        # Expiry
        # -----------------------------------------------------

        expiry_raw = (
            row.get("Expiry")
            or ""
        ).strip()

        expiry = self._normalize_expiry(
            expiry_raw
        )

        # -----------------------------------------------------
        # Strike
        # -----------------------------------------------------

        strike = None

        strike_raw = (
            row.get("StrikeRate")
            or ""
        ).strip()

        if strike_raw:

            try:
                strike = float(
                    strike_raw
                )

            except ValueError:
                strike = None

        # -----------------------------------------------------
        # Scrip Code
        # -----------------------------------------------------

        scrip_code = None

        scrip_code_raw = (
            row.get("ScripCode")
            or ""
        ).strip()

        if scrip_code_raw:

            try:
                scrip_code = int(
                    float(scrip_code_raw)
                )

            except ValueError:
                return None

        # -----------------------------------------------------
        # Lot size
        # -----------------------------------------------------

        lot_size = None

        lot_raw = (
            row.get("LotSize")
            or ""
        ).strip()

        if lot_raw:

            try:
                lot_size = int(
                    float(lot_raw)
                )

            except ValueError:
                pass

        # -----------------------------------------------------
        # Tick size
        # -----------------------------------------------------

        tick_size = None

        tick_raw = (
            row.get("TickSize")
            or ""
        ).strip()

        if tick_raw:

            try:
                tick_size = float(
                    tick_raw
                )

            except ValueError:
                pass

        return Instrument(
            underlying=symbol_root,
            symbol=(
                row.get("Name")
                or symbol_root
            ).strip(),

            exchange=exchange,

            instrument_type=
                instrument_type,

            expiry=expiry,

            strike=strike,

            option_type=(
                scrip_type
                if scrip_type in ["CE", "PE"]
                else None
            ),

            broker_token=scrip_code,

            lot_size=lot_size,

            tick_size=tick_size,

            scrip_data=scrip_data,
        )

    # ---------------------------------------------------------
    # EXPIRY NORMALIZATION
    # ---------------------------------------------------------

    def _normalize_expiry(
        self,
        value: str
    ):

        if not value:
            return None

        value = value.strip()

        # Example:
        # 20260430
        if len(value) == 8 and value.isdigit():

            try:

                dt = datetime.strptime(
                    value,
                    "%Y%m%d"
                )

                return dt.strftime(
                    "%Y-%m-%d"
                )

            except ValueError:
                pass

        # Example:
        # 2026-04-30
        try:

            dt = datetime.strptime(
                value[:10],
                "%Y-%m-%d"
            )

            return dt.strftime(
                "%Y-%m-%d"
            )

        except ValueError:
            pass

        return value

    # ---------------------------------------------------------
    # ENSURE LOADED
    # ---------------------------------------------------------

    def ensure_loaded(self):

        if not self.instruments:
            self.load_scrip_master()

    # ---------------------------------------------------------
    # UPDATE MASTER
    # ---------------------------------------------------------

    def update(self):

        self.download_scrip_master()

        return self.load_scrip_master()

    # ---------------------------------------------------------
    # FUTURES
    # ---------------------------------------------------------

    def get_futures(
        self,
        underlying: str
    ) -> List[Instrument]:

        self.ensure_loaded()

        underlying = underlying.upper()

        return [
            x
            for x in self.instruments
            if x.underlying == underlying
            and x.instrument_type == "FUTURE"
        ]

    # ---------------------------------------------------------
    # OPTIONS
    # ---------------------------------------------------------

    def get_options(
        self,
        underlying: str,
        option_type: Optional[str] = None,
        expiry: Optional[str] = None,
    ) -> List[Instrument]:

        self.ensure_loaded()

        underlying = underlying.upper()

        result = [
            x
            for x in self.instruments
            if x.underlying == underlying
            and x.instrument_type in [
                "CALL",
                "PUT"
            ]
        ]

        if option_type:

            option_type = option_type.upper()

            result = [
                x
                for x in result
                if x.option_type ==
                option_type
            ]

        if expiry:

            result = [
                x
                for x in result
                if x.expiry ==
                expiry
            ]

        return result

    # ---------------------------------------------------------
    # EXPIRIES
    # ---------------------------------------------------------

    def get_expiries(
        self,
        underlying: str
    ):

        self.ensure_loaded()

        expiries = set()

        for instrument in self.instruments:

            if (
                instrument.underlying
                == underlying.upper()
                and instrument.expiry
            ):

                expiries.add(
                    instrument.expiry
                )

        return sorted(expiries)

    # ---------------------------------------------------------
    # STRIKES
    # ---------------------------------------------------------

    def get_strikes(
        self,
        underlying: str,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
    ):

        options = self.get_options(
            underlying,
            option_type,
            expiry,
        )

        strikes = set()

        for instrument in options:

            if instrument.strike is not None:

                strikes.add(
                    instrument.strike
                )

        return sorted(strikes)

    # ---------------------------------------------------------
    # FIND OPTION
    # ---------------------------------------------------------

    def find_option(
        self,
        underlying: str,
        expiry: str,
        option_type: str,
        strike: float,
    ):

        options = self.get_options(
            underlying,
            option_type,
            expiry,
        )

        for instrument in options:

            if instrument.strike == float(
                strike
            ):
                return instrument

        return None

    # ---------------------------------------------------------
    # FIND BY TOKEN
    # ---------------------------------------------------------

    def find_by_token(
        self,
        broker_token: int
    ):

        self.ensure_loaded()

        for instrument in self.instruments:

            if (
                instrument.broker_token
                == int(broker_token)
            ):
                return instrument

        return None

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def status(self):

        self.ensure_loaded()

        counts = {}

        for instrument in self.instruments:

            key = (
                instrument.underlying,
                instrument.instrument_type
            )

            counts[key] = (
                counts.get(key, 0) + 1
            )

        return {
            "loaded": True,
            "total": len(
                self.instruments
            ),
            "file": str(
                self.scrip_master_file
            ),
            "counts": {
                f"{k[0]}_{k[1]}": v
                for k, v in counts.items()
            }
        }


instrument_manager = InstrumentManager()
