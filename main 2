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
            data[field] = getattr(instrument, field)

    if hasattr(instrument, "broker_token"):
        data["scrip_code"] = getattr(instrument, "broker_token")

    return data


def extract_ltp(response):
    if response is None:
        return None

    if isinstance(response, (int, float)):
        return float(response)

    if isinstance(response, dict):

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

            if isinstance(value, dict):
                result = extract_ltp(value)

                if result is not None:
                    return result

            if isinstance(value, list):

                for item in value:
                    result = extract_ltp(item)

                    if result is not None:
                        return result

    if isinstance(response, list):

        for item in response:
            result = extract_ltp(item)

            if result is not None:
                return result

    return None


def choose_selected_expiry(
    symbol: str,
    expiry: Optional[str] = None,
):
    expiries = instrument_manager.get_expiries(symbol)

    if not expiries:
        return None

    if expiry and expiry in expiries:
        return expiry

    return expiries[0]


def choose_future(
    symbol: str,
    expiry: Optional[str] = None,
):
    futures = instrument_manager.get_futures(symbol)

    if not futures:
        return None

    if expiry:

        for future in futures:

            if str(getattr(future, "expiry", "")) == str(expiry):
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
                if getattr(option, "strike", None) is not None
                and float(option.strike) > float(future_ltp)
            ]

            if otm:
                valid_options = otm

        elif option_type == "PUT":

            otm = [
                option
                for option in valid_options
                if getattr(option, "strike", None) is not None
                and float(option.strike) < float(future_ltp)
            ]

            if otm:
                valid_options = otm

    valid_options.sort(
        key=lambda x: float(getattr(x, "strike", 0))
    )

    if not valid_options:
        return []

    middle = len(valid_options) // 2

    start = max(0, middle - count // 2)

    return valid_options[start:start + count]


def get_quote_for_instrument(instrument):

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
            f"[QUOTE ERROR] "
            f"{getattr(instrument, 'symbol', '')}: "
            f"{exc}"
        )

        return None


@app.get("/")
async def root():

    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend index.html not found",
        )

    return FileResponse(index_file)


@app.get("/api/health")
async def health():

    return {
        "status": "ok",
        "service": "5paisa-trading-dashboard",
        "broker_connected": broker.is_connected(),
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
        "login_url": broker.get_login_url(),
    }


