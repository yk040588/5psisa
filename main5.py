from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from Backend.broker import broker
from Backend.instruments import instrument_manager
from Backend.market_data import market_data_manager
from config.settings import settings


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Trading Dashboard",
    description="Custom 5paisa/Xstream trading dashboard",
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# BASE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "Frontend"


# =========================================================
# SUPPORTED SYMBOLS
# =========================================================

SUPPORTED_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS",
]


# =========================================================
# HELPER - SERIALIZE INSTRUMENT
# =========================================================

def serialize_instrument(item):
    if item is None:
        return None

    return {
        "underlying": item.underlying,
        "symbol": item.symbol,
        "exchange": item.exchange,
        "instrument_type": item.instrument_type,
        "expiry": item.expiry,
        "strike": item.strike,
        "option_type": item.option_type,
        "scrip_code": item.broker_token,
        "lot_size": item.lot_size,
        "tick_size": item.tick_size,
        "scrip_data": item.scrip_data,
    }


# =========================================================
# HELPER - EXTRACT LTP
# =========================================================

def extract_ltp(data: Any):

    if data is None:
        return None

    if isinstance(data, (int, float)):
        try:
            value = float(data)

            if value > 0:
                return value

        except Exception:
            pass

        return None

    if isinstance(data, str):

        try:
            value = float(data)

            if value > 0:
                return value

        except Exception:
            pass

        return None

    if isinstance(data, list):

        for item in data:

            result = extract_ltp(item)

            if result is not None:
                return result

        return None

    if isinstance(data, dict):

        preferred_keys = [
            "LastRate",
            "LastTradedPrice",
            "LTP",
            "ltp",
            "LastPrice",
            "last_price",
            "Close",
            "close",
        ]

        for key in preferred_keys:

            if key in data:

                try:
                    value = float(data[key])

                    if value > 0:
                        return value

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

        for value in data.values():

            result = extract_ltp(value)

            if result is not None:
                return result

    return None


# =========================================================
# HELPER - SELECT EXPIRY
# =========================================================

def choose_selected_expiry(
    expiries,
    requested_expiry="",
):

    if not expiries:
        return ""

    values = [
        str(x)
        for x in expiries
        if x
    ]

    if not values:
        return ""

    if requested_expiry:

        requested = str(requested_expiry)

        if requested in values:
            return requested

    return values[0]


# =========================================================
# HELPER - SELECT FUTURE
# =========================================================

def choose_future(
    futures,
    selected_expiry="",
):

    if not futures:
        return None

    if selected_expiry:

        for future in futures:

            if str(future.expiry) == str(
                selected_expiry
            ):
                return future

    return futures[0]


# =========================================================
# HELPER - SELECT OTM OPTIONS
# =========================================================

def choose_option_contracts(
    options,
    future_ltp,
    count,
):

    if not options:
        return []

    valid_options = [
        x
        for x in options
        if x.strike is not None
    ]

    if not valid_options:
        return []

    count = max(1, int(count))

    # -----------------------------------------------------
    # Future LTP available
    # -----------------------------------------------------

    if future_ltp is not None:

        option_type = str(
            valid_options[0].option_type
        ).upper()

        # -------------------------------------------------
        # CALL OTM
        # -------------------------------------------------

        if option_type == "CALL":

            otm = [
                x
                for x in valid_options
                if float(x.strike)
                > float(future_ltp)
            ]

            otm.sort(
                key=lambda x: float(x.strike)
            )

            if otm:
                return otm[:count]

        # -------------------------------------------------
        # PUT OTM
        # -------------------------------------------------

        elif option_type == "PUT":

            otm = [
                x
                for x in valid_options
                if float(x.strike)
                < float(future_ltp)
            ]

            otm.sort(
                key=lambda x: abs(
                    float(x.strike)
                    - float(future_ltp)
                )
            )

            if otm:
                return otm[:count]

    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    valid_options.sort(
        key=lambda x: float(x.strike)
    )

    middle = len(valid_options) // 2

    start = max(
        0,
        middle - count // 2,
    )

    return valid_options[
        start:start + count
    ]


# =========================================================
# 5PAISA LOGIN
# =========================================================

