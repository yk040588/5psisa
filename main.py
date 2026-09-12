from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# ---------------------------------------------------------
# Application
# ---------------------------------------------------------

app = FastAPI(
    title="Trading Dashboard",
    description="Custom 5paisa/Xstream trading dashboard",
    version="1.0.0"
)

# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# ---------------------------------------------------------
# Supported symbols
# ---------------------------------------------------------

SUPPORTED_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS",
]

# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "application": "Trading Dashboard",
        "version": "1.0.0"
    }


# ---------------------------------------------------------
# Available symbols
# ---------------------------------------------------------

@app.get("/api/symbols")
async def get_symbols():
    return {
        "symbols": SUPPORTED_SYMBOLS
    }


# ---------------------------------------------------------
# Current dashboard configuration
# ---------------------------------------------------------

@app.get("/api/dashboard")
async def dashboard():
    return {
        "future_chart": True,
        "call_chart": True,
        "put_chart": True,
        "smoothed_heikin_ashi": True,
        "symbols": SUPPORTED_SYMBOLS,
        "buy_sell_enabled": False
    }


# ---------------------------------------------------------
# WebSocket
# ---------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    await websocket.send_json({
        "type": "connection",
        "status": "connected",
        "message": "Trading dashboard WebSocket connected"
    })

    try:
        while True:
            message = await websocket.receive_json()

            # Temporary response.
            # Later this will handle:
            # - symbol changes
            # - expiry changes
            # - CE/PE selection
            # - live market data

            await websocket.send_json({
                "type": "ack",
                "data": message
            })

    except Exception:
        # Client disconnected
        pass


# ---------------------------------------------------------
# Frontend
# ---------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(
            directory=str(FRONTEND_DIR),
            html=True
        ),
        name="frontend"
    )
