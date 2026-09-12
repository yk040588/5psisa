"""
instruments.py

Instrument management for the trading dashboard.

Supported underlyings:
    NIFTY
    BANKNIFTY
    SENSEX
    CRUDEOIL
    NATURALGAS

The actual broker scrip/instrument IDs should come from the
5paisa/Xstream instrument master.
"""

from dataclasses import dataclass, asdict
from typing import Optional


# ============================================================
# Supported Underlyings
# ============================================================

SUPPORTED_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS",
]


# ============================================================
# Instrument Types
# ============================================================

INSTRUMENT_TYPES = {
    "future",
    "option",
}


# ============================================================
# Option Types
# ============================================================

OPTION_TYPES = {
    "CE",
    "PE",
}


# ============================================================
# Instrument Data Model
# ============================================================

@dataclass
class Instrument:
    """
    Standard instrument representation used by our application.
    """

    underlying: str

    symbol: str

    exchange: str

    instrument_type: str

    expiry: Optional[str] = None

    strike: Optional[float] = None

    option_type: Optional[str] = None

    broker_token: Optional[str] = None

    lot_size: Optional[int] = None

    tick_size: Optional[float] = None

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def validate(self) -> None:

        if self.underlying not in SUPPORTED_SYMBOLS:
            raise ValueError(
                f"Unsupported underlying: {self.underlying}"
            )

        if self.instrument_type not in INSTRUMENT_TYPES:
            raise ValueError(
                f"Invalid instrument type: "
                f"{self.instrument_type}"
            )

        if self.instrument_type == "option":

            if self.option_type not in OPTION_TYPES:
                raise ValueError(
                    "Option must be CE or PE."
                )

            if self.strike is None:
                raise ValueError(
                    "Option must have a strike."
                )

        if self.instrument_type == "future":

            if self.option_type is not None:
                raise ValueError(
                    "Future cannot have CE/PE."
                )

    # --------------------------------------------------------
    # Dictionary representation
    # --------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
# Symbol Information
# ============================================================

SYMBOL_CONFIG = {

    "NIFTY": {
        "category": "index",
        "exchange": "NSE",
    },

    "BANKNIFTY": {
        "category": "index",
        "exchange": "NSE",
    },

    "SENSEX": {
        "category": "index",
        "exchange": "BSE",
    },

    "CRUDEOIL": {
        "category": "commodity",
        "exchange": "MCX",
    },

    "NATURALGAS": {
        "category": "commodity",
        "exchange": "MCX",
    },
}


# ============================================================
# Instrument Manager
# ============================================================

