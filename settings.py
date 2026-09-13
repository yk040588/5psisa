```python
"""
5paisa Xstream Trading Dashboard
Phase 1 Configuration

This file contains application configuration only.
Sensitive credentials must remain in .env.

Phase 1:
- Historical market data
- Local historical cache
- Future / Call / Put charts
- OTM-15 Calls
- OTM-15 Puts
- Smoothed Heiken Ashi
- 5paisa Xstream MarketFeedV3 WebSocket
- Live LTP
- Trading disabled
"""

from pathlib import Path
import os

from dotenv import load_dotenv


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
BACKEND_DIR = BASE_DIR / "Backend"
FRONTEND_DIR = BASE_DIR / "Frontend"

DATA_DIR = BASE_DIR / "data"
HISTORICAL_DIR = DATA_DIR / "historical"
CACHE_DIR = DATA_DIR / "cache"

ENV_FILE = BASE_DIR / ".env"


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv(ENV_FILE)


# ============================================================
# DIRECTORY SETUP
# ============================================================

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

HISTORICAL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# APPLICATION
# ============================================================

APP_NAME = os.getenv(
    "APP_NAME",
    "5paisa Trading Dashboard"
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
    "on",
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
# SUPPORTED SYMBOLS
# ============================================================

SUPPORTED_SYMBOLS = (
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS",
)


# ============================================================
# DEFAULT DASHBOARD
# ============================================================

DEFAULT_SYMBOL = os.getenv(
    "DEFAULT_SYMBOL",
    "NIFTY"
).upper()

DEFAULT_TIMEFRAME = os.getenv(
    "DEFAULT_TIMEFRAME",
    "5m"
).lower()


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
# OTM SETTINGS
# ============================================================

# Phase 1 requirement:
# 15 OTM Calls + 15 OTM Puts

OTM_CALL_COUNT = int(
    os.getenv(
        "OTM_CALL_COUNT",
        "15"
    )
)

OTM_PUT_COUNT = int(
    os.getenv(
        "OTM_PUT_COUNT",
        "15"
    )
)


# Maximum live instruments:
#
# 1 Future
# + 15 Calls
# + 15 Puts
# = 31 instruments

MAX_LIVE_INSTRUMENTS = (
    1
    + OTM_CALL_COUNT
    + OTM_PUT_COUNT
)


# ============================================================
# MARKET DATA
# ============================================================

MARKET_DATA_ENABLED = os.getenv(
    "MARKET_DATA_ENABLED",
    "true"
).lower() in {
    "1",
    "true",
    "yes",
    "on",
}


DEFAULT_CANDLE_COUNT = int(
    os.getenv(
        "DEFAULT_CANDLE_COUNT",
        "500"
    )
)

MAX_CANDLES = int(
    os.getenv(
        "MAX_CANDLES",
        "2000"
    )
)


# ============================================================
# HISTORICAL DATA
# ============================================================

FIVEPAISA_HISTORICAL_URL = os.getenv(
    "FIVEPAISA_HISTORICAL_URL",
    "https://openapi.5paisa.com/V2/historical"
)


# Native 5paisa intervals.
#
# 3m and 4h are intentionally NOT included here.
# They are created locally by resampling:
#
# 3m = 1m data
# 4h = 60m data

XSTREAM_NATIVE_INTERVALS = (
    "1m",
    "5m",
    "10m",
    "15m",
    "30m",
    "60m",
    "1d",
)


# Dashboard timeframe -> Xstream interval

TIMEFRAME_API_MAP = {
    "1m": "1m",
    "3m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "60m",
    "1d": "1d",
}


# ============================================================
# 5PAISA XSTREAM AUTHENTICATION
# ============================================================

FIVEPAISA_APP_KEY = os.getenv(
    "FIVEPAISA_APP_KEY",
    ""
)

FIVEPAISA_VENDOR_KEY = os.getenv(
    "FIVEPAISA_VENDOR_KEY",
    ""
)

FIVEPAISA_USER_ID = os.getenv(
    "FIVEPAISA_USER_ID",
    ""
)

FIVEPAISA_ENCRYPTION_KEY = os.getenv(
    "FIVEPAISA_ENCRYPTION_KEY",
    ""
)

FIVEPAISA_CLIENT_CODE = os.getenv(
    "FIVEPAISA_CLIENT_CODE",
    ""
)


# ------------------------------------------------------------
# Compatibility aliases
# ------------------------------------------------------------

# Some older project files may use these names.
# Keep them as aliases so old imports do not immediately break.

FIVEPAISA_USER_KEY = os.getenv(
    "FIVEPAISA_USER_KEY",
    FIVEPAISA_APP_KEY
)

FIVEPAISA_APP_NAME = os.getenv(
    "FIVEPAISA_APP_NAME",
    APP_NAME
)

FIVEPAISA_PASSWORD = os.getenv(
    "FIVEPAISA_PASSWORD",
    ""
)


# ============================================================
# OAUTH
# ============================================================

FIVEPAISA_OAUTH_URL = os.getenv(
    "FIVEPAISA_OAUTH_URL",
    "https://dev-openapi.5paisa.com/"
    "WebVendorLogin/VLogin/Index"
)

FIVEPAISA_REDIRECT_URL = os.getenv(
    "FIVEPAISA_REDIRECT_URL",
    "http://127.0.0.1:8000/api/5paisa/callback"
)

FIVEPAISA_STATE = os.getenv(
    "FIVEPAISA_STATE",
    "5paisa_dashboard"
)


# ============================================================
# ACCESS TOKEN
# ============================================================

FIVEPAISA_ACCESS_TOKEN_URL = os.getenv(
    "FIVEPAISA_ACCESS_TOKEN_URL",
    "https://Openapi.5paisa.com/"
    "VendorsAPI/Service1.svc/GetAccessToken"
)


# ============================================================
# MARKET FEED REST
# ============================================================

FIVEPAISA_MARKET_FEED_URL = os.getenv(
    "FIVEPAISA_MARKET_FEED_URL",
    "https://Openapi.5paisa.com/"
    "VendorsAPI/Service1.svc/V1/MarketFeed"
)


# ============================================================
# MARKET SNAPSHOT
# ============================================================

FIVEPAISA_MARKET_SNAPSHOT_URL = os.getenv(
    "FIVEPAISA_MARKET_SNAPSHOT_URL",
    "https://Openapi.5paisa.com/"
    "VendorsAPI/Service1.svc/MarketSnapshot"
)


# ============================================================
# XSTREAM SCRIP MASTER
# ============================================================

FIVEPAISA_SCRIP_MASTER_URL = os.getenv(
    "FIVEPAISA_SCRIP_MASTER_URL",
    "https://Openapi.5paisa.com/"
    "VendorsAPI/Service1.svc/"
    "ScripMaster/segment/all"
)


# ============================================================
# XSTREAM MARKETFEEDV3 WEBSOCKET
# ============================================================

WEBSOCKET_ENABLED = os.getenv(
    "WEBSOCKET_ENABLED",
    "true"
).lower() in {
    "1",
    "true",
    "yes",
    "on",
}


FIVEPAISA_WEBSOCKET_URL = os.getenv(
    "FIVEPAISA_WEBSOCKET_URL",
    "wss://openfeed.5paisa.com/"
    "feeds/api/chat"
)


WEBSOCKET_HEARTBEAT_SECONDS = int(
    os.getenv(
        "WEBSOCKET_HEARTBEAT_SECONDS",
        "20"
    )
)

WEBSOCKET_RECONNECT_SECONDS = float(
    os.getenv(
        "WEBSOCKET_RECONNECT_SECONDS",
        "3"
    )
)


# ============================================================
# BROKER
# ============================================================

BROKER_NAME = os.getenv(
    "BROKER_NAME",
    "5paisa"
)

BROKER_ENVIRONMENT = os.getenv(
    "BROKER_ENVIRONMENT",
    "development"
)


# ============================================================
# SHA - SMOOTHED HEIKEN ASHI
# ============================================================

# Phase 1 default:
#
# Raw OHLC
#     ↓
# Before-HA EMA
#     ↓
# Heikin Ashi
#     ↓
# After-HA EMA
#     ↓
# SHA

SHA_BEFORE_SMOOTH_LENGTH = int(
    os.getenv(
        "SHA_BEFORE_SMOOTH_LENGTH",
        "10"
    )
)

SHA_BEFORE_MA_TYPE = os.getenv(
    "SHA_BEFORE_MA_TYPE",
    "EMA"
).upper()

SHA_AFTER_SMOOTH_LENGTH = int(
    os.getenv(
        "SHA_AFTER_SMOOTH_LENGTH",
        "10"
    )
)

SHA_AFTER_MA_TYPE = os.getenv(
    "SHA_AFTER_MA_TYPE",
    "EMA"
).upper()


# Compatibility with older indicators.py

SHA_SMOOTHING_PERIOD = int(
    os.getenv(
        "SHA_SMOOTHING_PERIOD",
        "3"
    )
)


# ============================================================
# TRADING
# ============================================================

# Phase 1 = chart/data development.
# Orders remain disabled.

TRADING_ENABLED = os.getenv(
    "TRADING_ENABLED",
    "false"
).lower() in {
    "1",
    "true",
    "yes",
    "on",
}

ORDERS_ENABLED = os.getenv(
    "ORDERS_ENABLED",
    "false"
).lower() in {
    "1",
    "true",
    "yes",
    "on",
}


# ============================================================
# RISK LIMITS
# ============================================================

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
        "http://127.0.0.1:8000,"
        "http://localhost:8000"
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
    OTM_CALL_COUNT = 15


if OTM_PUT_COUNT < 1:
    OTM_PUT_COUNT = 15


if SHA_BEFORE_SMOOTH_LENGTH < 1:
    SHA_BEFORE_SMOOTH_LENGTH = 10


if SHA_AFTER_SMOOTH_LENGTH < 1:
    SHA_AFTER_SMOOTH_LENGTH = 10


if MAX_CANDLES < DEFAULT_CANDLE_COUNT:
    MAX_CANDLES = DEFAULT_CANDLE_COUNT


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def broker_credentials_configured() -> bool:
    """
    Check whether the minimum credentials required for
    Xstream access-token generation are present.

    This does NOT verify whether the credentials are valid.
    """

    required = (
        FIVEPAISA_APP_KEY,
        FIVEPAISA_USER_ID,
        FIVEPAISA_ENCRYPTION_KEY,
    )

    return all(
        bool(value)
        for value in required
    )


def websocket_credentials_configured() -> bool:
    """
    Check whether the credentials required to establish
    the Xstream MarketFeedV3 WebSocket are available.
    """

    return bool(
        FIVEPAISA_CLIENT_CODE
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

        "default_symbol": DEFAULT_SYMBOL,
        "default_timeframe": DEFAULT_TIMEFRAME,

        "supported_symbols": list(
            SUPPORTED_SYMBOLS
        ),

        "supported_timeframes": list(
            SUPPORTED_TIMEFRAMES
        ),

        "otm_call_count": OTM_CALL_COUNT,
        "otm_put_count": OTM_PUT_COUNT,

        "max_live_instruments":
            MAX_LIVE_INSTRUMENTS,

        "market_data_enabled":
            MARKET_DATA_ENABLED,

        "websocket_enabled":
            WEBSOCKET_ENABLED,

        "trading_enabled":
            TRADING_ENABLED,

        "orders_enabled":
            ORDERS_ENABLED,

        "sha_before_smooth_length":
            SHA_BEFORE_SMOOTH_LENGTH,

        "sha_before_ma_type":
            SHA_BEFORE_MA_TYPE,

        "sha_after_smooth_length":
            SHA_AFTER_SMOOTH_LENGTH,

        "sha_after_ma_type":
            SHA_AFTER_MA_TYPE,

        "broker":
            BROKER_NAME,

        "broker_environment":
            BROKER_ENVIRONMENT,

        "broker_credentials_configured":
            broker_credentials_configured(),

        "websocket_credentials_configured":
            websocket_credentials_configured(),
    }


# ============================================================
# SHARED SETTINGS OBJECT
# ============================================================

class Settings:
    """
    Compatibility object used by the backend modules.

    Example:

        from config.settings import settings

        settings.FIVEPAISA_APP_KEY
        settings.DATA_DIR
    """

    BASE_DIR = BASE_DIR
    CONFIG_DIR = CONFIG_DIR
    BACKEND_DIR = BACKEND_DIR
    FRONTEND_DIR = FRONTEND_DIR

    DATA_DIR = DATA_DIR
    HISTORICAL_DIR = HISTORICAL_DIR
    CACHE_DIR = CACHE_DIR

    APP_NAME = APP_NAME
    APP_ENV = APP_ENV
    DEBUG = DEBUG
    HOST = HOST
    PORT = PORT

    SUPPORTED_SYMBOLS = SUPPORTED_SYMBOLS
    SUPPORTED_TIMEFRAMES = SUPPORTED_TIMEFRAMES

    DEFAULT_SYMBOL = DEFAULT_SYMBOL
    DEFAULT_TIMEFRAME = DEFAULT_TIMEFRAME

    OTM_CALL_COUNT = OTM_CALL_COUNT
    OTM_PUT_COUNT = OTM_PUT_COUNT
    MAX_LIVE_INSTRUMENTS = MAX_LIVE_INSTRUMENTS

    MARKET_DATA_ENABLED = MARKET_DATA_ENABLED

    DEFAULT_CANDLE_COUNT = DEFAULT_CANDLE_COUNT
    MAX_CANDLES = MAX_CANDLES

    FIVEPAISA_HISTORICAL_URL = FIVEPAISA_HISTORICAL_URL

    XSTREAM_NATIVE_INTERVALS = XSTREAM_NATIVE_INTERVALS
    TIMEFRAME_API_MAP = TIMEFRAME_API_MAP

    FIVEPAISA_APP_KEY = FIVEPAISA_APP_KEY
    FIVEPAISA_VENDOR_KEY = FIVEPAISA_VENDOR_KEY
    FIVEPAISA_USER_ID = FIVEPAISA_USER_ID
    FIVEPAISA_ENCRYPTION_KEY = FIVEPAISA_ENCRYPTION_KEY
    FIVEPAISA_CLIENT_CODE = FIVEPAISA_CLIENT_CODE

    FIVEPAISA_USER_KEY = FIVEPAISA_USER_KEY
    FIVEPAISA_APP_NAME = FIVEPAISA_APP_NAME
    FIVEPAISA_PASSWORD = FIVEPAISA_PASSWORD

    FIVEPAISA_OAUTH_URL = FIVEPAISA_OAUTH_URL
    FIVEPAISA_REDIRECT_URL = FIVEPAISA_REDIRECT_URL
    FIVEPAISA_STATE = FIVEPAISA_STATE

    FIVEPAISA_ACCESS_TOKEN_URL = (
        FIVEPAISA_ACCESS_TOKEN_URL
    )

    FIVEPAISA_MARKET_FEED_URL = (
        FIVEPAISA_MARKET_FEED_URL
    )

    FIVEPAISA_MARKET_SNAPSHOT_URL = (
        FIVEPAISA_MARKET_SNAPSHOT_URL
    )

    FIVEPAISA_SCRIP_MASTER_URL = (
        FIVEPAISA_SCRIP_MASTER_URL
    )

    WEBSOCKET_ENABLED = WEBSOCKET_ENABLED

    FIVEPAISA_WEBSOCKET_URL = (
        FIVEPAISA_WEBSOCKET_URL
    )

    WEBSOCKET_HEARTBEAT_SECONDS = (
        WEBSOCKET_HEARTBEAT_SECONDS
    )

    WEBSOCKET_RECONNECT_SECONDS = (
        WEBSOCKET_RECONNECT_SECONDS
    )

    SHA_BEFORE_SMOOTH_LENGTH = (
        SHA_BEFORE_SMOOTH_LENGTH
    )

    SHA_BEFORE_MA_TYPE = (
        SHA_BEFORE_MA_TYPE
    )

    SHA_AFTER_SMOOTH_LENGTH = (
        SHA_AFTER_SMOOTH_LENGTH
    )

    SHA_AFTER_MA_TYPE = (
        SHA_AFTER_MA_TYPE
    )

    SHA_SMOOTHING_PERIOD = (
        SHA_SMOOTHING_PERIOD
    )

    BROKER_NAME = BROKER_NAME
    BROKER_ENVIRONMENT = BROKER_ENVIRONMENT

    TRADING_ENABLED = TRADING_ENABLED
    ORDERS_ENABLED = ORDERS_ENABLED

    MAX_ORDER_QUANTITY = MAX_ORDER_QUANTITY
    MAX_DAILY_ORDERS = MAX_DAILY_ORDERS

    CORS_ALLOW_ORIGINS = CORS_ALLOW_ORIGINS
    LOG_LEVEL = LOG_LEVEL


settings = Settings()
```