@app.get("/api/5paisa/login")
async def fivepaisa_login():

    return {
        "login_url": broker.get_login_url(),
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

        result = broker.exchange_token(token)

        return {
            "success": True,
            "result": result,
        }

    except Exception as exc:

        return {
            "success": False,
            "message": str(exc),
        }


@app.get("/api/5paisa/status")
async def fivepaisa_status():

    return broker.status()


@app.get("/api/instruments/status")
async def instruments_status():

    return instrument_manager.status()


@app.post("/api/instruments/update")
async def instruments_update():

    result = instrument_manager.update()

    return result


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

    futures_data = instrument_manager.get_futures(symbol)

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

    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    return {
        "symbol": symbol,
        "expiries": instrument_manager.get_expiries(symbol),
    }


@app.get("/api/instruments/options")
async def options(
    symbol: str = Query("NIFTY"),
    expiry: str = Query(...),
    option_type: str = Query(...),
):

    symbol = symbol.upper()
    option_type = option_type.upper()

    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    if option_type not in ["CALL", "PUT"]:
        raise HTTPException(
            status_code=400,
            detail="option_type must be CALL or PUT",
        )

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
        symbol=symbol,
        expiry=expiry,
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
        symbol=symbol,
        expiry=selected_expiry,
    )

    future_ltp = None

    if future is not None and broker.is_connected():

        future_ltp = get_quote_for_instrument(
            future
        )

    calls = choose_option_contracts(
        symbol=symbol,
        expiry=selected_expiry,
        future_ltp=future_ltp,
        option_type="CALL",
        count=5,
    )

    puts = choose_option_contracts(
        symbol=symbol,
        expiry=selected_expiry,
        future_ltp=future_ltp,
        option_type="PUT",
        count=5,
    )

    call_ltp = None
    put_ltp = None

    if calls and broker.is_connected():

        call_ltp = get_quote_for_instrument(
            calls[0]
        )

    if puts and broker.is_connected():

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

    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol: {symbol}",
        )

    if interval not in {
        "1m",
        "5m",
        "10m",
        "15m",
        "30m",
        "60m",
        "1d",
    }:
        raise HTTPException(
            status_code=400,
            detail="Unsupported historical interval",
        )

    try:

        candles = market_data_manager.get_candles(
            symbol=symbol,
            instrument_type=instrument_type,
            interval=interval,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            expiry=expiry if expiry else None,
            strike=strike,
            option_type=option_type
            if option_type
            else None,
            refresh=refresh,
        )

        return {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "interval": interval,
            "candles": candles,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@app.get("/api/market-data/status")
async def market_data_status():

    return market_data_manager.status()


async def websocket_connect(websocket: WebSocket):

    if hasattr(websocket_manager, "connect"):
        return await websocket_manager.connect(
            websocket
        )

    await websocket.accept()


async def websocket_disconnect(websocket: WebSocket):

    if hasattr(websocket_manager, "disconnect"):
        result = websocket_manager.disconnect(
            websocket
        )

        if hasattr(result, "__await__"):
            await result


async def websocket_send(
    websocket: WebSocket,
    data,
):

    if hasattr(websocket_manager, "send_personal_message"):

        result = websocket_manager.send_personal_message(
            data,
            websocket,
        )

        if hasattr(result, "__await__"):
            await result

        return

    await websocket.send_json(data)


def websocket_selection_message(message):

    if not isinstance(message, dict):
        return None

    if message.get("type") in [
        "selection",
        "subscribe",
        "select",
    ]:
        return message

    if "symbol" in message:
        return message

    return None


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):

    await websocket_connect(websocket)

    current_selection = {
        "symbol": "NIFTY",
        "expiry": None,
        "timeframe": "5m",
        "future": None,
        "call": None,
        "put": None,
    }

    try:

        await websocket_send(
            websocket,
            {
                "type": "connection",
                "status": "connected",
            },
        )

        while True:

            message = await websocket.receive_json()

            selection = websocket_selection_message(
                message
            )

            if selection is None:

                await websocket_send(
                    websocket,
                    {
                        "type": "ack",
                        "status": "received",
                    },
                )

                continue

            current_selection.update(
                {
                    key: value
                    for key, value in selection.items()
                    if value is not None
                }
            )

            symbol = str(
                current_selection.get(
                    "symbol",
                    "NIFTY",
                )
            ).upper()

            expiry = current_selection.get(
                "expiry"
            )

            future = current_selection.get(
                "future"
            )

            call = current_selection.get(
                "call"
            )

            put = current_selection.get(
                "put"
            )

            manager_updated = False

            # New websocket manager API
            if hasattr(
                websocket_manager,
                "set_selection",
            ):

                result = websocket_manager.set_selection(
                    websocket,
                    current_selection,
                )

                if hasattr(result, "__await__"):
                    await result

                manager_updated = True

            elif hasattr(
                websocket_manager,
                "update_selection",
            ):

                result = websocket_manager.update_selection(
                    websocket,
                    current_selection,
                )

                if hasattr(result, "__await__"):
                    await result

                manager_updated = True

            elif hasattr(
                websocket_manager,
                "subscribe",
            ):

                result = websocket_manager.subscribe(
                    websocket,
                    current_selection,
                )

                if hasattr(result, "__await__"):
                    await result

                manager_updated = True

            await websocket_send(
                websocket,
                {
                    "type": "selection",
                    "status": "updated",
                    "manager_updated": manager_updated,
                    "selection": {
                        "symbol": symbol,
                        "expiry": expiry,
                        "timeframe": current_selection.get(
                            "timeframe",
                            "5m",
                        ),
                        "future": future,
                        "call": call,
                        "put": put,
                    },
                },
            )

    except WebSocketDisconnect:

        await websocket_disconnect(
            websocket
        )

    except Exception as exc:

        print(
            f"[WEBSOCKET ERROR] {exc}"
        )

        try:
            await websocket_disconnect(
                websocket
            )
        except Exception:
            pass


@app.on_event("startup")
async def startup_event():

    print(
        "========================================"
    )
    print(
        "5paisa Trading Dashboard started"
    )
    print(
        "========================================"
    )

    try:

        if hasattr(
            websocket_manager,
            "start",
        ):

            result = websocket_manager.start()

            if hasattr(result, "__await__"):
                await result

        elif hasattr(
            websocket_manager,
            "start_market_data_loop",
        ):

            result = (
                websocket_manager
                .start_market_data_loop()
            )

            if hasattr(result, "__await__"):
                await result

    except Exception as exc:

        print(
            f"[WEBSOCKET START ERROR] {exc}"
        )


@app.on_event("shutdown")
async def shutdown_event():

    try:

        if hasattr(
            websocket_manager,
            "stop",
        ):

            result = websocket_manager.stop()

            if hasattr(result, "__await__"):
                await result

        elif hasattr(
            websocket_manager,
            "stop_market_data_loop",
        ):

            result = (
                websocket_manager
                .stop_market_data_loop()
            )

            if hasattr(result, "__await__"):
                await result

    except Exception as exc:

        print(
            f"[WEBSOCKET STOP ERROR] {exc}"
        )


if FRONTEND_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(
            directory=FRONTEND_DIR
        ),
        name="static",
    )
