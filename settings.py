```python
"""
Application configuration for Trading Dashboard.

All sensitive broker credentials should be stored in the .env file.
Never hard-code API keys, passwords, encryption keys, or user credentials
in this file.
"""

from pathlib import Path
import os

from dotenv import load_dotenv


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"

BACKEND_DIR = BASE_DIR / "backend"

FRONTEND_DIR = BASE_DIR / "frontend"

DATA_DIR = BASE_DIR / "data"


# Load .env from project root
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


# ============================================================
# APPLICATION
# ============================================================

APP_NAME = os.getenv(
    "APP_NAME",
    "Trading Dashboard"
)

APP_ENV = os.getenv(
    "APP_ENV",
    "development"
)

DEBUG = os.getenv(
    "DEBUG",
    "true"
).lower() in {
    "1",
    "true",
    "yes",
    "on"
}

HOST = os.getenv(
    "HOST",
    "127.0.0.1"
)

PORT = int(
    os.getenv(
        "PORT",
        "8000"
    )
)


# ============================================================
# SUPPORTED MASTER SYMBOLS
# ============================================================

SUPPORTED_SYMBOLS = (
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS",
)


# ============================================================
# DEFAULT DASHBOARD SETTINGS
# ============================================================

DEFAULT_SYMBOL = os.getenv(
    "DEFAULT_SYMBOL",
    "NIFTY"
)

DEFAULT_TIMEFRAME = os.getenv(
    "DEFAULT_TIMEFRAME",
    "5m"
)


SUPPORTED_TIMEFRAMES = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
    "1d",
)


# ============================================================
# OPTION SETTINGS
# ============================================================

# Number of OTM Call contracts shown in the Call dropdown.
OTM_CALL_COUNT = int(
    os.getenv(
        "OTM_CALL_COUNT",
        "5"
    )
)


# Number of OTM Put contracts shown in the Put dropdown.
OTM_PUT_COUNT = int(
    os.getenv(
        "OTM_PUT_COUNT",
        "5"
    )
)


# ============================================================
# SHA SETTINGS
# ============================================================

# Generic fallback SHA smoothing period.
#
# IMPORTANT:
# This is only a fallback.
# If the user's complete Pine Script is supplied, the exact
# Pine calculation should be implemented in indicators.py.

SHA_SMOOTHING_PERIOD = int(
    os.getenv(
        "SHA_SMOOTHING_PERIOD",
        "3"
    )
)


# ============================================================
# MARKET DATA SETTINGS
# ============================================================

MARKET_DATA_ENABLED = os.getenv(
    "MARKET_DATA_ENABLED",
    "true"
).lower() in {
    "1",
    "true",
    "yes",
    "on"
}


# How many candles to request initially.
DEFAULT_CANDLE_COUNT = int(
    os.getenv(
        "DEFAULT_CANDLE_COUNT",
        "500"
    )
)


# Maximum candles retained in backend memory
# for each active instrument.
MAX_CANDLES = int(
    os.getenv(
        "MAX_CANDLES",
        "2000"
    )
)


# ============================================================
# WEBSOCKET SETTINGS
# ============================================================

WEBSOCKET_ENABLED = os.getenv(
    "WEBSOCKET_ENABLED",
    "true"
).lower() in {
    "1",
    "true",
    "yes",
    "on"
}


# Seconds between WebSocket heartbeat messages.
WEBSOCKET_HEARTBEAT_SECONDS = int(
    os.getenv(
        "WEBSOCKET_HEARTBEAT_SECONDS",
        "20"
    )
)


# ============================================================
# 5PAISA / XSTREAM CREDENTIALS
# ============================================================

FIVEPAISA_APP_NAME = os.getenv(
    "FIVEPAISA_APP_NAME",
    ""
)

FIVEPAISA_USER_ID = os.getenv(
    "FIVEPAISA_USER_ID",
    ""
)

FIVEPAISA_PASSWORD = os.getenv(
    "FIVEPAISA_PASSWORD",
    ""
)

FIVEPAISA_USER_KEY = os.getenv(
    "FIVEPAISA_USER_KEY",
    ""
)

FIVEPAISA_ENCRYPTION_KEY = os.getenv(
    "FIVEPAISA_ENCRYPTION_KEY",
    ""
)


# ============================================================
# BROKER SETTINGS
# ============================================================

BROKER_NAME = os.getenv(
    "BROKER_NAME",
    "5paisa"
)

BROKER_ENVIRONMENT = os.getenv(
    "BROKER_ENVIRONMENT",
    "production"
)


# Actual broker API endpoints should be configured only after
# verifying the current 5paisa/Xstream API documentation.

FIVEPAISA_API_BASE_URL = os.getenv(
    "FIVEPAISA_API_BASE_URL",
    ""
)

FIVEPAISA_MARKET_DATA_URL = os.getenv(
    "FIVEPAISA_MARKET_DATA_URL",
    ""
)

FIVEPAISA_ORDER_URL = os.getenv(
    "FIVEPAISA_ORDER_URL",
    ""
)


# ============================================================
# TRADING
# ============================================================

# Keep trading disabled during the market-data development phase.

TRADING_ENABLED = os.getenv(
    "TRADING_ENABLED",
    "false"
).lower() in {
    "1",
    "true",
    "yes",
    "on"
}


# Buy/Sell API should not be called until explicitly enabled.
ORDERS_ENABLED = os.getenv(
    "ORDERS_ENABLED",
    "false"
).lower() in {
    "1",
    "true",
    "yes",
    "on"
}


# ============================================================
# RISK SETTINGS
# ============================================================

# These are safety defaults for the future order system.

MAX_ORDER_QUANTITY = int(
    os.getenv(
        "MAX_ORDER_QUANTITY",
        "0"
    )
)


MAX_DAILY_ORDERS = int(
    os.getenv(
        "MAX_DAILY_ORDERS",
        "0"
    )
)


# ============================================================
# CORS
# ============================================================

CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if origin.strip()
]


# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
).upper()


# ============================================================
# VALIDATION
# ============================================================

if DEFAULT_SYMBOL not in SUPPORTED_SYMBOLS:

    DEFAULT_SYMBOL = "NIFTY"


if DEFAULT_TIMEFRAME not in SUPPORTED_TIMEFRAMES:

    DEFAULT_TIMEFRAME = "5m"


if OTM_CALL_COUNT < 1:

    OTM_CALL_COUNT = 5


if OTM_PUT_COUNT < 1:

    OTM_PUT_COUNT = 5


if SHA_SMOOTHING_PERIOD < 1:

    SHA_SMOOTHING_PERIOD = 3


# ============================================================
# CONFIGURATION STATUS
# ============================================================

def broker_credentials_configured() -> bool:
    """
    Return True when the minimum 5paisa credentials are present.

    This does NOT verify that the credentials are valid.
    """

    required_values = (
        FIVEPAISA_APP_NAME,
        FIVEPAISA_USER_ID,
        FIVEPAISA_PASSWORD,
        FIVEPAISA_USER_KEY,
        FIVEPAISA_ENCRYPTION_KEY,
    )

    return all(
        bool(value)
        for value in required_values
    )


def configuration_status() -> dict:
    """
    Return a safe configuration summary.

    Sensitive credentials are never returned.
    """

    return {

        "app_name": APP_NAME,

        "environment": APP_ENV,

        "debug": DEBUG,

        "host": HOST,

        "port": PORT,

        "default_symbol":
            DEFAULT_SYMBOL,

        "default_timeframe":
            DEFAULT_TIMEFRAME,

        "supported_symbols":
            list(SUPPORTED_SYMBOLS),

        "supported_timeframes":
            list(SUPPORTED_TIMEFRAMES),

        "otm_call_count":
            OTM_CALL_COUNT,

        "otm_put_count":
            OTM_PUT_COUNT,

        "sha_smoothing_period":
            SHA_SMOOTHING_PERIOD,

        "market_data_enabled":
            MARKET_DATA_ENABLED,

        "websocket_enabled":
            WEBSOCKET_ENABLED,

        "trading_enabled":
            TRADING_ENABLED,

        "orders_enabled":
            ORDERS_ENABLED,

        "broker":
            BROKER_NAME,

        "broker_credentials_configured":
            broker_credentials_configured(),

    }


# ============================================================
# DIRECTORY SETUP
# ============================================================

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)
```
