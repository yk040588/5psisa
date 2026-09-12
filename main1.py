from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from Backend.broker import broker
from Backend.instruments import instrument_manager
from Backend.market_data import market_data_manager
from Backend.websocket_manager import websocket_manager
from config.settings import settings


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


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
async def frontend_index():

    path = FRONTEND_DIR / "index.html"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend index.html not found",
        )

    return FileResponse(path)


@app.get("/app.js")
async def frontend_app_js():
    return FileResponse(
        FRONTEND_DIR / "app.js",
        media_type="application/javascript",
    )


@app.get("/charts.js")
async def frontend_charts_js():
    return FileResponse(
        FRONTEND_DIR / "charts.js",
        media_type="application/javascript",
    )


@app.get("/controls.js")
async def frontend_controls_js():
    return FileResponse(
        FRONTEND_DIR / "controls.js",
        media_type="application/javascript",
    )


@app.get("/indicators.js")
async def frontend_indicators_js():
    return FileResponse(
        FRONTEND_DIR / "indicators.js",
        media_type="application/javascript",
    )


@app.get("/websocket.js")
async def frontend_websocket_js():
    return FileResponse(
        FRONTEND_DIR / "websocket.js",
        media_type="application/javascript",
    )


@app.get("/style.css")
async def frontend_style_css():
    return FileResponse(
        FRONTEND_DIR / "style.css",
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
        "frontend": FRONTEND_DIR.exists(),
        "instruments_loaded": instrument_manager.loaded,
        "trading_enabled": settings.TRADING_ENABLED,
        "orders_enabled": settings.ORDERS_ENABLED,
    }


# ============================================================
# AUTH
# ============================================================

@app.get("/api/auth/login")
async def login():

    return {
        "login_url": broker.get_login_url()
    }


@app.get("/api/5paisa/callback")
async def callback(
    code: Optional[str] = None,
    RequestToken: Optional[str] = None,
):

    token_code = code or RequestToken

    if not token_code:
        return {
            "success": False,
            "message": "Authorization code missing",
        }

    result = broker.exchange_token(
        token_code
    )

    return result


# ============================================================
# SYMBOLS
# ============================================================

@app.get("/api/symbols")
async def symbols():

    return {
        "symbols": list(
            instrument_manager.SUPPORTED_UNDERLYINGS
            if hasattr(
                instrument_manager,
                "SUPPORTED_UNDERLYINGS",
            )
            else [
                "NIFTY",
                "BANKNIFTY",
                "SENSEX",
                "CRUDEOIL",
                "NATURALGAS",
            ]
        )
    }


# ============================================================
# INSTRUMENT STATUS
# ============================================================

@app.get("/api/instruments/status")
async def instruments_status():

    return instrument_manager.status()


@app.post("/api/instruments/update")
async def instruments_update():

    return instrument_manager.update()


# ============================================================
# EXPIRIES
# ============================================================

@app.get("/api/expiries")
async def expiries(
    symbol: str = Query(...),
):

    return {
        "symbol": symbol.upper(),
        "expiries": instrument_manager.get_expiries(
            symbol
        ),
    }


# ============================================================
# OPTIONS
# ============================================================

@app.get("/api/options")
async def options(
    symbol: str = Query(...),
    expiry: str = Query(...),
    option_type: Optional[str] = Query(None),
):

    values = instrument_manager.get_options(
        underlying=symbol,
        expiry=expiry,
        option_type=option_type,
    )

    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "option_type": option_type,
        "options": [
            x.to_dict()
            for x in values
        ],
    }


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/api/dashboard")
async def dashboard(
    symbol: str = Query(
        settings.DEFAULT_SYMBOL
    ),
    expiry: Optional[str] = Query(None),
):

    symbol = symbol.upper()

    expiry_list = (
        instrument_manager.get_expiries(
            symbol
        )
    )

    if not expiry:
        futures = (
            instrument_manager.get_futures(
                symbol
            )
        )

        if futures:
            expiry = futures[0].expiry

    futures = (
        instrument_manager.get_futures(
            symbol,
            expiry=expiry,
        )
    )

    calls = (
        instrument_manager.get_options(
            symbol,
            expiry=expiry,
            option_type="CALL",
        )
        if expiry
        else []
    )

    puts = (
        instrument_manager.get_options(
            symbol,
            expiry=expiry,
            option_type="PUT",
        )
        if expiry
        else []
    )

    future_data = [
        x.to_dict()
        for x in futures
    ]

    call_data = [
        x.to_dict()
        for x in calls
    ]

    put_data = [
        x.to_dict()
        for x in puts
    ]

    return {
        "symbol": symbol,
        "expiry": expiry,
        "expiries": expiry_list,

        "future": (
            future_data[0]
            if future_data
            else None
        ),

        "futures": future_data,

        "call": (
            call_data[0]
            if call_data
            else None
        ),

        "calls": call_data,

        "put": (
            put_data[0]
            if put_data
            else None
        ),

        "puts": put_data,
    }


# ============================================================
# HISTORICAL
# ============================================================

@app.get("/api/historical")
async def historical(
    symbol: str = Query(...),
    instrument_type: str = Query("FUTURE"),
    interval: str = Query("5m"),

    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),

    expiry: Optional[str] = Query(None),
    strike: Optional[float] = Query(None),
    option_type: Optional[str] = Query(None),

    refresh: bool = Query(False),
):

    try:

        result = (
            market_data_manager.get_candles(
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
        )

        return result

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# MARKET DATA STATUS
# ============================================================

@app.get("/api/market-data/status")
async def market_data_status():

    return market_data_manager.status()


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):

    await websocket_manager.connect(
        websocket
    )

    try:

        while True:

            message = (
                await websocket.receive_json()
            )

            message_type = (
                message.get("type")
            )

            if message_type == "selection":

                selection = (
                    message.get(
                        "selection",
                        {},
                    )
                )

                websocket_manager.update_selection(
                    websocket,
                    selection,
                )

                await websocket_manager.send(
                    websocket,
                    {
                        "type": "ack",
                        "selection": selection,
                    },
                )

            elif message_type == "ping":

                await websocket_manager.send(
                    websocket,
                    {
                        "type": "pong"
                    },
                )

    except WebSocketDisconnect:

        websocket_manager.disconnect(
            websocket
        )

    except Exception as exc:

        print(
            f"[WS] Client error: {exc}"
        )

        websocket_manager.disconnect(
            websocket
        )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():

    print("=" * 40)
    print("5paisa Trading Dashboard started")
    print("=" * 40)

    if not instrument_manager.loaded:

        print(
            "[STARTUP] Scrip master not loaded."
        )

        try:
            instrument_manager.update()
        except Exception as exc:
            print(
                f"[STARTUP] Scrip master update failed: {exc}"
            )

    websocket_manager.start()


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown():

    await websocket_manager.stop()
