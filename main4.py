from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
from typing import Optional

from Backend.broker import broker
from Backend.instruments import instrument_manager
from Backend.market_data import market_data_manager


app = FastAPI(
    title="Trading Dashboard",
    description="Custom 5paisa/Xstream trading dashboard",
    version="1.0.0"
)


# =========================================================
# 5PAISA LOGIN
# =========================================================

@app.get("/api/5paisa/login")
def fivepaisa_login():

    try:

        login_url = (
            broker.get_oauth_login_url()
        )

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
    response_class=HTMLResponse
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

        result = (
            broker.exchange_request_token(
                RequestToken
            )
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

        "connected":
            broker.connected,

        "client_code":
            broker.client_code,

        "configuration":
            broker.configuration_status(),
    }


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
# DIRECTORIES
# =========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent.parent
)

FRONTEND_DIR = (
    BASE_DIR / "Frontend"
)


# =========================================================
# SYMBOLS
# =========================================================

SUPPORTED_SYMBOLS = [

    "NIFTY",

    "BANKNIFTY",

    "SENSEX",

    "CRUDEOIL",

    "NATURALGAS",
]


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
async def health():

    return {

        "status":
            "ok",

        "application":
            "Trading Dashboard",

        "version":
            "1.0.0"
    }


# =========================================================
# SYMBOLS
# =========================================================

@app.get("/api/symbols")
async def get_symbols():

    return {

        "symbols":
            SUPPORTED_SYMBOLS
    }


# =========================================================
# DASHBOARD
# =========================================================

@app.get("/api/dashboard")
async def dashboard():

    return {

        "future_chart":
            True,

        "call_chart":
            True,

        "put_chart":
            True,

        "smoothed_heikin_ashi":
            True,

        "symbols":
            SUPPORTED_SYMBOLS,

        "buy_sell_enabled":
            False
    }


# =========================================================
# INSTRUMENT STATUS
# =========================================================

@app.get("/api/instruments/status")
async def instruments_status():

    try:

        return (
            instrument_manager.status()
        )

    except Exception as e:

        return {

            "status":
                "error",

            "message":
                str(e)
        }


# =========================================================
# UPDATE SCRIP MASTER
# =========================================================

@app.post("/api/instruments/update")
async def instruments_update():

    try:

        total = (
            instrument_manager.update()
        )

        return {

            "status":
                "ok",

            "total":
                total,

            "message":
                "5paisa Scrip Master updated successfully."
        }

    except Exception as e:

        return {

            "status":
                "error",

            "message":
                str(e)
        }


# =========================================================
# EXPIRIES
# =========================================================

@app.get(
    "/api/instruments/{symbol}/expiries"
)
async def instrument_expiries(
    symbol: str
):

    try:

        return {

            "symbol":
                symbol.upper(),

            "expiries":
                instrument_manager
                .get_expiries(symbol)
        }

    except Exception as e:

        return {

            "status":
                "error",

            "message":
                str(e)
        }


# =========================================================
# FUTURES
# =========================================================

@app.get(
    "/api/instruments/{symbol}/futures"
)
async def instrument_futures(
    symbol: str
):

    try:

        futures = (
            instrument_manager
            .get_futures(symbol)
        )

        return {

            "symbol":
                symbol.upper(),

            "futures": [

                {

                    "underlying":
                        x.underlying,

                    "symbol":
                        x.symbol,

                    "exchange":
                        x.exchange,

                    "instrument_type":
                        x.instrument_type,

                    "expiry":
                        x.expiry,

                    "scrip_code":
                        x.broker_token,

                    "lot_size":
                        x.lot_size,

                    "tick_size":
                        x.tick_size,

                    "scrip_data":
                        x.scrip_data,
                }

                for x in futures
            ]
        }

    except Exception as e:

        return {

            "status":
                "error",

            "message":
                str(e)
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

        options = (
            instrument_manager
            .get_options(

                symbol,

                option_type
                if option_type
                else None,

                expiry
                if expiry
                else None,
            )
        )

        return {

            "symbol":
                symbol.upper(),

            "expiry":
                expiry,

            "option_type":
                option_type.upper(),

            "options": [

                {

                    "underlying":
                        x.underlying,

                    "symbol":
                        x.symbol,

                    "exchange":
                        x.exchange,

                    "instrument_type":
                        x.instrument_type,

                    "expiry":
                        x.expiry,

                    "strike":
                        x.strike,

                    "option_type":
                        x.option_type,

                    "scrip_code":
                        x.broker_token,

                    "lot_size":
                        x.lot_size,

                    "tick_size":
                        x.tick_size,

                    "scrip_data":
                        x.scrip_data,
                }

                for x in options
            ]
        }

    except Exception as e:

        return {

            "status":
                "error",

            "message":
                str(e)
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

        strikes = (
            instrument_manager
            .get_strikes(

                symbol,

                expiry
                if expiry
                else None,

                option_type
                if option_type
                else None,
            )
        )

        return {

            "symbol":
                symbol.upper(),

            "expiry":
                expiry,

            "option_type":
                option_type.upper(),

            "strikes":
                strikes
        }

    except Exception as e:

        return {

            "status":
                "error",

            "message":
                str(e)
        }


# =========================================================
# MARKET DATA STATUS
# =========================================================

@app.get(
    "/api/market-data/status"
)
async def market_data_status():

    return (
        market_data_manager.status()
    )


# =========================================================
# HISTORICAL DATA
# =========================================================

@app.get(
    "/api/historical"
)
async def historical_data(

    symbol: str,

    instrument_type: str,

    interval: str = "5m",

    start_date: Optional[str] = None,

    end_date: Optional[str] = None,

    expiry: Optional[str] = None,

    option_type: Optional[str] = None,

    strike: Optional[float] = None,

    refresh: bool = False,
):

    try:

        result = (
            market_data_manager
            .get_candles(

                symbol=symbol,

                instrument_type=
                    instrument_type,

                interval=interval,

                start_date=start_date,

                end_date=end_date,

                expiry=expiry,

                option_type=option_type,

                strike=strike,

                refresh=refresh,
            )
        )

        return result

    except Exception as e:

        return {

            "status":
                "error",

            "message":
                str(e)
        }


# =========================================================
# WEBSOCKET
# =========================================================

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):

    await websocket.accept()

    await websocket.send_json({

        "type":
            "connection",

        "status":
            "connected",

        "message":
            "Trading dashboard WebSocket connected"
    })

    try:

        while True:

            message = (
                await websocket
                .receive_json()
            )

            await websocket.send_json({

                "type":
                    "ack",

                "data":
                    message
            })

    except Exception:

        pass


# =========================================================
# FRONTEND
# =========================================================

if FRONTEND_DIR.exists():

    app.mount(

        "/",

        StaticFiles(

            directory=
                str(FRONTEND_DIR),

            html=True
        ),

        name="frontend"
    )
