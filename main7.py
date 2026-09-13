from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from Backend.instruments import instrument_manager
from Backend.market_data import market_data_manager
from Backend.websocket_manager import websocket_manager


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "Frontend"


# =========================================================
# LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("[APP] Starting application...")

    try:
        instrument_manager.update()
        print("[APP] Scrip master loaded")
    except Exception as exc:
        print(f"[APP] Scrip master update failed: {exc}")

    websocket_manager.start()

    print("[APP] Application started")

    try:
        yield

    finally:

        print("[APP] Stopping application...")

        try:
            await websocket_manager.stop()
        except Exception as exc:
            print(f"[APP] WebSocket manager stop error: {exc}")

        print("[APP] Application stopped")


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="5paisa Trading Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)


# =========================================================
# BASIC
# =========================================================

@app.get("/api/health")
async def health():

    return {
        "status": "ok",
        "application": "5paisa Trading Dashboard",
    }


@app.get("/api/status")
async def api_status():

    try:
        instrument_status = instrument_manager.status()
    except Exception as exc:
        instrument_status = {
            "loaded": False,
            "error": str(exc),
        }

    try:
        market_status = market_data_manager.status()
    except Exception as exc:
        market_status = {
            "error": str(exc),
        }

    return {
        "status": "ok",
        "instruments": instrument_status,
        "market_data": market_status,
        "websocket": {
            "running": websocket_manager.running,
            "clients": len(websocket_manager.clients),
        },
    }


# =========================================================
# SYMBOLS
# =========================================================

@app.get("/api/symbols")
async def get_symbols():

    symbols = [
        "NIFTY",
        "BANKNIFTY",
        "SENSEX",
        "CRUDEOIL",
        "NATURALGAS",
    ]

    return {
        "symbols": symbols
    }


# =========================================================
# EXPIRIES
# =========================================================

