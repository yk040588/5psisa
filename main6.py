#main.py

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect
)

from fastapi.responses import (
    FileResponse,
    JSONResponse
)

from fastapi.staticfiles import StaticFiles

from Backend.instruments import (
    instrument_manager
)

from Backend.market_data import (
    market_data_manager
)

from Backend.websocket_manager import (
    websocket_manager
)


BASE_DIR = (
    Path(__file__).resolve().parent.parent
)

INDEX_FILE = (
    BASE_DIR / "index.html"
)

CSS_DIR = (
    BASE_DIR / "css"
)

JS_DIR = (
    BASE_DIR / "js"
)


# -------------------------------------------------
# LIFESPAN
# -------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    print(
        "Starting 5paisa Trading Dashboard..."
    )

    try:

        instrument_manager.update()

    except Exception as error:

        print(
            "Instrument update error:",
            error
        )

    await websocket_manager.start()

    try:

        yield

    finally:

        await websocket_manager.stop()


# -------------------------------------------------
# APP
# -------------------------------------------------

app = FastAPI(
    title="5paisa Trading Dashboard",
    version="1.0.0",
    lifespan=lifespan
)


# -------------------------------------------------
# STATIC FILES
# -------------------------------------------------

if CSS_DIR.exists():

    app.mount(
        "/css",
        StaticFiles(
            directory=str(CSS_DIR)
        ),
        name="css"
    )


if JS_DIR.exists():

    app.mount(
        "/js",
        StaticFiles(
            directory=str(JS_DIR)
        ),
        name="js"
    )


# -------------------------------------------------
# HEALTH
# -------------------------------------------------

@app.get("/api/health")
async def health():

    return {
        "status": "ok",
        "service": (
            "5paisa Trading Dashboard"
        )
    }


# -------------------------------------------------
# STATUS
# -------------------------------------------------

@app.get("/api/status")
async def status():

    return {
        "broker": {
            "connected": (
                instrument_manager.loaded
            )
        },
        "instruments": (
            instrument_manager.status()
        ),
        "websocket": {
            "running": (
                websocket_manager.running
            ),
            "clients": len(
                websocket_manager.clients
            )
        }
    }


# -------------------------------------------------
# SYMBOLS
# -------------------------------------------------

@app.get("/api/symbols")
async def symbols():

    return {
        "symbols": [
            "NIFTY",
            "BANKNIFTY",
            "SENSEX",
            "CRUDEOIL",
            "NATURALGAS"
        ]
    }


# -------------------------------------------------
# EXPIRIES
# -------------------------------------------------

@app.get("/api/expiries")
async def expiries(
    symbol: str = Query("NIFTY")
):

    return {
        "symbol": symbol,
        "expiries": (
            instrument_manager
            .get_expiries(symbol.upper())
        )
    }


# -------------------------------------------------
# FUTURES
# -------------------------------------------------

@app.get("/api/futures")
async def futures(
    symbol: str = Query("NIFTY"),
    expiry: str | None = Query(None)
):

    data = (
        instrument_manager
        .get_futures(
            symbol.upper(),
            expiry
        )
    )

    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "futures": [
            item.to_dict()
            for item in data
        ]
    }


# -------------------------------------------------
# OPTIONS
# -------------------------------------------------

@app.get("/api/options")
async def options(
    symbol: str = Query("NIFTY"),
    expiry: str | None = Query(None),
    option_type: str | None = Query(None)
):

    data = (
        instrument_manager
        .get_options(
            symbol.upper(),
            expiry,
            option_type
        )
    )

    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "option_type": option_type,
        "options": [
            item.to_dict()
            for item in data
        ]
    }


# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------

@app.get("/api/dashboard")
async def dashboard(
    symbol: str = Query("NIFTY"),
    expiry: str | None = Query(None)
):

    symbol = symbol.upper()

    expiry_list = (
        instrument_manager
        .get_expiries(symbol)
    )

    if not expiry and expiry_list:

        expiry = expiry_list[0]

    futures = (
        instrument_manager
        .get_futures(
            symbol,
            expiry
        )
    )

    calls = (
        instrument_manager
        .get_options(
            symbol,
            expiry,
            "CE"
        )
    )

    puts = (
        instrument_manager
        .get_options(
            symbol,
            expiry,
            "PE"
        )
    )

    future = (
        futures[0].to_dict()
        if futures
        else None
    )

    call_data = [
        item.to_dict()
        for item in calls
    ]

    put_data = [
        item.to_dict()
        for item in puts
    ]

    return {
        "symbol": symbol,
        "expiry": expiry,
        "expiries": expiry_list,
        "future": future,
        "futures": [
            item.to_dict()
            for item in futures
        ],
        "calls": call_data,
        "puts": put_data
    }


# -------------------------------------------------
# HISTORICAL
# -------------------------------------------------

@app.get("/api/historical")
async def historical(
    symbol: str = Query("NIFTY"),
    instrument_type: str = Query("FUTURE"),
    timeframe: str = Query("5m"),
    interval: str | None = Query(None),
    expiry: str | None = Query(None),
    strike: float | None = Query(None),
    option_type: str | None = Query(None)
):

    if interval:
        timeframe = _convert_interval(
            interval
        )

    candles = (
        market_data_manager
        .get_candles(
            symbol=symbol.upper(),
            instrument_type=(
                instrument_type.upper()
            ),
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            timeframe=timeframe
        )
    )

    return {
        "symbol": symbol.upper(),
        "instrument_type": (
            instrument_type.upper()
        ),
        "timeframe": timeframe,
        "candles": candles
    }


def _convert_interval(
    interval: str
):

    mapping = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "1h",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d"
    }

    return mapping.get(
        interval,
        "5m"
    )


# -------------------------------------------------
# INSTRUMENT STATUS
# -------------------------------------------------

@app.get("/api/instruments/status")
async def instrument_status():

    return (
        instrument_manager.status()
    )


# -------------------------------------------------
# INSTRUMENT UPDATE
# -------------------------------------------------

@app.post("/api/instruments/update")
async def instrument_update():

    success = (
        instrument_manager.update()
    )

    return {
        "success": success,
        "status": (
            instrument_manager.status()
        )
    }


# -------------------------------------------------
# WEBSOCKET
# -------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):

    await websocket_manager.connect(
        websocket
    )

    try:

        while True:

            message = (
                await websocket.receive_json()
            )

            if (
                message.get("type")
                == "selection"
            ):

                websocket_manager.update_selection(
                    websocket,
                    message.get(
                        "selection",
                        {}
                    )
                )

    except WebSocketDisconnect:

        await websocket_manager.disconnect(
            websocket
        )

    except Exception as error:

        print(
            "WebSocket error:",
            error
        )

        await websocket_manager.disconnect(
            websocket
        )


# -------------------------------------------------
# FRONTEND
# -------------------------------------------------

@app.get("/")
async def root():

    if not INDEX_FILE.exists():

        raise HTTPException(
            status_code=404,
            detail="index.html not found"
        )

    return FileResponse(
        INDEX_FILE
    )


@app.get("/index.html")
async def index():

    return FileResponse(
        INDEX_FILE
    )


# -------------------------------------------------
# ERROR HANDLER
# -------------------------------------------------

@app.exception_handler(
    Exception
)
async def general_exception_handler(
    request,
    exc
):

    print(
        "Unhandled error:",
        exc
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc)
        }
    )