@app.get("/api/5paisa/login")
def fivepaisa_login():

    try:

        login_url = broker.get_oauth_login_url()

        return {
            "status": "ok",
            "login_url": login_url,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# 5PAISA CALLBACK
# =========================================================

@app.get(
    "/api/5paisa/callback",
    response_class=HTMLResponse,
)
def fivepaisa_callback(
    RequestToken: str = "",
    state: str = "",
):

    if not RequestToken:

        return """
        <html>
        <body>
            <h2>5paisa Login Failed</h2>
            <p>RequestToken नहीं मिला.</p>
        </body>
        </html>
        """

    try:

        result = broker.exchange_request_token(
            RequestToken
        )

        return f"""
        <html>
        <body>
            <h2>5paisa Connected Successfully</h2>

            <p>
                Trading Dashboard अब 5paisa
                से connected है.
            </p>

            <p>
                Client Code:
                <b>{result.get("client_code")}</b>
            </p>

            <p>
                आप इस window को बंद कर सकते हैं.
            </p>
        </body>
        </html>
        """

    except Exception as e:

        return f"""
        <html>
        <body>
            <h2>5paisa Connection Failed</h2>
            <pre>{str(e)}</pre>
        </body>
        </html>
        """


# =========================================================
# 5PAISA STATUS
# =========================================================

@app.get("/api/5paisa/status")
def fivepaisa_status():

    return {
        "connected": broker.connected,
        "client_code": broker.client_code,
        "configuration": broker.configuration_status(),
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
async def health():

    return {
        "status": "ok",
        "application": "Trading Dashboard",
        "version": "1.0.0",
    }


# =========================================================
# SYMBOLS
# =========================================================

@app.get("/api/symbols")
async def get_symbols():

    return {
        "symbols": SUPPORTED_SYMBOLS,
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/api/dashboard")
async def dashboard(
    symbol: str = "NIFTY",
    expiry: str = "",
):

    try:

        symbol = symbol.upper().strip()

        if symbol not in SUPPORTED_SYMBOLS:

            return {
                "status": "error",
                "message": f"Unsupported symbol: {symbol}",
            }

        # -------------------------------------------------
        # EXPIRIES
        # -------------------------------------------------

        expiries = instrument_manager.get_expiries(
            symbol
        )

        expiries = [
            str(x)
            for x in expiries
            if x
        ]

        selected_expiry = choose_selected_expiry(
            expiries,
            expiry,
        )

        # -------------------------------------------------
        # FUTURES
        # -------------------------------------------------

        futures = instrument_manager.get_futures(
            symbol
        )

        future = choose_future(
            futures,
            selected_expiry,
        )

        future_data = [
            serialize_instrument(x)
            for x in futures
        ]

        # -------------------------------------------------
        # FUTURE LTP
        # -------------------------------------------------

        future_ltp = None

        if future and broker.connected:

            try:

                quote = broker.get_quote(
                    future.exchange,
                    "D",
                    future.broker_token,
                )

                future_ltp = extract_ltp(quote)

            except Exception as e:

                print(
                    "Future quote error:",
                    e,
                )

        # -------------------------------------------------
        # CALL OPTIONS
        # -------------------------------------------------

        calls = instrument_manager.get_options(
            symbol,
            "CALL",
            selected_expiry
            if selected_expiry
            else None,
        )

        # -------------------------------------------------
        # PUT OPTIONS
        # -------------------------------------------------

        puts = instrument_manager.get_options(
            symbol,
            "PUT",
            selected_expiry
            if selected_expiry
            else None,
        )

        # -------------------------------------------------
        # SELECT OTM CALLS
        # -------------------------------------------------

        calls = choose_option_contracts(
            calls,
            future_ltp,
            settings.OTM_CALL_COUNT,
        )

        # -------------------------------------------------
        # SELECT OTM PUTS
        # -------------------------------------------------

        puts = choose_option_contracts(
            puts,
            future_ltp,
            settings.OTM_PUT_COUNT,
        )

        # -------------------------------------------------
        # SERIALIZE
        # -------------------------------------------------

        call_data = [
            serialize_instrument(x)
            for x in calls
        ]

        put_data = [
            serialize_instrument(x)
            for x in puts
        ]

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return {
            "status": "ok",
            "symbol": symbol,
            "expiry": selected_expiry,
            "expiries": expiries,
            "futures": future_data,
            "calls": call_data,
            "puts": put_data,
            "future": (
                serialize_instrument(future)
                if future
                else None
            ),
            "future_ltp": future_ltp,
            "call_ltp": None,
            "put_ltp": None,
            "smoothed_heikin_ashi": True,
            "buy_sell_enabled": False,
        }

    except Exception as e:

        print(
            "Dashboard error:",
            e,
        )

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# HISTORICAL DATA
# =========================================================

@app.get("/api/historical")
async def historical_data(
    symbol: str = "NIFTY",
    instrument_type: str = "FUTURE",
    interval: str = "5m",
    start_date: str = "",
    end_date: str = "",
    expiry: str = "",
    strike: float | None = None,
    option_type: str = "",
    scrip_code: int | None = None,
    refresh: bool = False,
):

    try:

        symbol = symbol.upper().strip()

        instrument_type = (
            instrument_type.upper().strip()
        )

        option_type = (
            option_type.upper().strip()
        )

        if symbol not in SUPPORTED_SYMBOLS:

            return {
                "status": "error",
                "message": f"Unsupported symbol: {symbol}",
            }

        # -------------------------------------------------
        # SERVER SUPPORTED INTERVALS
        # -------------------------------------------------

        supported_intervals = [
            "1m",
            "5m",
            "10m",
            "15m",
            "30m",
            "60m",
            "1d",
        ]

        if interval not in supported_intervals:

            return {
                "status": "error",
                "message": (
                    f"Unsupported server interval: {interval}"
                ),
            }

        # -------------------------------------------------
        # HISTORICAL DATA
        # -------------------------------------------------

        candles = market_data_manager.get_candles(
            symbol=symbol,
            instrument_type=instrument_type,
            interval=interval,
            start_date=(
                start_date
                if start_date
                else None
            ),
            end_date=(
                end_date
                if end_date
                else None
            ),
            expiry=(
                expiry
                if expiry
                else None
            ),
            strike=strike,
            option_type=(
                option_type
                if option_type
                else None
            ),
            refresh=refresh,
        )

        return {
            "status": "ok",
            "symbol": symbol,
            "instrument_type": instrument_type,
            "interval": interval,
            "expiry": expiry,
            "strike": strike,
            "option_type": option_type,
            "candles": candles,
        }

    except Exception as e:

        print(
            "Historical data error:",
            e,
        )

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# MARKET DATA STATUS
# =========================================================

@app.get("/api/market-data/status")
async def market_data_status():

    try:

        return market_data_manager.status()

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# INSTRUMENT MASTER STATUS
# =========================================================

@app.get("/api/instruments/status")
async def instruments_status():

    try:

        return instrument_manager.status()

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# UPDATE SCRIP MASTER
# =========================================================

@app.post("/api/instruments/update")
async def instruments_update():

    try:

        total = instrument_manager.update()

        return {
            "status": "ok",
            "total": total,
            "message": (
                "5paisa Scrip Master updated successfully."
            ),
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# EXPIRIES
# =========================================================

@app.get(
    "/api/instruments/{symbol}/expiries"
)
async def instrument_expiries(
    symbol: str,
):

    try:

        symbol = symbol.upper().strip()

        expiries = instrument_manager.get_expiries(
            symbol
        )

        return {
            "symbol": symbol,
            "expiries": expiries,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# FUTURES
# =========================================================

@app.get(
    "/api/instruments/{symbol}/futures"
)
async def instrument_futures(
    symbol: str,
):

    try:

        symbol = symbol.upper().strip()

        futures = instrument_manager.get_futures(
            symbol
        )

        return {
            "symbol": symbol,
            "futures": [
                serialize_instrument(x)
                for x in futures
            ],
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# OPTIONS
# =========================================================

@app.get(
    "/api/instruments/{symbol}/options"
)
async def instrument_options(
    symbol: str,
    expiry: str = "",
    option_type: str = "",
):

    try:

        symbol = symbol.upper().strip()

        options = instrument_manager.get_options(
            symbol,
            option_type if option_type else None,
            expiry if expiry else None,
        )

        return {
            "symbol": symbol,
            "expiry": expiry,
            "option_type": (
                option_type.upper()
                if option_type
                else ""
            ),
            "options": [
                serialize_instrument(x)
                for x in options
            ],
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# STRIKES
# =========================================================

@app.get(
    "/api/instruments/{symbol}/strikes"
)
async def instrument_strikes(
    symbol: str,
    expiry: str = "",
    option_type: str = "",
):

    try:

        symbol = symbol.upper().strip()

        strikes = instrument_manager.get_strikes(
            symbol,
            expiry if expiry else None,
            option_type if option_type else None,
        )

        return {
            "symbol": symbol,
            "expiry": expiry,
            "option_type": (
                option_type.upper()
                if option_type
                else ""
            ),
            "strikes": strikes,
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# =========================================================
# WEBSOCKET
# =========================================================

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):

    await websocket.accept()

    await websocket.send_json(
        {
            "type": "connection",
            "status": "connected",
            "message": (
                "Trading dashboard WebSocket connected"
            ),
        }
    )

    try:

        while True:

            message = await websocket.receive_json()

            await websocket.send_json(
                {
                    "type": "ack",
                    "data": message,
                }
            )

    except Exception:

        pass


# =========================================================
# FRONTEND
# =========================================================

if FRONTEND_DIR.exists():

    app.mount(
        "/",
        StaticFiles(
            directory=str(FRONTEND_DIR),
            html=True,
        ),
        name="frontend",
    )
