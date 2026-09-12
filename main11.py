from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from Backend.broker import broker
from Backend.instruments import instrument_manager
from Backend.market_data import market_data_manager
from Backend.websocket_manager import websocket_manager


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "Frontend"


app = FastAPI(
    title="5paisa Trading Dashboard",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SUPPORTED_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS",
]


SUPPORTED_TIMEFRAMES = [
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
    "1d",
]


def serialize_instrument(instrument):

    if instrument is None:
        return None

    data = {}

    for field in [
        "underlying",
        "symbol",
        "exchange",
        "instrument_type",
        "expiry",
        "strike",
        "option_type",
        "broker_token",
        "lot_size",
        "tick_size",
        "scrip_code",
        "scrip_data",
    ]:

        if hasattr(instrument, field):
            data[field] = getattr(
                instrument,
                field,
            )

    if hasattr(instrument, "broker_token"):
        data["scrip_code"] = getattr(
            instrument,
            "broker_token",
        )

    return data


def extract_ltp(response):

    if response is None:
        return None

    if isinstance(
        response,
        (int, float),
    ):
        return float(response)

    if isinstance(
        response,
        dict,
    ):

        for key in [
            "LastRate",
            "last_rate",
            "LTP",
            "ltp",
            "LastPrice",
            "last_price",
            "Close",
            "close",
        ]:

            value = response.get(key)

            if value is not None:

                try:
                    return float(value)
                except Exception:
                    pass

        for value in response.values():

            result = extract_ltp(value)

            if result is not None:
                return result

    if isinstance(
        response,
        list,
    ):

        for item in response:

            result = extract_ltp(item)

            if result is not None:
                return result

    return None


def choose_selected_expiry(
    symbol: str,
    expiry: Optional[str] = None,
):

    expiries = instrument_manager.get_expiries(
        symbol
    )

    if not expiries:
        return None

    if expiry and expiry in expiries:
        return expiry

    return expiries[0]


def choose_future(
    symbol: str,
    expiry: Optional[str] = None,
):

    futures = instrument_manager.get_futures(
        symbol
    )

    if not futures:
        return None

    if expiry:

        for future in futures:

            if str(
                getattr(
                    future,
                    "expiry",
                    "",
                )
            ) == str(expiry):

                return future

    return futures[0]


def choose_option_contracts(
    symbol: str,
    expiry: str,
    future_ltp: Optional[float],
    option_type: str,
    count: int = 5,
):

    options = instrument_manager.get_options(
        symbol=symbol,
        expiry=expiry,
        option_type=option_type,
    )

    if not options:
        return []

    valid_options = list(options)

    if future_ltp is not None:

        if option_type == "CALL":

            otm = [
                option
                for option in valid_options
                if getattr(
                    option,
                    "strike",
                    None,
                ) is not None
                and float(option.strike)
                > float(future_ltp)
            ]

            if otm:
                valid_options = otm

        elif option_type == "PUT":

            otm = [
                option
                for option in valid_options
                if getattr(
                    option,
                    "strike",
                    None,
                ) is not None
                and float(option.strike)
                < float(future_ltp)
            ]

            if otm:
                valid_options = otm

    valid_options.sort(
        key=lambda x: float(
            getattr(
                x,
                "strike",
                0,
            )
        )
    )

    if not valid_options:
        return []

    middle = len(valid_options) // 2

    start = max(
        0,
        middle - count // 2,
    )

    return valid_options[
        start:start + count
    ]


def get_quote_for_instrument(
    instrument,
):

    if instrument is None:
        return None

    try:

        scrip_code = getattr(
            instrument,
            "broker_token",
            None,
        )

        if scrip_code is None:

            scrip_code = getattr(
                instrument,
                "scrip_code",
                None,
            )

        if scrip_code is None:
            return None

        exchange = getattr(
            instrument,
            "exchange",
            None,
        )

        if not exchange:
            return None

        response = broker.get_quote(
            exchange=exchange,
            exchange_type="D",
            scrip_code=int(scrip_code),
        )

        return extract_ltp(response)

    except Exception as exc:

        print(
            f"[QUOTE ERROR] {exc}"
        )

        return None


@app.get("/")
async def root():

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get("/api/health")
async def health():

    return {
        "status": "ok",
        "service": "5paisa-trading-dashboard",
        "websocket": True,
    }


@app.get("/api/symbols")
async def symbols():

    return {
        "symbols": SUPPORTED_SYMBOLS,
        "timeframes": SUPPORTED_TIMEFRAMES,
    }


@app.get("/api/auth/login")
async def auth_login():

    return {
        "login_url": broker.get_login_url()
    }


@app.get("/api/5paisa/login")
async def fivepaisa_login():

    return {
        "login_url": broker.get_login_url()
    }