class InstrumentManager:
    """
    Handles instrument information received from the broker.

    The broker instrument master will eventually populate
    self.instruments.
    """

    def __init__(self):

        self.instruments: list[Instrument] = []

    # --------------------------------------------------------
    # Supported symbols
    # --------------------------------------------------------

    @staticmethod
    def get_supported_symbols() -> list[str]:

        return SUPPORTED_SYMBOLS.copy()

    # --------------------------------------------------------
    # Symbol configuration
    # --------------------------------------------------------

    @staticmethod
    def get_symbol_config(
        symbol: str,
    ) -> dict:

        symbol = symbol.upper()

        if symbol not in SYMBOL_CONFIG:
            raise ValueError(
                f"Unsupported symbol: {symbol}"
            )

        return SYMBOL_CONFIG[symbol].copy()

    # --------------------------------------------------------
    # Add instrument
    # --------------------------------------------------------

    def add_instrument(
        self,
        instrument: Instrument,
    ) -> None:

        instrument.validate()

        self.instruments.append(instrument)

    # --------------------------------------------------------
    # Load broker instrument master
    # --------------------------------------------------------

    def load_instruments(
        self,
        broker_instruments: list[dict],
    ) -> int:
        """
        Convert broker instrument-master records into our
        standard Instrument objects.

        The exact field mapping will be finalized against
        the current Xstream instrument-master format.
        """

        self.instruments.clear()

        for item in broker_instruments:

            underlying = (
                item.get("underlying")
                or item.get("Underlying")
            )

            if underlying not in SUPPORTED_SYMBOLS:
                continue

            instrument_type = (
                item.get("instrument_type")
                or item.get("InstrumentType")
            )

            # Normalize broker naming.
            if instrument_type:
                instrument_type = instrument_type.lower()

            if instrument_type not in INSTRUMENT_TYPES:
                continue

            option_type = (
                item.get("option_type")
                or item.get("OptionType")
            )

            if option_type:
                option_type = option_type.upper()

            instrument = Instrument(
                underlying=underlying,
                symbol=(
                    item.get("symbol")
                    or item.get("Symbol")
                    or ""
                ),
                exchange=(
                    item.get("exchange")
                    or item.get("Exchange")
                    or SYMBOL_CONFIG[
                        underlying
                    ]["exchange"]
                ),
                instrument_type=instrument_type,
                expiry=(
                    item.get("expiry")
                    or item.get("Expiry")
                ),
                strike=_to_float(
                    item.get("strike")
                    or item.get("Strike")
                ),
                option_type=option_type,
                broker_token=(
                    item.get("broker_token")
                    or item.get("Token")
                    or item.get("ScripCode")
                ),
                lot_size=_to_int(
                    item.get("lot_size")
                    or item.get("LotSize")
                ),
                tick_size=_to_float(
                    item.get("tick_size")
                    or item.get("TickSize")
                ),
            )

            try:
                instrument.validate()
                self.instruments.append(instrument)
            except ValueError:
                continue

        return len(self.instruments)

    # --------------------------------------------------------
    # Futures
    # --------------------------------------------------------

    def get_futures(
        self,
        underlying: str,
        expiry: Optional[str] = None,
    ) -> list[Instrument]:

        underlying = underlying.upper()

        results = [
            instrument
            for instrument in self.instruments
            if instrument.underlying == underlying
            and instrument.instrument_type == "future"
        ]

        if expiry is not None:

            results = [
                instrument
                for instrument in results
                if instrument.expiry == expiry
            ]

        return results

    # --------------------------------------------------------
    # Options
    # --------------------------------------------------------

    def get_options(
        self,
        underlying: str,
        expiry: Optional[str] = None,
        option_type: Optional[str] = None,
    ) -> list[Instrument]:

        underlying = underlying.upper()

        results = [
            instrument
            for instrument in self.instruments
            if instrument.underlying == underlying
            and instrument.instrument_type == "option"
        ]

        if expiry is not None:

            results = [
                instrument
                for instrument in results
                if instrument.expiry == expiry
            ]

        if option_type is not None:

            option_type = option_type.upper()

            results = [
                instrument
                for instrument in results
                if instrument.option_type == option_type
            ]

        return results

    # --------------------------------------------------------
    # Expiries
    # --------------------------------------------------------

    def get_expiries(
        self,
        underlying: str,
    ) -> list[str]:

        instruments = [
            instrument
            for instrument in self.instruments
            if instrument.underlying == underlying
            and instrument.expiry
        ]

        expiries = {
            instrument.expiry
            for instrument in instruments
        }

        return sorted(expiries)

    # --------------------------------------------------------
    # Strikes
    # --------------------------------------------------------

    def get_strikes(
        self,
        underlying: str,
        expiry: str,
        option_type: Optional[str] = None,
    ) -> list[float]:

        options = self.get_options(
            underlying=underlying,
            expiry=expiry,
            option_type=option_type,
        )

        strikes = {
            instrument.strike
            for instrument in options
            if instrument.strike is not None
        }

        return sorted(strikes)

    # --------------------------------------------------------
    # Find exact option
    # --------------------------------------------------------

    def find_option(
        self,
        underlying: str,
        expiry: str,
        strike: float,
        option_type: str,
    ) -> Optional[Instrument]:

        options = self.get_options(
            underlying=underlying,
            expiry=expiry,
            option_type=option_type,
        )

        for option in options:

            if option.strike == strike:
                return option

        return None

    # --------------------------------------------------------
    # Find instrument by broker token
    # --------------------------------------------------------

    def find_by_token(
        self,
        broker_token: str,
    ) -> Optional[Instrument]:

        for instrument in self.instruments:

            if str(instrument.broker_token) == str(
                broker_token
            ):
                return instrument

        return None

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    def status(self) -> dict:

        return {
            "supported_symbols": len(
                SUPPORTED_SYMBOLS
            ),
            "loaded_instruments": len(
                self.instruments
            ),
        }


# ============================================================
# Utility functions
# ============================================================

def _to_float(value):

    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _to_int(value):

    if value is None:
        return None

    try:
        return int(value)

    except (TypeError, ValueError):
        return None


# ============================================================
# Shared instance
# ============================================================

instrument_manager = InstrumentManager()
