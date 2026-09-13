@app.get("/")
async def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/app.js")
async def app_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"))


@app.get("/charts.js")
async def charts_js():
    return FileResponse(str(FRONTEND_DIR / "charts.js"))


@app.get("/controls.js")
async def controls_js():
    return FileResponse(str(FRONTEND_DIR / "controls.js"))


@app.get("/websocket.js")
async def websocket_js():
    return FileResponse(str(FRONTEND_DIR / "websocket.js"))


@app.get("/indicators.js")
async def indicators_js():
    return FileResponse(str(FRONTEND_DIR / "indicators.js"))


@app.get("/style.css")
async def style_css():
    return FileResponse(str(FRONTEND_DIR / "style.css"))


check from fastapi.responses import FileResponse