@app.get("/api/5paisa/callback")
async def fivepaisa_callback(
    code: Optional[str] = None,
    RequestToken: Optional[str] = None,
):

    token = code or RequestToken

    if not token:

        return {
            "success": False,
            "message": "Authorization token not received",
        }

    try:

        result = broker.exchange_token(
            token
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


@app.get("/api/instruments/status")
async def instruments_status():

    return instrument_manager.status()


@app.post("/api/instruments/update")
async def instruments_update():

    return instrument_manager.update()


@app.get("/api/instruments/futures")
async def futures(
    symbol: str = Query("NIFTY"),
):

    symbol = symbol.upper()

    if symbol not in SUPPORTED_SYMBOLS:

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    futures_data = instrument_manager.get_futures(
        symbol
    )

    return {
        "symbol": symbol,
        "futures": [
            serialize_instrument(item)
            for item in futures_data
        ],
    }


@app.get("/api/instruments/expiries")
async def expiries(
    symbol: str = Query("NIFTY"),
):

    symbol = symbol.upper()

    return {
        "symbol": symbol,
        "expiries": instrument_manager.get_expiries(
            symbol
        ),
    }


@app.get("/api/instruments/options")
async def options(
    symbol: str = Query("NIFTY"),
    expiry: str = Query(...),
    option_type: str = Query(...),
):

    symbol = symbol.upper()
    option_type = option_type.upper()

    options_data = instrument_manager.get_options(
        symbol=symbol,
        expiry=expiry,
        option_type=option_type,
    )

    return {
        "symbol": symbol,
        "expiry": expiry,
        "option_type": option_type,
        "options": [
            serialize_instrument(item)
            for item in options_data
        ],
    }


@app.get("/api/dashboard")
async def dashboard(
    symbol: str = Query("NIFTY"),
    expiry: Optional[str] = Query(None),
):

    symbol = symbol.upper()

    if symbol not in SUPPORTED_SYMBOLS:

        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    selected_expiry = choose_selected_expiry(
        symbol,
        expiry,
    )

    if not selected_expiry:

        return {
            "symbol": symbol,
            "expiry": None,
            "futures": [],
            "calls": [],
            "puts": [],
            "future": None,
            "call": None,
            "put": None,
            "future_ltp": None,
            "call_ltp": None,
            "put_ltp": None,
            "smoothed_heikin_ashi": True,
            "buy_sell_enabled": False,
        }

    future = choose_future(
        symbol,
        selected_expiry,
    )

    future_ltp = None

    if future:

        future_ltp = get_quote_for_instrument(
            future
        )

    calls = choose_option_contracts(
        symbol,
        selected_expiry,
        future_ltp,
        "CALL",
        5,
    )

    puts = choose_option_contracts(
        symbol,
        selected_expiry,
        future_ltp,
        "PUT",
        5,
    )

    call_ltp = None
    put_ltp = None

    if calls:

        call_ltp = get_quote_for_instrument(
            calls[0]
        )

    if puts:

        put_ltp = get_quote_for_instrument(
            puts[0]
        )

    return {
        "symbol": symbol,
        "expiry": selected_expiry,

        "expiries": instrument_manager.get_expiries(
            symbol
        ),

        "futures": [
            serialize_instrument(item)
            for item in instrument_manager.get_futures(
                symbol
            )
        ],

        "calls": [
            serialize_instrument(item)
            for item in calls
        ],

        "puts": [
            serialize_instrument(item)
            for item in puts
        ],

        "future": serialize_instrument(
            future
        ),

        "call": (
            serialize_instrument(calls[0])
            if calls
            else None
        ),

        "put": (
            serialize_instrument(puts[0])
            if puts
            else None
        ),

        "future_ltp": future_ltp,
        "call_ltp": call_ltp,
        "put_ltp": put_ltp,

        "smoothed_heikin_ashi": True,
        "buy_sell_enabled": False,
    }


@app.get("/api/historical")
async def historical(
    symbol: str = Query("NIFTY"),
    instrument_type: str = Query("FUTURE"),
    interval: str = Query("5m"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    expiry: Optional[str] = Query(None),
    strike: Optional[float] = Query(None),
    option_type: Optional[str] = Query(None),
    refresh: bool = Query(False),
    scrip_code: Optional[int] = Query(None),
):

    symbol = symbol.upper()
    instrument_type = instrument_type.upper()

    allowed = {
        "1m",
        "5m",
        "10m",
        "15m",
        "30m",
        "60m",
        "1d",
    }

    if interval not in allowed:

        raise HTTPException(
            status_code=400,
            detail="Unsupported historical interval",
        )

    candles = market_data_manager.get_candles(
        symbol=symbol,
        instrument_type=instrument_type,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        refresh=refresh,
    )

    return {
        "symbol": symbol,
        "instrument_type": instrument_type,
        "interval": interval,
        "candles": candles,
    }


@app.get("/api/market-data/status")
async def market_data_status():

    return market_data_manager.status()


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):

    await websocket_manager.connect(
        websocket
    )

    try:

        await websocket.send_json(
            {
                "type": "connection",
                "status": "connected",
            }
        )

        while True:

            message = await websocket.receive_json()

            if not isinstance(
                message,
                dict,
            ):
                continue

            selection = message

            if message.get("type") in [
                "selection",
                "subscribe",
                "select",
            ]:

                selection = {
                    key: value
                    for key, value in message.items()
                    if key != "type"
                }

            websocket_manager.set_selection(
                websocket,
                selection,
            )

            await websocket.send_json(
                {
                    "type": "ack",
                    "status": "selection_updated",
                }
            )

    except WebSocketDisconnect:

        websocket_manager.disconnect(
            websocket
        )

    except Exception as exc:

        print(
            f"[WS ERROR] {exc}"
        )

        websocket_manager.disconnect(
            websocket
        )


@app.on_event("startup")
async def startup_event():

    print("========================================")
    print("5paisa Trading Dashboard started")
    print("========================================")

    websocket_manager.start()


@app.on_event("shutdown")
async def shutdown_event():

    await websocket_manager.stop()


# IMPORTANT:
# index.html requests /app.js, /charts.js, etc.
# So Frontend must be available directly from root.
#
# API and WebSocket routes are declared above this mount.
app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True,
    ),
    name="frontend",
)
