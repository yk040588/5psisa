(function () {
    const charts = {
        future: null,
        call: null,
        put: null
    };
  
    let dashboardData = null;
    let currentSelection = null;

    const intervalMap = {
        "1m": { api: "1m", resample: 1 },
        "3m": { api: "1m", resample: 3 },
        "5m": { api: "5m", resample: 1 },
        "15m": { api: "15m", resample: 1 },
        "30m": { api: "30m", resample: 1 },
        "1h": { api: "60m", resample: 1 },
        "4h": { api: "60m", resample: 4 },
        "1d": { api: "1d", resample: 1 }
    };

    function canvasContext(id) {
        const canvas = document.getElementById(id);
        if (!canvas) return null;

        const rect = canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        canvas.width = Math.max(300, rect.width * dpr);
        canvas.height = Math.max(250, rect.height * dpr);

        const ctx = canvas.getContext("2d");

        ctx.setTransform(
            dpr,
            0,
            0,
            dpr,
            0,
            0
        );

        return {
            canvas,
            ctx,
            width: rect.width,
            height: rect.height
        };
    }

    function normalizeCandles(candles) {
        if (!Array.isArray(candles)) return [];

        return candles
            .map(candle => ({
                timestamp: candle.timestamp,
                open: Number(candle.open),
                high: Number(candle.high),
                low: Number(candle.low),
                close: Number(candle.close),
                volume: Number(candle.volume || 0)
            }))
            .filter(candle =>
                Number.isFinite(candle.open) &&
                Number.isFinite(candle.high) &&
                Number.isFinite(candle.low) &&
                Number.isFinite(candle.close)
            );
    }

    function resample(candles, factor) {
        if (factor <= 1) return candles;

        const result = [];

        for (let i = 0; i < candles.length; i += factor) {
            const group = candles.slice(i, i + factor);
            if (!group.length) continue;

            result.push({
                timestamp: group[0].timestamp,
                open: group[0].open,
                high: Math.max(...group.map(x => x.high)),
                low: Math.min(...group.map(x => x.low)),
                close: group[group.length - 1].close,
                volume: group.reduce(
                    (sum, x) => sum + x.volume,
                    0
                )
            });
        }

        return result;
    }

    async function loadHistorical(
        instrumentType,
        contract,
        expiry,
        timeframe
    ) {
        if (!contract) return [];

        const config =
            intervalMap[timeframe] ||
            intervalMap["5m"];

        const params = new URLSearchParams({
            symbol: currentSelection.symbol,
            instrument_type: instrumentType,
            interval: config.api,
            expiry: expiry || "",
            strike: contract.strike ?? "",
            option_type:
                instrumentType === "CALL"
                    ? "CALL"
                    : instrumentType === "PUT"
                        ? "PUT"
                        : "",
            refresh: "false"
        });

        try {
            const response =
                await fetch(
                    `/api/historical?${params}`
                );

            if (!response.ok) {
                const text = await response.text();
                throw new Error(text);
            }

            const data = await response.json();

            let candles =
                normalizeCandles(data.candles);

            candles =
                resample(
                    candles,
                    config.resample
                );

            return candles;

        } catch (error) {
            console.error(
                "Historical error:",
                error
            );
            return [];
        }
    }

    function drawChart(
        canvasId,
        candles,
        title,
        showSHA = false
    ) {
        const info = canvasContext(canvasId);
        if (!info) return;

        const {
            ctx,
            width,
            height
        } = info;

        ctx.clearRect(0, 0, width, height);

        if (!candles.length) {
            ctx.font = "14px Arial";
            ctx.fillText(
                "Waiting for market data...",
                20,
                30
            );
            return;
        }

        const padding = {
            left: 60,
            right: 20,
            top: 25,
            bottom: 35
        };

        const chartWidth =
            width -
            padding.left -
            padding.right;

        const chartHeight =
            height -
            padding.top -
            padding.bottom;

        let minPrice =
            Math.min(
                ...candles.map(x => x.low)
            );

        let maxPrice =
            Math.max(
                ...candles.map(x => x.high)
            );

        if (showSHA) {
            const sha =
                window.TradingIndicators
                    ?.smoothedHeikinAshi(
                        candles,
                        3
                    );

            if (sha?.length) {
                minPrice =
                    Math.min(
                        minPrice,
                        ...sha.map(x => x.low)
                    );

                maxPrice =
                    Math.max(
                        maxPrice,
                        ...sha.map(x => x.high)
                    );
            }
        }

        const range =
            maxPrice - minPrice || 1;

        const visible =
            candles.slice(-150);

        const candleWidth =
            Math.max(
                2,
                chartWidth / visible.length * 0.65
            );

        function x(index) {
            return (
                padding.left +
                index *
                (
                    chartWidth /
                    Math.max(
                        1,
                        visible.length - 1
                    )
                )
            );
        }

        function y(price) {
            return (
                padding.top +
                (
                    maxPrice - price
                ) /
                range *
                chartHeight
            );
        }

        ctx.font = "11px Arial";

        for (let i = 0; i <= 5; i++) {
            const price =
                minPrice +
                range * i / 5;

            const py = y(price);

            ctx.beginPath();

            ctx.moveTo(
                padding.left,
                py
            );

            ctx.lineTo(
                width - padding.right,
                py
            );

            ctx.stroke();

            ctx.fillText(
                price.toFixed(2),
                5,
                py + 4
            );
        }

        visible.forEach(
            (candle, index) => {
                const cx = x(index);

                const openY = y(candle.open);
                const closeY = y(candle.close);
                const highY = y(candle.high);
                const lowY = y(candle.low);

                ctx.beginPath();

                ctx.moveTo(cx, highY);
                ctx.lineTo(cx, lowY);
                ctx.stroke();

                const top =
                    Math.min(
                        openY,
                        closeY
                    );

                const bodyHeight =
                    Math.max(
                        1,
                        Math.abs(
                            closeY - openY
                        )
                    );

                ctx.fillRect(
                    cx - candleWidth / 2,
                    top,
                    candleWidth,
                    bodyHeight
                );
            }
        );

        if (showSHA) {
            const sha =
                window.TradingIndicators
                    ?.smoothedHeikinAshi(
                        visible,
                        3
                    );

            if (sha?.length) {
                ctx.beginPath();

                sha.forEach(
                    (item, index) => {
                        const px = x(index);
                        const py = y(item.close);

                        if (index === 0) {
                            ctx.moveTo(px, py);
                        } else {
                            ctx.lineTo(px, py);
                        }
                    }
                );

                ctx.stroke();
            }
        }

        ctx.font = "12px Arial";

        ctx.fillText(
            title,
            padding.left,
            15
        );
    }

    async function refreshFutureChart() {
        if (!dashboardData) return;

        const future = dashboardData.future;
        if (!future) return;

        const candles =
            await loadHistorical(
                "FUTURE",
                future,
                currentSelection.expiry,
                currentSelection.timeframe
            );

        drawChart(
            "futureChart",
            candles,
            future.symbol || "Future",
            true
        );

        charts.future = candles;
    }

    async function refreshCallChart() {
        if (!dashboardData) return;

        const call =
            currentSelection.call ||
            dashboardData.call;

        if (!call) return;

        const candles =
            await loadHistorical(
                "CALL",
                call,
                currentSelection.expiry,
                currentSelection.timeframe
            );

        drawChart(
            "callChart",
            candles,
            call.symbol || "CALL"
        );

        charts.call = candles;
    }

    async function refreshPutChart() {
        if (!dashboardData) return;

        const put =
            currentSelection.put ||
            dashboardData.put;

        if (!put) return;

        const candles =
            await loadHistorical(
                "PUT",
                put,
                currentSelection.expiry,
                currentSelection.timeframe
            );

        drawChart(
            "putChart",
            candles,
            put.symbol || "PUT"
        );

        charts.put = candles;
    }

    async function refreshCharts(options = {}) {
        if (options.timeframe) {
            currentSelection.timeframe =
                options.timeframe;
        }

        await Promise.all([
            refreshFutureChart(),
            refreshCallChart(),
            refreshPutChart()
        ]);
    }

    function setDashboardData(
        data,
        selection
    ) {
        dashboardData = data;
        currentSelection = selection;
        refreshCharts();
    }

    function updateChartTick(data) {
        if (!data) return;

        if (data.future?.ltp) {
            const future = charts.future;

            if (future?.length) {
                future[
                    future.length - 1
                ].close =
                    Number(
                        data.future.ltp
                    );
            }
        }
    }

    window.setDashboardData =
        setDashboardData;

    window.refreshCharts =
        refreshCharts;

    window.refreshFutureChart =
        refreshFutureChart;

    window.refreshCallChart =
        refreshCallChart;

    window.refreshPutChart =
        refreshPutChart;

    window.updateChartTick =
        updateChartTick;

    window.tradingCharts =
        charts;

    window.addEventListener(
        "resize",
        () => {
            if (dashboardData) {
                refreshCharts();
            }
        }
    );
})();
