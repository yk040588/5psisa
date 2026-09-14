```javascript
(function () {
    "use strict";

    /*
     * ============================================================
     * 5PAISA PHASE 1 - CHART ENGINE
     * ============================================================
     *
     * Charts:
     *   1. Future
     *   2. Call
     *   3. Put
     *
     * SHA:
     *   Smoothed Heikin Ashi is enabled on ALL THREE charts.
     *
     * Historical data:
     *   Frontend -> /api/historical
     *
     * Live data:
     *   Backend WebSocket / controls.js can call:
     *       window.updateChartTick(...)
     *
     * OTM:
     *   Backend is responsible for providing the correct
     *   OTM-15 Call/Put contracts.
     *
     * Trading:
     *   No order placement is implemented here.
     */

    const charts = {
        future: null,
        call: null,
        put: null
    };

    let dashboardData = null;

    let currentSelection = {
        symbol: null,
        expiry: null,
        timeframe: "5m",
        call: null,
        put: null
    };

    /*
     * Native historical intervals supported by backend / 5paisa.
     *
     * 3m  = fetch 1m and resample 3
     * 4h  = fetch 60m and resample 4
     */
    const INTERVAL_MAP = {
        "1m": {
            apiInterval: "1m",
            resample: 1
        },
        "3m": {
            apiInterval: "1m",
            resample: 3
        },
        "5m": {
            apiInterval: "5m",
            resample: 1
        },
        "15m": {
            apiInterval: "15m",
            resample: 1
        },
        "30m": {
            apiInterval: "30m",
            resample: 1
        },
        "1h": {
            apiInterval: "60m",
            resample: 1
        },
        "4h": {
            apiInterval: "60m",
            resample: 4
        },
        "1d": {
            apiInterval: "1d",
            resample: 1
        }
    };

    const MAX_VISIBLE_CANDLES = 150;

    /*
     * SHA settings
     *
     * Existing indicator implementation can be used if available:
     *   window.TradingIndicators.smoothedHeikinAshi(...)
     *
     * Fallback implementation is also included below.
     */
    const SHA_ENABLED = {
        future: true,
        call: true,
        put: true
    };

    /* ============================================================
     * DOM HELPERS
     * ============================================================ */

    function getElement(id) {
        return document.getElementById(id);
    }

    function setText(id, value) {
        const element = getElement(id);

        if (!element) {
            return;
        }

        element.textContent =
            value === undefined ||
            value === null ||
            value === ""
                ? "-"
                : String(value);
    }

    function showLoading(type, visible) {
        const id = `${type}-loading`;
        const element = getElement(id);

        if (!element) {
            return;
        }

        element.style.display = visible ? "" : "none";
    }

    function getCanvas(type) {
        return getElement(`${type}-canvas`);
    }

    /* ============================================================
     * NUMBER / DATA HELPERS
     * ============================================================ */

    function toNumber(value) {
        if (
            value === null ||
            value === undefined ||
            value === ""
        ) {
            return null;
        }

        const number = Number(value);

        return Number.isFinite(number)
            ? number
            : null;
    }

    function firstDefined(object, keys) {
        if (!object || typeof object !== "object") {
            return null;
        }

        for (const key of keys) {
            if (
                object[key] !== undefined &&
                object[key] !== null &&
                object[key] !== ""
            ) {
                return object[key];
            }
        }

        return null;
    }

    function normalizeTimestamp(value) {
        if (value === undefined || value === null) {
            return null;
        }

        if (typeof value === "number") {
            /*
             * Handle seconds and milliseconds.
             */
            if (value < 10000000000) {
                return value * 1000;
            }

            return value;
        }

        const parsed = Date.parse(String(value));

        return Number.isFinite(parsed)
            ? parsed
            : null;
    }

    function normalizeCandle(candle) {
        if (!candle) {
            return null;
        }

        /*
         * Supports backend objects such as:
         * {
         *   timestamp,
         *   open,
         *   high,
         *   low,
         *   close,
         *   volume
         * }
         *
         * and 5paisa-style:
         * {
         *   Timestamp,
         *   Open,
         *   High,
         *   Low,
         *   Close,
         *   Volume
         * }
         */

        const timestamp = firstDefined(
            candle,
            [
                "timestamp",
                "Timestamp",
                "time",
                "Time",
                "datetime",
                "DateTime",
                "date"
            ]
        );

        const open = firstDefined(
            candle,
            ["open", "Open", "OpenRate"]
        );

        const high = firstDefined(
            candle,
            ["high", "High"]
        );

        const low = firstDefined(
            candle,
            ["low", "Low"]
        );

        const close = firstDefined(
            candle,
            [
                "close",
                "Close",
                "LastRate",
                "ltp",
                "LTP"
            ]
        );

        const volume = firstDefined(
            candle,
            [
                "volume",
                "Volume",
                "TotalQty",
                "volume_traded"
            ]
        );

        const normalizedTimestamp =
            normalizeTimestamp(timestamp);

        const o = toNumber(open);
        const h = toNumber(high);
        const l = toNumber(low);
        const c = toNumber(close);
        const v = toNumber(volume);

        if (
            normalizedTimestamp === null ||
            o === null ||
            h === null ||
            l === null ||
            c === null
        ) {
            return null;
        }

        return {
            timestamp: normalizedTimestamp,
            open: o,
            high: h,
            low: l,
            close: c,
            volume: v === null ? 0 : v
        };
    }

    function normalizeCandles(data) {
        if (!Array.isArray(data)) {
            return [];
        }

        return data
            .map(normalizeCandle)
            .filter(Boolean)
            .sort(
                (a, b) =>
                    a.timestamp - b.timestamp
            );
    }

    /* ============================================================
     * RESAMPLING
     * ============================================================ */

    function resampleCandles(candles, factor) {
        if (
            !Array.isArray(candles) ||
            candles.length === 0 ||
            factor <= 1
        ) {
            return candles;
        }

        const result = [];

        for (
            let index = 0;
            index < candles.length;
            index += factor
        ) {
            const group =
                candles.slice(
                    index,
                    index + factor
                );

            if (!group.length) {
                continue;
            }

            const first = group[0];
            const last =
                group[group.length - 1];

            let high = -Infinity;
            let low = Infinity;
            let volume = 0;

            for (const candle of group) {
                high = Math.max(
                    high,
                    candle.high
                );

                low = Math.min(
                    low,
                    candle.low
                );

                volume +=
                    Number(candle.volume) || 0;
            }

            result.push({
                timestamp: first.timestamp,
                open: first.open,
                high,
                low,
                close: last.close,
                volume
            });
        }

        return result;
    }

    /* ============================================================
     * SHA
     * ============================================================ */

    function fallbackSmoothedHeikinAshi(
        candles,
        period = 3
    ) {
        if (
            !Array.isArray(candles) ||
            candles.length === 0
        ) {
            return [];
        }

        const ha = [];

        let previousHaOpen = null;
        let previousHaClose = null;

        for (const candle of candles) {
            const haClose =
                (
                    candle.open +
                    candle.high +
                    candle.low +
                    candle.close
                ) / 4;

            const haOpen =
                previousHaOpen === null
                    ? (
                        candle.open +
                        candle.close
                    ) / 2
                    : (
                        previousHaOpen +
                        previousHaClose
                    ) / 2;

            const haHigh = Math.max(
                candle.high,
                haOpen,
                haClose
            );

            const haLow = Math.min(
                candle.low,
                haOpen,
                haClose
            );

            ha.push({
                timestamp: candle.timestamp,
                open: haOpen,
                high: haHigh,
                low: haLow,
                close: haClose
            });

            previousHaOpen = haOpen;
            previousHaClose = haClose;
        }

        /*
         * EMA smoothing.
         */
        const alpha =
            2 / (period + 1);

        let smoothOpen =
            ha[0].open;

        let smoothClose =
            ha[0].close;

        return ha.map((item) => {
            smoothOpen =
                alpha * item.open +
                (1 - alpha) * smoothOpen;

            smoothClose =
                alpha * item.close +
                (1 - alpha) * smoothClose;

            const smoothHigh =
                Math.max(
                    item.high,
                    smoothOpen,
                    smoothClose
                );

            const smoothLow =
                Math.min(
                    item.low,
                    smoothOpen,
                    smoothClose
                );

            return {
                timestamp: item.timestamp,
                open: smoothOpen,
                high: smoothHigh,
                low: smoothLow,
                close: smoothClose
            };
        });
    }

    function calculateSHA(candles) {
        if (
            window.TradingIndicators &&
            typeof window.TradingIndicators
                .smoothedHeikinAshi ===
                "function"
        ) {
            try {
                return window.TradingIndicators
                    .smoothedHeikinAshi(
                        candles,
                        3
                    );
            } catch (error) {
                console.warn(
                    "External SHA calculation failed. Using fallback.",
                    error
                );
            }
        }

        return fallbackSmoothedHeikinAshi(
            candles,
            3
        );
    }

    /* ============================================================
     * CHART OBJECT
     * ============================================================ */

    function createChartState(type) {
        return {
            type,
            candles: [],
            sha: [],
            lastUpdated: null
        };
    }

    function ensureChartState(type) {
        if (!charts[type]) {
            charts[type] =
                createChartState(type);
        }

        return charts[type];
    }

    /* ============================================================
     * CANVAS
     * ============================================================ */

    function canvasContext(type) {
        const canvas = getCanvas(type);

        if (!canvas) {
            return null;
        }

        const rect =
            canvas.getBoundingClientRect();

        const width =
            Math.max(
                300,
                Math.floor(rect.width || 300)
            );

        const height =
            Math.max(
                220,
                Math.floor(rect.height || 220)
            );

        const devicePixelRatio =
            window.devicePixelRatio || 1;

        canvas.width =
            width * devicePixelRatio;

        canvas.height =
            height * devicePixelRatio;

        canvas.style.width =
            `${width}px`;

        canvas.style.height =
            `${height}px`;

        const ctx =
            canvas.getContext("2d");

        ctx.setTransform(
            devicePixelRatio,
            0,
            0,
            devicePixelRatio,
            0,
            0
        );

        return {
            ctx,
            width,
            height
        };
    }

    function drawGrid(
        ctx,
        width,
        height,
        padding
    ) {
        ctx.save();

        ctx.strokeStyle =
            "rgba(128, 128, 128, 0.20)";

        ctx.lineWidth = 1;

        const horizontalLines = 5;

        for (
            let i = 0;
            i <= horizontalLines;
            i++
        ) {
            const y =
                padding.top +
                (
                    height -
                    padding.top -
                    padding.bottom
                ) *
                (
                    i /
                    horizontalLines
                );

            ctx.beginPath();
            ctx.moveTo(
                padding.left,
                y
            );

            ctx.lineTo(
                width - padding.right,
                y
            );

            ctx.stroke();
        }

        const verticalLines = 6;

        for (
            let i = 0;
            i <= verticalLines;
            i++
        ) {
            const x =
                padding.left +
                (
                    width -
                    padding.left -
                    padding.right
                ) *
                (
                    i /
                    verticalLines
                );

            ctx.beginPath();
            ctx.moveTo(
                x,
                padding.top
            );

            ctx.lineTo(
                x,
                height - padding.bottom
            );

            ctx.stroke();
        }

        ctx.restore();
    }

    function drawPriceLabels(
        ctx,
        width,
        height,
        padding,
        minPrice,
        maxPrice
    ) {
        ctx.save();

        ctx.fillStyle =
            "rgba(128, 128, 128, 0.95)";

        ctx.font =
            "11px Arial, sans-serif";

        ctx.textAlign = "right";
        ctx.textBaseline = "middle";

        const count = 5;

        for (
            let i = 0;
            i <= count;
            i++
        ) {
            const ratio =
                i / count;

            const price =
                maxPrice -
                (
                    maxPrice -
                    minPrice
                ) *
                ratio;

            const y =
                padding.top +
                (
                    height -
                    padding.top -
                    padding.bottom
                ) *
                ratio;

            ctx.fillText(
                price.toFixed(2),
                width - 5,
                y
            );
        }

        ctx.restore();
    }

    function drawTimeLabels(
        ctx,
        width,
        height,
        padding,
        candles
    ) {
        if (!candles.length) {
            return;
        }

        ctx.save();

        ctx.fillStyle =
            "rgba(128, 128, 128, 0.95)";

        ctx.font =
            "10px Arial, sans-serif";

        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        const positions = [
            0,
            Math.floor(
                candles.length * 0.25
            ),
            Math.floor(
                candles.length * 0.50
            ),
            Math.floor(
                candles.length * 0.75
            ),
            candles.length - 1
        ];

        const unique =
            [...new Set(positions)];

        for (const index of unique) {
            const candle =
                candles[index];

            if (!candle) {
                continue;
            }

            const x =
                padding.left +
                (
                    width -
                    padding.left -
                    padding.right
                ) *
                (
                    index /
                    Math.max(
                        1,
                        candles.length - 1
                    )
                );

            const date =
                new Date(
                    candle.timestamp
                );

            const label =
                date.toLocaleTimeString(
                    [],
                    {
                        hour: "2-digit",
                        minute: "2-digit"
                    }
                );

            ctx.fillText(
                label,
                x,
                height -
                padding.bottom +
                7
            );
        }

        ctx.restore();
    }

    function drawCandles(
        ctx,
        width,
        height,
        padding,
        candles,
        minPrice,
        maxPrice
    ) {
        if (!candles.length) {
            return;
        }

        const chartWidth =
            width -
            padding.left -
            padding.right;

        const chartHeight =
            height -
            padding.top -
            padding.bottom;

        const range =
            Math.max(
                0.000001,
                maxPrice - minPrice
            );

        const candleWidth =
            Math.max(
                2,
                Math.min(
                    14,
                    chartWidth /
                    candles.length *
                    0.65
                )
            );

        function priceToY(price) {
            return (
                padding.top +
                (
                    maxPrice - price
                ) /
                range *
                chartHeight
            );
        }

        for (
            let i = 0;
            i < candles.length;
            i++
        ) {
            const candle =
                candles[i];

            const x =
                padding.left +
                (
                    i + 0.5
                ) *
                (
                    chartWidth /
                    candles.length
                );

            const yOpen =
                priceToY(candle.open);

            const yClose =
                priceToY(candle.close);

            const yHigh =
                priceToY(candle.high);

            const yLow =
                priceToY(candle.low);

            const rising =
                candle.close >=
                candle.open;

            ctx.save();

            /*
             * Wick
             */
            ctx.strokeStyle =
                rising
                    ? "rgba(40, 180, 100, 0.95)"
                    : "rgba(220, 70, 70, 0.95)";

            ctx.lineWidth = 1;

            ctx.beginPath();

            ctx.moveTo(
                x,
                yHigh
            );

            ctx.lineTo(
                x,
                yLow
            );

            ctx.stroke();

            /*
             * Body
             */
            const bodyTop =
                Math.min(
                    yOpen,
                    yClose
                );

            const bodyBottom =
                Math.max(
                    yOpen,
                    yClose
                );

            const bodyHeight =
                Math.max(
                    1,
                    bodyBottom -
                    bodyTop
                );

            ctx.fillStyle =
                rising
                    ? "rgba(40, 180, 100, 0.85)"
                    : "rgba(220, 70, 70, 0.85)";

            ctx.fillRect(
                x -
                candleWidth / 2,
                bodyTop,
                candleWidth,
                bodyHeight
            );

            ctx.restore();
        }
    }

    function drawSHA(
        ctx,
        width,
        height,
        padding,
        sha,
        minPrice,
        maxPrice
    ) {
        if (
            !Array.isArray(sha) ||
            sha.length < 2
        ) {
            return;
        }

        const chartWidth =
            width -
            padding.left -
            padding.right;

        const chartHeight =
            height -
            padding.top -
            padding.bottom;

        const range =
            Math.max(
                0.000001,
                maxPrice - minPrice
            );

        function priceToY(price) {
            return (
                padding.top +
                (
                    maxPrice - price
                ) /
                range *
                chartHeight
            );
        }

        ctx.save();

        ctx.strokeStyle =
            "rgba(255, 193, 7, 0.95)";

        ctx.lineWidth = 1.6;

        ctx.beginPath();

        for (
            let i = 0;
            i < sha.length;
            i++
        ) {
            const item = sha[i];

            const x =
                padding.left +
                (
                    i + 0.5
                ) *
                (
                    chartWidth /
                    sha.length
                );

            const y =
                priceToY(
                    Number(item.close)
                );

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }

        ctx.stroke();

        ctx.restore();
    }

    function drawChart(
        type,
        candles,
        showSHA
    ) {
        const state =
            ensureChartState(type);

        const canvasInfo =
            canvasContext(type);

        if (!canvasInfo) {
            return;
        }

        const {
            ctx,
            width,
            height
        } = canvasInfo;

        ctx.clearRect(
            0,
            0,
            width,
            height
        );

        if (
            !Array.isArray(candles) ||
            candles.length === 0
        ) {
            ctx.save();

            ctx.fillStyle =
                "rgba(128, 128, 128, 0.85)";

            ctx.font =
                "14px Arial, sans-serif";

            ctx.textAlign = "center";
            ctx.textBaseline = "middle";

            ctx.fillText(
                "Waiting for market data...",
                width / 2,
                height / 2
            );

            ctx.restore();

            return;
        }

        const visibleCandles =
            candles.slice(
                -MAX_VISIBLE_CANDLES
            );

        state.candles =
            visibleCandles;

        const padding = {
            top: 15,
            right: 55,
            bottom: 30,
            left: 10
        };

        let minPrice = Infinity;
        let maxPrice = -Infinity;

        for (const candle of visibleCandles) {
            minPrice =
                Math.min(
                    minPrice,
                    candle.low
                );

            maxPrice =
                Math.max(
                    maxPrice,
                    candle.high
                );
        }

        /*
         * Include SHA in price range.
         */
        let sha = [];

        if (showSHA) {
            sha =
                calculateSHA(
                    visibleCandles
                );

            for (const item of sha) {
                const close =
                    Number(item.close);

                if (Number.isFinite(close)) {
                    minPrice =
                        Math.min(
                            minPrice,
                            close
                        );

                    maxPrice =
                        Math.max(
                            maxPrice,
                            close
                        );
                }
            }
        }

        /*
         * Small visual margin.
         */
        const range =
            Math.max(
                0.000001,
                maxPrice - minPrice
            );

        minPrice -=
            range * 0.04;

        maxPrice +=
            range * 0.04;

        drawGrid(
            ctx,
            width,
            height,
            padding
        );

        drawCandles(
            ctx,
            width,
            height,
            padding,
            visibleCandles,
            minPrice,
            maxPrice
        );

        if (showSHA) {
            drawSHA(
                ctx,
                width,
                height,
                padding,
                sha,
                minPrice,
                maxPrice
            );
        }

        drawPriceLabels(
            ctx,
            width,
            height,
            padding,
            minPrice,
            maxPrice
        );

        drawTimeLabels(
            ctx,
            width,
            height,
            padding,
            visibleCandles
        );

        state.sha = sha;
        state.lastUpdated =
            Date.now();
    }

    /* ============================================================
     * HISTORICAL API
     * ============================================================ */

    function buildHistoricalParams(
        type
    ) {
        const params =
            new URLSearchParams();

        const symbol =
            currentSelection.symbol ||
            dashboardData?.symbol;

        const expiry =
            currentSelection.expiry ||
            dashboardData?.expiry;

        params.set(
            "symbol",
            symbol || ""
        );

        params.set(
            "instrument_type",
            type === "future"
                ? "FUTURE"
                : type === "call"
                    ? "CALL"
                    : "PUT"
        );

        const timeframe =
            currentSelection.timeframe ||
            "5m";

        const interval =
            INTERVAL_MAP[timeframe] ||
            INTERVAL_MAP["5m"];

        params.set(
            "interval",
            interval.apiInterval
        );

        if (expiry) {
            params.set(
                "expiry",
                expiry
            );
        }

        let contract = null;

        if (type === "future") {
            contract =
                dashboardData?.future ||
                dashboardData?.futures?.[0] ||
                null;
        }

        if (type === "call") {
            contract =
                currentSelection.call ||
                dashboardData?.call ||
                null;
        }

        if (type === "put") {
            contract =
                currentSelection.put ||
                dashboardData?.put ||
                null;
        }

        if (contract) {
            const strike =
                firstDefined(
                    contract,
                    [
                        "strike",
                        "Strike",
                        "StrikePrice"
                    ]
                );

            if (
                strike !== null &&
                strike !== undefined
            ) {
                params.set(
                    "strike",
                    strike
                );
            }

            const optionType =
                firstDefined(
                    contract,
                    [
                        "option_type",
                        "optionType",
                        "OptionType",
                        "type"
                    ]
                );

            if (
                optionType !== null &&
                optionType !== undefined
            ) {
                params.set(
                    "option_type",
                    optionType
                );
            }

            const scripCode =
                firstDefined(
                    contract,
                    [
                        "scrip_code",
                        "scripCode",
                        "ScripCode",
                        "broker_token",
                        "token",
                        "instrument_token"
                    ]
                );

            if (
                scripCode !== null &&
                scripCode !== undefined
            ) {
                params.set(
                    "scrip_code",
                    scripCode
                );
            }
        }

        /*
         * false means:
         * use backend/local cache when possible.
         */
        params.set(
            "refresh",
            "false"
        );

        return params;
    }

    async function fetchHistorical(
        type
    ) {
        const params =
            buildHistoricalParams(type);

        const url =
            `/api/historical?${params.toString()}`;

        const response =
            await fetch(url, {
                method: "GET",
                headers: {
                    "Accept":
                        "application/json"
                },
                cache: "no-store"
            });

        if (!response.ok) {
            throw new Error(
                `Historical API failed: ${response.status}`
            );
        }

        const data =
            await response.json();

        /*
         * Accept common backend formats.
         */
        let rawCandles = [];

        if (Array.isArray(data)) {
            rawCandles = data;
        } else if (
            Array.isArray(data.candles)
        ) {
            rawCandles =
                data.candles;
        } else if (
            Array.isArray(data.data)
        ) {
            rawCandles =
                data.data;
        } else if (
            Array.isArray(data?.data?.candles)
        ) {
            rawCandles =
                data.data.candles;
        }

        return normalizeCandles(
            rawCandles
        );
    }

    /* ============================================================
     * LOAD INDIVIDUAL CHART
     * ============================================================ */

    async function loadChart(
        type
    ) {
        showLoading(
            type,
            true
        );

        try {
            let candles =
                await fetchHistorical(
                    type
                );

            const timeframe =
                currentSelection.timeframe ||
                "5m";

            const interval =
                INTERVAL_MAP[timeframe] ||
                INTERVAL_MAP["5m"];

            if (
                interval.resample > 1
            ) {
                candles =
                    resampleCandles(
                        candles,
                        interval.resample
                    );
            }

            const state =
                ensureChartState(type);

            state.candles =
                candles;

            drawChart(
                type,
                candles,
                SHA_ENABLED[type]
            );

            return candles;
        } catch (error) {
            console.error(
                `Failed to load ${type} chart:`,
                error
            );

            drawChart(
                type,
                [],
                SHA_ENABLED[type]
            );

            return [];
        } finally {
            showLoading(
                type,
                false
            );
        }
    }

    /* ============================================================
     * PUBLIC REFRESH FUNCTIONS
     * ============================================================ */

    async function refreshFutureChart() {
        return loadChart("future");
    }

    async function refreshCallChart() {
        return loadChart("call");
    }

    async function refreshPutChart() {
        return loadChart("put");
    }

    async function refreshCharts() {
        /*
         * Run all three together.
         */
        return Promise.all([
            refreshFutureChart(),
            refreshCallChart(),
            refreshPutChart()
        ]);
    }

    /* ============================================================
     * DASHBOARD DATA
     * ============================================================ */

    function setDashboardData(
        data,
        selection
    ) {
        dashboardData =
            data || null;

        if (selection) {
            currentSelection = {
                ...currentSelection,
                ...selection
            };
        }

        if (data) {
            if (data.symbol) {
                currentSelection.symbol =
                    data.symbol;
            }

            if (data.expiry) {
                currentSelection.expiry =
                    data.expiry;
            }
        }

        /*
         * If backend sends selected contracts,
         * use them.
         */
        if (
            data?.call &&
            !currentSelection.call
        ) {
            currentSelection.call =
                data.call;
        }

        if (
            data?.put &&
            !currentSelection.put
        ) {
            currentSelection.put =
                data.put;
        }

        /*
         * Backend may send futures array.
         */
        if (
            !data?.future &&
            Array.isArray(data?.futures) &&
            data.futures.length
        ) {
            data.future =
                data.futures[0];
        }

        updateChartLabels();

        /*
         * Historical charts are refreshed only when
         * dashboard data is available.
         */
        refreshCharts();
    }

    function updateChartLabels() {
        const future =
            dashboardData?.future ||
            dashboardData?.futures?.[0];

        const call =
            currentSelection.call ||
            dashboardData?.call;

        const put =
            currentSelection.put ||
            dashboardData?.put;

        setText(
            "future-symbol",
            contractDisplayName(
                future
            )
        );

        setText(
            "call-symbol",
            contractDisplayName(
                call
            )
        );

        setText(
            "put-symbol",
            contractDisplayName(
                put
            )
        );

        setText(
            "future-contract",
            contractDisplayName(
                future
            )
        );

        setText(
            "call-contract",
            contractDisplayName(
                call
            )
        );

        setText(
            "put-contract",
            contractDisplayName(
                put
            )
        );
    }

    function contractDisplayName(
        contract
    ) {
        if (!contract) {
            return "-";
        }

        const symbol =
            firstDefined(
                contract,
                [
                    "symbol",
                    "Symbol",
                    "name",
                    "Name",
                    "tradingsymbol",
                    "TradingSymbol"
                ]
            );

        if (symbol) {
            return String(symbol);
        }

        const strike =
            firstDefined(
                contract,
                [
                    "strike",
                    "Strike",
                    "StrikePrice"
                ]
            );

        const optionType =
            firstDefined(
                contract,
                [
                    "option_type",
                    "optionType",
                    "OptionType"
                ]
            );

        if (
            strike !== null &&
            optionType
        ) {
            return `${optionType} ${strike}`;
        }

        return "-";
    }

    /* ============================================================
     * CONTRACT SELECTION
     * ============================================================ */

    function setSelectedCall(
        contract
    ) {
        currentSelection.call =
            contract || null;

        if (dashboardData) {
            dashboardData.call =
                contract || null;
        }

        updateChartLabels();

        refreshCallChart();
    }

    function setSelectedPut(
        contract
    ) {
        currentSelection.put =
            contract || null;

        if (dashboardData) {
            dashboardData.put =
                contract || null;
        }

        updateChartLabels();

        refreshPutChart();
    }

    /*
     * app.js can call this after selector change.
     */
    function updateSelection(
        selection
    ) {
        if (!selection) {
            return;
        }

        if (
            selection.symbol !== undefined
        ) {
            currentSelection.symbol =
                selection.symbol;
        }

        if (
            selection.expiry !== undefined
        ) {
            currentSelection.expiry =
                selection.expiry;
        }

        if (
            selection.timeframe !== undefined
        ) {
            currentSelection.timeframe =
                selection.timeframe;
        }

        if (
            selection.call !== undefined
        ) {
            currentSelection.call =
                selection.call;
        }

        if (
            selection.put !== undefined
        ) {
            currentSelection.put =
                selection.put;
        }

        updateChartLabels();
    }

    /* ============================================================
     * LIVE TICK
     * ============================================================ */

    function getTickPrice(tick) {
        return toNumber(
            firstDefined(
                tick,
                [
                    "ltp",
                    "LTP",
                    "LastRate",
                    "lastRate",
                    "last_price",
                    "LastPrice",
                    "price",
                    "Price"
                ]
            )
        );
    }

    function getTickTimestamp(tick) {
        const value =
            firstDefined(
                tick,
                [
                    "timestamp",
                    "Timestamp",
                    "TickDt",
                    "tickDt",
                    "time",
                    "Time"
                ]
            );

        return (
            normalizeTimestamp(
                value
            ) ||
            Date.now()
        );
    }

    function updateLastCandle(
        type,
        price,
        timestamp
    ) {
        if (
            !Number.isFinite(price)
        ) {
            return;
        }

        const state =
            ensureChartState(type);

        if (
            !Array.isArray(
                state.candles
            )
        ) {
            state.candles = [];
        }

        const candles =
            state.candles;

        if (!candles.length) {
            /*
             * No historical candle:
             * create an initial candle.
             */
            const candle = {
                timestamp,
                open: price,
                high: price,
                low: price,
                close: price,
                volume: 0
            };

            candles.push(candle);

            drawChart(
                type,
                candles,
                SHA_ENABLED[type]
            );

            return;
        }

        const last =
            candles[candles.length - 1];

        /*
         * Use selected timeframe to determine
         * candle bucket.
         */
        const timeframe =
            currentSelection.timeframe ||
            "5m";

        const milliseconds =
            timeframeToMilliseconds(
                timeframe
            );

        const currentBucket =
            Math.floor(
                timestamp /
                milliseconds
            ) *
            milliseconds;

        const lastBucket =
            Math.floor(
                last.timestamp /
                milliseconds
            ) *
            milliseconds;

        if (
            currentBucket ===
            lastBucket
        ) {
            last.high =
                Math.max(
                    last.high,
                    price
                );

            last.low =
                Math.min(
                    last.low,
                    price
                );

            last.close =
                price;
        } else if (
            currentBucket >
            lastBucket
        ) {
            candles.push({
                timestamp:
                    currentBucket,
                open: last.close,
                high: price,
                low: price,
                close: price,
                volume: 0
            });
        } else {
            /*
             * Older tick:
             * do not corrupt current candle.
             */
            return;
        }

        if (
            candles.length >
            MAX_VISIBLE_CANDLES * 3
        ) {
            state.candles =
                candles.slice(
                    -MAX_VISIBLE_CANDLES * 2
                );
        }

        drawChart(
            type,
            state.candles,
            SHA_ENABLED[type]
        );
    }

    function timeframeToMilliseconds(
        timeframe
    ) {
        switch (timeframe) {
            case "1m":
                return 60 * 1000;

            case "3m":
                return 3 * 60 * 1000;

            case "5m":
                return 5 * 60 * 1000;

            case "15m":
                return 15 * 60 * 1000;

            case "30m":
                return 30 * 60 * 1000;

            case "1h":
                return 60 * 60 * 1000;

            case "4h":
                return 4 * 60 * 60 * 1000;

            case "1d":
                return 24 * 60 * 60 * 1000;

            default:
                return 5 * 60 * 1000;
        }
    }

    /*
     * Generic live tick entry point.
     *
     * type:
     *   future
     *   call
     *   put
     */
    function updateChartTick(
        type,
        tick
    ) {
        if (
            !["future", "call", "put"]
                .includes(type)
        ) {
            return;
        }

        const price =
            getTickPrice(tick);

        if (
            !Number.isFinite(price)
        ) {
            return;
        }

        const timestamp =
            getTickTimestamp(tick);

        updateLastCandle(
            type,
            price,
            timestamp
        );

        /*
         * Update visible LTP.
         */
        const ltpId =
            `${type}-ltp`;

        setText(
            ltpId,
            price.toFixed(2)
        );
    }

    /*
     * Alternate argument support:
     *
     * updateChartTick({
     *     type: "future",
     *     ltp: 24500
     * })
     */
    function applyLiveTick(
        typeOrPayload,
        maybeTick
    ) {
        if (
            typeof typeOrPayload ===
            "string"
        ) {
            updateChartTick(
                typeOrPayload,
                maybeTick || {}
            );

            return;
        }

        const payload =
            typeOrPayload || {};

        const type =
            payload.type ||
            payload.instrument_type ||
            payload.instrumentType;

        if (type) {
            updateChartTick(
                normalizeChartType(type),
                payload.tick ||
                payload
            );
        }
    }

    function normalizeChartType(
        type
    ) {
        const value =
            String(type || "")
                .toLowerCase();

        if (
            value === "future" ||
            value === "futures"
        ) {
            return "future";
        }

        if (
            value === "call" ||
            value === "ce"
        ) {
            return "call";
        }

        if (
            value === "put" ||
            value === "pe"
        ) {
            return "put";
        }

        return value;
    }

    /* ============================================================
     * RESIZE
     * ============================================================ */

    function redrawAllCharts() {
        for (const type of [
            "future",
            "call",
            "put"
        ]) {
            const state =
                charts[type];

            if (
                state &&
                Array.isArray(
                    state.candles
                )
            ) {
                drawChart(
                    type,
                    state.candles,
                    SHA_ENABLED[type]
                );
            }
        }
    }

    let resizeTimer = null;

    window.addEventListener(
        "resize",
        function () {
            clearTimeout(
                resizeTimer
            );

            resizeTimer =
                setTimeout(
                    redrawAllCharts,
                    120
                );
        }
    );

    /* ============================================================
     * PUBLIC API
     * ============================================================ */

    window.refreshFutureChart =
        refreshFutureChart;

    window.refreshCallChart =
        refreshCallChart;

    window.refreshPutChart =
        refreshPutChart;

    window.refreshCharts =
        refreshCharts;

    window.setDashboardData =
        setDashboardData;

    window.updateSelection =
        updateSelection;

    window.updateChartTick =
        updateChartTick;

    window.applyLiveTick =
        applyLiveTick;

    window.setSelectedCall =
        setSelectedCall;

    window.setSelectedPut =
        setSelectedPut;

    window.TradingCharts = {
        charts,
        refreshFutureChart,
        refreshCallChart,
        refreshPutChart,
        refreshCharts,
        setDashboardData,
        updateSelection,
        updateChartTick,
        applyLiveTick,
        setSelectedCall,
        setSelectedPut,
        redrawAllCharts
    };

    /* ============================================================
     * INITIAL STATE
     * ============================================================ */

    document.addEventListener(
        "DOMContentLoaded",
        function () {
            /*
             * Create chart states.
             */
            ensureChartState("future");
            ensureChartState("call");
            ensureChartState("put");

            /*
             * Initial empty render.
             */
            drawChart(
                "future",
                [],
                true
            );

            drawChart(
                "call",
                [],
                true
            );

            drawChart(
                "put",
                [],
                true
            );
        }
    );
})();
```
