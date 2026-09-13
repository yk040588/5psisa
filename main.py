```python
from __future__ import annotations

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from Backend.broker import broker
from Backend.instruments import (
    SUPPORTED_UNDERLYINGS,
    instrument_manager,
)
from Backend import market_data
from Backend.websocket_manager import websocket_manager


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "Frontend"

INDEX_FILE = FRONTEND_DIR / "index.html"
APP_JS_FILE = FRONTEND_DIR / "app.js"
CHARTS_JS_FILE = FRONTEND_DIR / "charts.js"
CONTROLS_JS_FILE = FRONTEND_DIR / "controls.js"
INDICATORS_JS_FILE = FRONTEND_DIR / "indicators.js"
STYLE_CSS_FILE = FRONTEND_DIR / "style.css"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("5paisa.main")


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_SYMBOL = "NIFTY"
DEFAULT_TIMEFRAME = "5m"

OTM_CALL_COUNT = 15
OTM_PUT_COUNT = 15

TRADING_ENABLED = False
ORDERS_ENABLED = False


# ============================================================
# GENERIC HELPERS
# ============================================================

async def maybe_await(value: Any) -> Any:
    """
    Allows us to work with both synchronous and asynchronous
    methods in existing backend modules.
    """
    if inspect.isawaitable(value):
        return await value

    return value


def safe_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value

    if hasattr(value, "to_dict"):
        try:
            result = value.to_dict()
            if isinstance(result, dict):
                return result
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return dict(value.__dict__)
        except Exception:
            pass

    return {}


def safe_list(value: Any) -> list:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, set):
        return list(value)

    return [value]


def normalize_instrument(item: Any) -> dict:
    """
    Converts dataclass/object/dict instrument into JSON-safe dict.
    """

    if isinstance(item, dict):
        result = dict(item)

    elif hasattr(item, "to_dict"):
        try:
            result = item.to_dict()
        except Exception:
            result = safe_dict(item)

    else:
        result = safe_dict(item)

    # Normalize common field names.
    if "scrip_code" in result and "ScripCode" not in result:
        result["ScripCode"] = result["scrip_code"]

    if "broker_token" in result and "Token" not in result:
        result["Token"] = result["broker_token"]

    if "exchange" in result and "Exch" not in result:
        result["Exch"] = result["exchange"]

    if "exchange_type" in result and "ExchType" not in result:
        result["ExchType"] = result["exchange_type"]

    if "expiry" in result and result["expiry"] is not None:
        result["expiry"] = str(result["expiry"])

    return result


def instrument_to_xstream(item: Any) -> dict | None:
    """
    Converts our Instrument object to the exact fields needed
    by Xstream MarketFeedV3 subscription.
    """

    data = normalize_instrument(item)

    exchange = (
        data.get("Exch")
        or data.get("exchange")
        or data.get("Exchange")
    )

    exchange_type = (
        data.get("ExchType")
        or data.get("exchange_type")
        or data.get("ExchangeType")
    )

    scrip_code = (
        data.get("ScripCode")
        or data.get("scrip_code")
        or data.get("Scripcode")
    )

    if exchange is None or exchange_type is None or scrip_code is None:
        return None

    try:
        scrip_code = int(scrip_code)
    except (TypeError, ValueError):
        return None

    return {
        "Exch": str(exchange),
        "ExchType": str(exchange_type),
        "ScripCode": scrip_code,
    }


# ============================================================
# BROKER HELPERS
# ============================================================

async def broker_is_connected() -> bool:
    """
    Reads broker connection state without assuming a particular
    implementation of broker.py.
    """

    try:
        value = getattr(broker, "connected", False)

        if callable(value):
            value = value()

        value = await maybe_await(value)

        return bool(value)

    except Exception:
        return False


async def broker_login() -> bool:
    """
    Attempts broker login if the current broker implementation
    provides login().
    """

    try:
        login_method = getattr(broker, "login", None)

        if login_method is None:
            return False

        result = await maybe_await(login_method())

        if isinstance(result, bool):
            return result

        return await broker_is_connected()

    except Exception as exc:
        logger.warning("Broker login not completed: %s", exc)
        return False


async def broker_logout() -> None:
    try:
        logout_method = getattr(broker, "logout", None)

        if logout_method is not None:
            await maybe_await(logout_method())

    except Exception as exc:
        logger.warning("Broker logout error: %s", exc)


# ============================================================
# INSTRUMENT MANAGER HELPERS
# ============================================================

async def update_instruments() -> Any:
    """
    Loads/updates the 5paisa Scrip Master.

    Supports different method names used by earlier versions
    of instruments.py.
    """

    candidates = [
        "update",
        "update_instruments",
        "load",
        "load_instruments",
        "refresh",
        "refresh_instruments",
    ]

    for method_name in candidates:
        method = getattr(instrument_manager, method_name, None)

        if method is None:
            continue

        try:
            result = await maybe_await(method())
            logger.info("Instrument manager updated using %s()", method_name)
            return result

        except TypeError:
            continue

        except Exception as exc:
            logger.warning(
                "Instrument update using %s() failed: %s",
                method_name,
                exc,
            )
            return None

    logger.warning("No instrument update method found.")
    return None


def instrument_status() -> dict:
    """
    Returns best-effort instrument manager status.
    """

    try:
        method = getattr(instrument_manager, "status", None)

        if method is not None:
            result = method()

            if isinstance(result, dict):
                return result

    except Exception:
        pass

    result = {
        "loaded": False,
        "instrument_count": 0,
    }

    for attr in (
        "loaded",
        "is_loaded",
        "_loaded",
    ):
        if hasattr(instrument_manager, attr):
            try:
                result["loaded"] = bool(getattr(instrument_manager, attr))
                break
            except Exception:
                pass

    for attr in (
        "instruments",
        "_instruments",
        "all_instruments",
    ):
        if hasattr(instrument_manager, attr):
            try:
                value = getattr(instrument_manager, attr)

                if isinstance(value, dict):
                    result["instrument_count"] = len(value)

                elif isinstance(value, (list, tuple, set)):
                    result["instrument_count"] = len(value)

                break

            except Exception:
                pass

    return result


# ============================================================
# INSTRUMENT QUERY HELPERS
# ============================================================

async def get_expiries(symbol: str) -> list:
    method = getattr(instrument_manager, "get_expiries", None)

    if method is None:
        return []

    try:
        result = await maybe_await(method(symbol))
        return safe_list(result)

    except Exception as exc:
        logger.warning("get_expiries(%s) failed: %s", symbol, exc)
        return []


async def get_futures(symbol: str, expiry: str | None = None) -> list:
    method = getattr(instrument_manager, "get_futures", None)

    if method is None:
        return []

    try:
        if expiry:
            try:
                result = await maybe_await(method(symbol, expiry))
            except TypeError:
                result = await maybe_await(method(symbol))
        else:
            result = await maybe_await(method(symbol))

        return safe_list(result)

    except Exception as exc:
        logger.warning("get_futures(%s) failed: %s", symbol, exc)
        return []


async def get_options(
    symbol: str,
    expiry: str | None = None,
) -> list:
    method = getattr(instrument_manager, "get_options", None)

    if method is None:
        return []

    try:
        if expiry:
            try:
                result = await maybe_await(method(symbol, expiry))
            except TypeError:
                result = await maybe_await(method(symbol))
        else:
            result = await maybe_await(method(symbol))

        return safe_list(result)

    except Exception as exc:
        logger.warning("get_options(%s) failed: %s", symbol, exc)
        return []


async def get_nearest_future(
    symbol: str,
    expiry: str | None = None,
) -> Any:
    method = getattr(instrument_manager, "get_nearest_future", None)

    if method is None:
        futures = await get_futures(symbol, expiry)

        return futures[0] if futures else None

    try:
        if expiry:
            try:
                return await maybe_await(method(symbol, expiry))
            except TypeError:
                return await maybe_await(method(symbol))

        return await maybe_await(method(symbol))

    except Exception as exc:
        logger.warning(
            "get_nearest_future(%s) failed: %s",
            symbol,
            exc,
        )

        futures = await get_futures(symbol, expiry)
        return futures[0] if futures else None


async def get_otm_options(
    symbol: str,
    expiry: str | None,
    underlying_price: float | None,
) -> tuple[list, list]:
    """
    Uses the final instruments.py OTM-15 implementation.

    Returns:
        calls, puts
    """

    method = getattr(instrument_manager, "get_otm_options", None)

    if method is None:
        return [], []

    try:
        # Preferred final signature.
        try:
            result = await maybe_await(
                method(
                    symbol=symbol,
                    expiry=expiry,
                    underlying_price=underlying_price,
                    call_count=OTM_CALL_COUNT,
                    put_count=OTM_PUT_COUNT,
                )
            )

        except TypeError:

            try:
                result = await maybe_await(
                    method(
                        symbol,
                        expiry,
                        underlying_price,
                        OTM_CALL_COUNT,
                        OTM_PUT_COUNT,
                    )
                )

            except TypeError:

                result = await maybe_await(
                    method(
                        symbol,
                        expiry,
                        underlying_price,
                    )
                )

        if isinstance(result, tuple) and len(result) == 2:
            return safe_list(result[0]), safe_list(result[1])

        if isinstance(result, dict):
            calls = (
                result.get("calls")
                or result.get("call")
                or []
            )

            puts = (
                result.get("puts")
                or result.get("put")
                or []
            )

            return safe_list(calls), safe_list(puts)

        return [], []

    except Exception as exc:
        logger.warning(
            "OTM selection failed for %s/%s: %s",
            symbol,
            expiry,
            exc,
        )

        return [], []


# ============================================================
# PRICE EXTRACTION
# ============================================================

def extract_price(data: Any) -> float | None:
    """
    Extract LTP/price from instrument, quote or market-feed object.
    """

    if data is None:
        return None

    if isinstance(data, (int, float)):
        return float(data)

    if isinstance(data, dict):
        keys = [
            "LastRate",
            "LTP",
            "ltp",
            "last_rate",
            "LastPrice",
            "last_price",
            "Close",
            "close",
            "price",
            "Price",
        ]

        for key in keys:
            value = data.get(key)

            if value is None:
                continue

            try:
                return float(value)
            except (TypeError, ValueError):
                continue

    for attr in (
        "LastRate",
        "LTP",
        "ltp",
        "last_rate",
        "last_price",
        "price",
        "Price",
        "Close",
        "close",
    ):
        try:
            value = getattr(data, attr)

            if value is None:
                continue

            return float(value)

        except (AttributeError, TypeError, ValueError):
            continue

    return None


async def get_future_price(future: Any) -> float | None:
    """
    Gets current Future price.

    Phase 1 prefers a broker quote/snapshot if available,
    otherwise uses price information already present on
    the instrument.
    """

    if future is None:
        return None

    # First try broker quote methods.
    for method_name in (
        "get_quote",
        "quote",
        "get_market_quote",
        "get_market_snapshot",
        "market_snapshot",
    ):
        method = getattr(broker, method_name, None)

        if method is None:
            continue

        data = normalize_instrument(future)

        exchange = (
            data.get("Exch")
            or data.get("exchange")
        )

        exchange_type = (
            data.get("ExchType")
            or data.get("exchange_type")
        )

        scrip_code = (
            data.get("ScripCode")
            or data.get("scrip_code")
        )

        try:
            # Try object first.
            try:
                result = await maybe_await(method(future))
            except TypeError:

                # Try common broker arguments.
                result = await maybe_await(
                    method(
                        exchange,
                        exchange_type,
                        scrip_code,
                    )
                )

            price = extract_price(result)

            if price is not None:
                return price

        except Exception:
            continue

    return extract_price(future)


# ============================================================
# MARKET DATA HELPERS
# ============================================================

async def historical_data(
    symbol: str,
    expiry: str | None,
    instrument_type: str,
    strike: float | None,
    option_type: str | None,
    timeframe: str,
    limit: int,
) -> list:
    """
    Calls existing market_data.py implementation.

    The helper supports several method names/signatures so that
    the new main.py remains compatible with the current backend.
    """

    candidates = [
        "get_historical",
        "get_historical_data",
        "historical",
        "fetch_historical",
    ]

    method = None

    for method_name in candidates:
        candidate = getattr(market_data, method_name, None)

        if candidate is not None:
            method = candidate
            break

    if method is None:
        raise HTTPException(
            status_code=500,
            detail="Historical data method is not available.",
        )

    kwargs = {
        "symbol": symbol,
        "expiry": expiry,
        "instrument_type": instrument_type,
        "strike": strike,
        "option_type": option_type,
        "timeframe": timeframe,
        "limit": limit,
        "refresh": False,
    }

    try:
        result = await maybe_await(method(**kwargs))
        return safe_list(result)

    except TypeError:
        pass

    # Compatibility fallback.
    try:
        result = await maybe_await(
            method(
                symbol,
                expiry,
                instrument_type,
                strike,
                option_type,
                timeframe,
                limit,
            )
        )

        return safe_list(result)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Historical data error: {exc}",
        )


# ============================================================
# XSTREAM SUBSCRIPTION HELPERS
# ============================================================

async def subscribe_instruments(
    instruments: list[Any],
) -> Any:
    """
    Sends selected Future + OTM-15 Calls + OTM-15 Puts
    to the WebSocket manager.

    The actual Xstream MarketFeedV3 protocol remains inside
    websocket_manager.py.
    """

    normalized = []

    for item in instruments:
        if item is None:
            continue

        xstream_item = instrument_to_xstream(item)

        if xstream_item is not None:
            normalized.append(xstream_item)

    if not normalized:
        return None

    # Preferred API.
    for method_name in (
        "subscribe",
        "subscribe_instruments",
        "subscribe_tokens",
    ):
        method = getattr(websocket_manager, method_name, None)

        if method is None:
            continue

        try:
            return await maybe_await(method(normalized))

        except TypeError:
            try:
                return await maybe_await(
                    method(
                        normalized
                    )
                )
            except Exception:
                continue

        except Exception as exc:
            logger.warning(
                "WebSocket subscribe failed: %s",
                exc,
            )
            return None

    logger.warning(
        "websocket_manager has no subscription method."
    )

    return None


async def unsubscribe_all() -> Any:
    """
    Clears current broker subscriptions when selection changes.
    """

    for method_name in (
        "unsubscribe_all",
        "unsubscribe",
        "clear_subscriptions",
    ):
        method = getattr(websocket_manager, method_name, None)

        if method is None:
            continue

        try:
            return await maybe_await(method())

        except TypeError:
            continue

        except Exception as exc:
            logger.warning(
                "WebSocket unsubscribe failed: %s",
                exc,
            )
            return None

    return None


# ============================================================
# DASHBOARD BUILDER
# ============================================================

async def build_dashboard(
    symbol: str,
    expiry: str | None = None,
) -> dict:
    """
    Main Phase-1 dashboard pipeline:

        Symbol
          ↓
        Expiry
          ↓
        Future
          ↓
        Future price
          ↓
        15 OTM Calls
        15 OTM Puts
          ↓
        Xstream subscription
    """

    symbol = symbol.upper().strip()

    if symbol not in SUPPORTED_UNDERLYINGS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported symbol '{symbol}'. "
                f"Supported symbols: {SUPPORTED_UNDERLYINGS}"
            ),
        )

    # --------------------------------------------------------
    # Expiry
    # --------------------------------------------------------

    expiries = await get_expiries(symbol)

    normalized_expiries = []

    for item in expiries:
        if isinstance(item, dict):
            value = (
                item.get("expiry")
                or item.get("Expiry")
                or item.get("ExpiryDate")
            )

            if value is not None:
                normalized_expiries.append(str(value))

        else:
            normalized_expiries.append(str(item))

    if expiry:
        selected_expiry = str(expiry)
    else:
        selected_expiry = (
            normalized_expiries[0]
            if normalized_expiries
            else None
        )

    # --------------------------------------------------------
    # Future
    # --------------------------------------------------------

    future = await get_nearest_future(
        symbol,
        selected_expiry,
    )

    future_data = normalize_instrument(future) if future else {}

    future_price = await get_future_price(future)

    # --------------------------------------------------------
    # OTM-15
    # --------------------------------------------------------

    calls, puts = await get_otm_options(
        symbol=symbol,
        expiry=selected_expiry,
        underlying_price=future_price,
    )

    # Safety limit.
    calls = calls[:OTM_CALL_COUNT]
    puts = puts[:OTM_PUT_COUNT]

    # --------------------------------------------------------
    # Subscribe Future + 15 CE + 15 PE
    # --------------------------------------------------------

    selected_instruments = []

    if future is not None:
        selected_instruments.append(future)

    selected_instruments.extend(calls)
    selected_instruments.extend(puts)

    await unsubscribe_all()

    if selected_instruments:
        await subscribe_instruments(selected_instruments)

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "success": True,
        "symbol": symbol,
        "expiry": selected_expiry,
        "expiries": normalized_expiries,

        "future": future_data,

        "future_price": future_price,

        "futures": (
            [normalize_instrument(future)]
            if future is not None
            else []
        ),

        "calls": [
            normalize_instrument(item)
            for item in calls
        ],

        "puts": [
            normalize_instrument(item)
            for item in puts
        ],

        "otm_call_count": len(calls),
        "otm_put_count": len(puts),

        "selected": {
            "future": future_data,
            "call": (
                normalize_instrument(calls[0])
                if calls
                else None
            ),
            "put": (
                normalize_instrument(puts[0])
                if puts
                else None
            ),
        },

        "live_feed": {
            "provider": "5paisa Xstream",
            "protocol": "MarketFeedV3",
            "enabled": True,
        },

        "sha": {
            "enabled": True,
            "before_smoothing_length": 10,
            "after_smoothing_length": 10,
            "ma_type": "EMA",
        },

        "trading": {
            "enabled": TRADING_ENABLED,
            "orders_enabled": ORDERS_ENABLED,
        },
    }


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting 5paisa Trading Dashboard...")

    # --------------------------------------------------------
    # Load Scrip Master
    # --------------------------------------------------------

    try:
        await update_instruments()
    except Exception as exc:
        logger.warning(
            "Instrument initialization failed: %s",
            exc,
        )

    # --------------------------------------------------------
    # Start WebSocket manager
    # --------------------------------------------------------

    try:
        start_method = getattr(
            websocket_manager,
            "start",
            None,
        )

        if start_method is not None:
            await maybe_await(start_method())

            logger.info(
                "Market WebSocket manager started."
            )

    except Exception as exc:
        logger.warning(
            "WebSocket manager startup failed: %s",
            exc,
        )

    # --------------------------------------------------------
    # Broker login
    #
    # Do not force application startup to fail if credentials
    # are not configured yet. Historical/cache functionality
    # can still work.
    # --------------------------------------------------------

    connected = await broker_is_connected()

    if not connected:
        logger.info(
            "5paisa broker is not connected at startup."
        )

    yield

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    try:
        await unsubscribe_all()
    except Exception:
        pass

    try:
        stop_method = getattr(
            websocket_manager,
            "stop",
            None,
        )

        if stop_method is not None:
            await maybe_await(stop_method())

    except Exception as exc:
        logger.warning(
            "WebSocket manager shutdown error: %s",
            exc,
        )

    await broker_logout()

    logger.info(
        "5paisa Trading Dashboard stopped."
    )


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="5paisa Trading Dashboard",
    description=(
        "Phase 1 local trading dashboard using "
        "5paisa Xstream market data."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# FRONTEND ROUTES
# ============================================================

@app.get("/", include_in_schema=False)
async def serve_index():
    if not INDEX_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend/index.html not found.",
        )

    return FileResponse(INDEX_FILE)


@app.get("/index.html", include_in_schema=False)
async def serve_index_html():
    return await serve_index()


@app.get("/app.js", include_in_schema=False)
async def serve_app_js():
    if not APP_JS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend/app.js not found.",
        )

    return FileResponse(
        APP_JS_FILE,
        media_type="application/javascript",
    )


@app.get("/charts.js", include_in_schema=False)
async def serve_charts_js():
    if not CHARTS_JS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend/charts.js not found.",
        )

    return FileResponse(
        CHARTS_JS_FILE,
        media_type="application/javascript",
    )


@app.get("/controls.js", include_in_schema=False)
async def serve_controls_js():
    if not CONTROLS_JS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend/controls.js not found.",
        )

    return FileResponse(
        CONTROLS_JS_FILE,
        media_type="application/javascript",
    )


@app.get("/indicators.js", include_in_schema=False)
async def serve_indicators_js():
    if not INDICATORS_JS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend/indicators.js not found.",
        )

    return FileResponse(
        INDICATORS_JS_FILE,
        media_type="application/javascript",
    )


@app.get("/style.css", include_in_schema=False)
async def serve_style_css():
    if not STYLE_CSS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend/style.css not found.",
        )

    return FileResponse(
        STYLE_CSS_FILE,
        media_type="text/css",
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "application": "5paisa Trading Dashboard",
        "phase": 1,
        "trading_enabled": TRADING_ENABLED,
        "orders_enabled": ORDERS_ENABLED,
    }


# ============================================================
# STATUS
# ============================================================

@app.get("/api/status")
async def status():
    connected = await broker_is_connected()

    return {
        "status": "ok",
        "broker": {
            "name": "5paisa",
            "connected": connected,
        },
        "instruments": instrument_status(),
        "websocket": {
            "provider": "5paisa Xstream",
            "protocol": "MarketFeedV3",
            "enabled": True,
        },
        "phase": 1,
        "trading_enabled": TRADING_ENABLED,
        "orders_enabled": ORDERS_ENABLED,
    }


# ============================================================
# SYMBOLS
# ============================================================

@app.get("/api/symbols")
async def symbols():
    return {
        "success": True,
        "symbols": list(SUPPORTED_UNDERLYINGS),
        "default": DEFAULT_SYMBOL,
    }


# ============================================================
# EXPIRIES
# ============================================================

@app.get("/api/expiries")
async def expiries(
    symbol: str = Query(DEFAULT_SYMBOL),
):
    symbol = symbol.upper().strip()

    if symbol not in SUPPORTED_UNDERLYINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    values = await get_expiries(symbol)

    result = []

    for value in values:

        if isinstance(value, dict):
            expiry = (
                value.get("expiry")
                or value.get("Expiry")
                or value.get("ExpiryDate")
            )

            if expiry is not None:
                result.append(str(expiry))

        else:
            result.append(str(value))

    return {
        "success": True,
        "symbol": symbol,
        "expiries": result,
    }


# ============================================================
# FUTURES
# ============================================================

@app.get("/api/futures")
async def futures(
    symbol: str = Query(DEFAULT_SYMBOL),
    expiry: str | None = Query(None),
):
    symbol = symbol.upper().strip()

    if symbol not in SUPPORTED_UNDERLYINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    values = await get_futures(
        symbol,
        expiry,
    )

    return {
        "success": True,
        "symbol": symbol,
        "expiry": expiry,
        "futures": [
            normalize_instrument(item)
            for item in values
        ],
    }


# ============================================================
# OPTIONS
# ============================================================

@app.get("/api/options")
async def options(
    symbol: str = Query(DEFAULT_SYMBOL),
    expiry: str | None = Query(None),
    underlying_price: float | None = Query(None),
):
    symbol = symbol.upper().strip()

    if symbol not in SUPPORTED_UNDERLYINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    calls, puts = await get_otm_options(
        symbol=symbol,
        expiry=expiry,
        underlying_price=underlying_price,
    )

    return {
        "success": True,
        "symbol": symbol,
        "expiry": expiry,
        "calls": [
            normalize_instrument(item)
            for item in calls[:OTM_CALL_COUNT]
        ],
        "puts": [
            normalize_instrument(item)
            for item in puts[:OTM_PUT_COUNT]
        ],
        "otm_call_count": min(
            len(calls),
            OTM_CALL_COUNT,
        ),
        "otm_put_count": min(
            len(puts),
            OTM_PUT_COUNT,
        ),
    }


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/api/dashboard")
async def dashboard(
    symbol: str = Query(DEFAULT_SYMBOL),
    expiry: str | None = Query(None),
):
    return await build_dashboard(
        symbol=symbol,
        expiry=expiry,
    )


# ============================================================
# HISTORICAL DATA
# ============================================================

@app.get("/api/historical")
async def historical(
    symbol: str = Query(DEFAULT_SYMBOL),
    expiry: str | None = Query(None),

    instrument_type: str = Query("FUTURE"),

    strike: float | None = Query(None),

    option_type: str | None = Query(None),

    timeframe: str = Query(DEFAULT_TIMEFRAME),

    limit: int = Query(
        500,
        ge=1,
        le=2000,
    ),
):
    symbol = symbol.upper().strip()
    instrument_type = instrument_type.upper().strip()

    if symbol not in SUPPORTED_UNDERLYINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    valid_types = {
        "FUTURE",
        "CALL",
        "PUT",
    }

    if instrument_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "instrument_type must be "
                "FUTURE, CALL or PUT."
            ),
        )

    if option_type:
        option_type = option_type.upper().strip()

        if option_type not in {
            "CALL",
            "PUT",
            "CE",
            "PE",
        }:
            raise HTTPException(
                status_code=400,
                detail="Invalid option_type.",
            )

    candles = await historical_data(
        symbol=symbol,
        expiry=expiry,
        instrument_type=instrument_type,
        strike=strike,
        option_type=option_type,
        timeframe=timeframe,
        limit=limit,
    )

    return {
        "success": True,
        "symbol": symbol,
        "expiry": expiry,
        "instrument_type": instrument_type,
        "strike": strike,
        "option_type": option_type,
        "timeframe": timeframe,
        "count": len(candles),
        "candles": candles,
    }


# ============================================================
# INSTRUMENT MASTER REFRESH
# ============================================================

@app.post("/api/instruments/update")
async def instruments_update():
    result = await update_instruments()

    return {
        "success": True,
        "result": result,
        "status": instrument_status(),
    }


# Compatibility alias for earlier frontend/backend versions.
@app.post("/api/instruments/refresh")
async def instruments_refresh():
    return await instruments_update()


# ============================================================
# 5PAISA LOGIN
# ============================================================

@app.get("/api/5paisa/login")
async def fivepaisa_login():
    """
    Starts OAuth login using broker.py implementation.
    """

    candidates = (
        "get_login_url",
        "login_url",
        "get_oauth_login_url",
        "build_login_url",
    )

    for method_name in candidates:

        method = getattr(broker, method_name, None)

        if method is None:
            continue

        try:
            url = await maybe_await(method())

            if url:
                return {
                    "success": True,
                    "login_url": str(url),
                }

        except Exception as exc:
            logger.warning(
                "Login URL generation failed: %s",
                exc,
            )

    raise HTTPException(
        status_code=501,
        detail=(
            "OAuth login URL is not available in "
            "the current broker.py implementation."
        ),
    )


# ============================================================
# 5PAISA CALLBACK
# ============================================================

@app.get("/api/5paisa/callback")
async def fivepaisa_callback(
    request: Request,
):
    """
    Receives OAuth callback and passes RequestToken to broker.py.
    """

    params = dict(request.query_params)

    request_token = (
        params.get("RequestToken")
        or params.get("requestToken")
        or params.get("request_token")
    )

    if not request_token:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "RequestToken not found.",
                "received_parameters": list(params.keys()),
            },
        )

    candidates = (
        "exchange_request_token",
        "get_access_token",
        "request_access_token",
        "exchange_token",
    )

    for method_name in candidates:

        method = getattr(broker, method_name, None)

        if method is None:
            continue

        try:

            result = await maybe_await(
                method(request_token)
            )

            connected = await broker_is_connected()

            return {
                "success": True,
                "connected": connected,
                "result": result,
            }

        except Exception as exc:

            logger.exception(
                "Access token exchange failed."
            )

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": str(exc),
                },
            )

    raise HTTPException(
        status_code=501,
        detail=(
            "Access-token exchange method is not "
            "available in broker.py."
        ),
    )


# ============================================================
# BROKER LOGIN DIRECT
# ============================================================

@app.post("/api/5paisa/login")
async def fivepaisa_login_post():
    connected = await broker_login()

    return {
        "success": connected,
        "connected": connected,
        "broker": "5paisa",
    }


# ============================================================
# BROWSER WEBSOCKET
# ============================================================

@app.websocket("/ws")
async def browser_websocket(
    websocket: WebSocket,
):
    """
    Browser-facing WebSocket.

    Actual 5paisa MarketFeedV3 connection is maintained by
    websocket_manager.py.

    This endpoint is for sending live market events to the
    browser and receiving selection/ping messages.
    """

    await websocket.accept()

    logger.info(
        "Browser WebSocket connected."
    )

    # Register browser with websocket manager when supported.
    registered = False

    for method_name in (
        "register_client",
        "add_client",
        "connect_client",
    ):

        method = getattr(
            websocket_manager,
            method_name,
            None,
        )

        if method is None:
            continue

        try:
            await maybe_await(
                method(websocket)
            )

            registered = True
            break

        except Exception as exc:
            logger.warning(
                "Browser registration failed: %s",
                exc,
            )

    try:

        while True:

            message = await websocket.receive_json()

            if not isinstance(message, dict):
                continue

            message_type = (
                message.get("type")
                or message.get("action")
                or ""
            )

            message_type = str(
                message_type
            ).lower()

            # ------------------------------------------------
            # Ping
            # ------------------------------------------------

            if message_type == "ping":

                await websocket.send_json({
                    "type": "pong",
                })

                continue

            # ------------------------------------------------
            # Dashboard selection
            # ------------------------------------------------

            if message_type in {
                "selection",
                "select",
                "dashboard_selection",
            }:

                symbol = (
                    message.get("symbol")
                    or DEFAULT_SYMBOL
                )

                expiry = message.get("expiry")

                try:

                    data = await build_dashboard(
                        symbol=symbol,
                        expiry=expiry,
                    )

                    await websocket.send_json({
                        "type": "dashboard",
                        "data": data,
                    })

                except Exception as exc:

                    await websocket.send_json({
                        "type": "error",
                        "message": str(exc),
                    })

                continue

            # ------------------------------------------------
            # Subscribe
            # ------------------------------------------------

            if message_type == "subscribe":

                instruments = message.get(
                    "instruments",
                    [],
                )

                if not isinstance(
                    instruments,
                    list,
                ):
                    instruments = []

                result = await subscribe_instruments(
                    instruments
                )

                await websocket.send_json({
                    "type": "subscribed",
                    "result": result,
                })

                continue

            # ------------------------------------------------
            # Unknown message
            # ------------------------------------------------

            await websocket.send_json({
                "type": "ack",
                "message": "Message received.",
            })

    except WebSocketDisconnect:

        logger.info(
            "Browser WebSocket disconnected."
        )

    except Exception as exc:

        logger.warning(
            "Browser WebSocket error: %s",
            exc,
        )

    finally:

        if registered:

            for method_name in (
                "unregister_client",
                "remove_client",
                "disconnect_client",
            ):

                method = getattr(
                    websocket_manager,
                    method_name,
                    None,
                )

                if method is None:
                    continue

                try:
                    await maybe_await(
                        method(websocket)
                    )

                    break

                except Exception:
                    continue


# ============================================================
# LEGACY WEBSOCKET ALIAS
# ============================================================

@app.websocket("/api/ws")
async def browser_websocket_alias(
    websocket: WebSocket,
):
    await browser_websocket(websocket)


# ============================================================
# ERROR HANDLER
# ============================================================

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unhandled application error: %s",
        exc,
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
        },
    )


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "Backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
```