@app.get("/api/expiries")
async def get_expiries(
    symbol: str = Query(...),
):

    symbol = symbol.upper().strip()

    try:
        expiries = instrument_manager.get_expiries(symbol)

        return {
            "symbol": symbol,
            "expiries": expiries,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# FUTURES
# =========================================================

@app.get("/api/futures")
async def get_futures(
    symbol: str = Query(...),
    expiry: Optional[str] = Query(None),
):

    symbol = symbol.upper().strip()

    try:

        futures = instrument_manager.get_futures(
            symbol,
            expiry=expiry,
        )

        result = []

        for item in futures:

            result.append(
                {
                    "symbol": item.symbol,
                    "exchange": item.exchange,
                    "exchange_type": item.exchange_type,
                    "instrument_type": item.instrument_type,
                    "expiry": item.expiry,
                    "strike": item.strike,
                    "option_type": item.option_type,
                    "scrip_code": item.broker_token,
                    "lot_size": item.lot_size,
                    "tick_size": item.tick_size,
                }
            )

        return {
            "symbol": symbol,
            "expiry": expiry,
            "futures": result,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# OPTIONS
# =========================================================

@app.get("/api/options")
async def get_options(
    symbol: str = Query(...),
    expiry: str = Query(...),
    option_type: str = Query(...),
):

    symbol = symbol.upper().strip()
    option_type = option_type.upper().strip()

    if option_type not in ("CALL", "PUT"):
        raise HTTPException(
            status_code=400,
            detail="option_type must be CALL or PUT",
        )

    try:

        options = instrument_manager.get_options(
            symbol,
            expiry=expiry,
            option_type=option_type,
        )

        result = []

        for item in options:

            result.append(
                {
                    "symbol": item.symbol,
                    "exchange": item.exchange,
                    "exchange_type": item.exchange_type,
                    "instrument_type": item.instrument_type,
                    "expiry": item.expiry,
                    "strike": item.strike,
                    "option_type": item.option_type,
                    "scrip_code": item.broker_token,
                    "lot_size": item.lot_size,
                    "tick_size": item.tick_size,
                }
            )

        return {
            "symbol": symbol,
            "expiry": expiry,
            "option_type": option_type,
            "options": result,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# HISTORICAL DATA
# =========================================================

@app.get("/api/historical")
async def historical_data(
    symbol: str = Query(...),
    instrument_type: str = Query("FUTURE"),
    expiry: Optional[str] = Query(None),
    strike: Optional[float] = Query(None),
    option_type: Optional[str] = Query(None),
    timeframe: str = Query("5m"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    refresh: bool = Query(False),
):

    symbol = symbol.upper().strip()
    instrument_type = instrument_type.upper().strip()
    timeframe = timeframe.lower().strip()

    if option_type:
        option_type = option_type.upper().strip()

    try:

        candles = market_data_manager.get_candles(
            symbol=symbol,
            instrument_type=instrument_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            interval=timeframe,
            start_date=start_date,
            end_date=end_date,
            refresh=refresh,
        )

        return {
            "symbol": symbol,
            "instrument_type": instrument_type,
            "expiry": expiry,
            "strike": strike,
            "option_type": option_type,
            "timeframe": timeframe,
            "candles": candles,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# INSTRUMENT MASTER STATUS
# =========================================================

@app.get("/api/instruments/status")
async def instruments_status():

    try:

        return instrument_manager.status()

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# REFRESH SCRIP MASTER
# =========================================================

@app.post("/api/instruments/update")
async def update_instruments():

    try:

        result = instrument_manager.update()

        return {
            "status": "ok",
            "result": result,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# =========================================================
# WEBSOCKET
# =========================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket_manager.connect(websocket)

    try:

        while True:

            message = await websocket.receive_json()

            if not isinstance(message, dict):
                continue

            message_type = message.get("type")

            # ---------------------------------------------
            # Selection update
            # ---------------------------------------------

            if message_type in (
                "selection",
                "update_selection",
                "select",
            ):

                selection = message.get(
                    "selection",
                    message,
                )

                if isinstance(selection, dict):

                    websocket_manager.update_selection(
                        websocket,
                        selection,
                    )

                    await websocket_manager.send(
                        websocket,
                        {
                            "type": "selection_updated",
                            "selection": selection,
                        },
                    )

            # ---------------------------------------------
            # Ping
            # ---------------------------------------------

            elif message_type == "ping":

                await websocket_manager.send(
                    websocket,
                    {
                        "type": "pong"
                    },
                )

    except WebSocketDisconnect:

        websocket_manager.disconnect(websocket)

    except Exception as exc:

        print(
            f"[WS] Client error: {exc}"
        )

        websocket_manager.disconnect(websocket)


# =========================================================
# FRONTEND
# =========================================================

@app.get("/")
async def root():

    return FileResponse(
        str(FRONTEND_DIR / "index.html")
    )


@app.get("/index.html")
async def index_html():

    return FileResponse(
        str(FRONTEND_DIR / "index.html")
    )


@app.get("/app.js")
async def app_js():

    return FileResponse(
        str(FRONTEND_DIR / "app.js")
    )


@app.get("/charts.js")
async def charts_js():

    return FileResponse(
        str(FRONTEND_DIR / "charts.js")
    )


@app.get("/controls.js")
async def controls_js():

    return FileResponse(
        str(FRONTEND_DIR / "controls.js")
    )


@app.get("/websocket.js")
async def websocket_js():

    return FileResponse(
        str(FRONTEND_DIR / "websocket.js")
    )


@app.get("/indicators.js")
async def indicators_js():

    return FileResponse(
        str(FRONTEND_DIR / "indicators.js")
    )


@app.get("/style.css")
async def style_css():

    return FileResponse(
        str(FRONTEND_DIR / "style.css")
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):

    print(
        f"[APP] Unhandled error: {exc}"
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc),
        },
    )
