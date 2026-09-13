/* =========================================================
   5PAISA TRADING DASHBOARD
   app.js
   PHASE 1
   ========================================================= */

"use strict";


/* =========================================================
   SUPPORTED SYMBOLS
   ========================================================= */

const SUPPORTED_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS"
];


/* =========================================================
   APPLICATION STATE
   ========================================================= */

const appState = {

    symbol: "NIFTY",

    expiry: "",

    timeframe: "5m",

    future: null,

    call: null,

    put: null,

    dashboard: null,

    initialized: false,

    connected: false

};


/* =========================================================
   DOM REFERENCES
   ========================================================= */

const elements = {

    symbol:
        document.getElementById("symbol"),

    expiry:
        document.getElementById("expiry"),

    timeframe:
        document.getElementById("timeframe"),

    callSelector:
        document.getElementById("call-selector"),

    putSelector:
        document.getElementById("put-selector"),

    connectionStatus:
        document.getElementById("connection-status"),

    futureSymbol:
        document.getElementById("future-symbol"),

    callSymbol:
        document.getElementById("call-symbol"),

    putSymbol:
        document.getElementById("put-symbol"),

    futureContract:
        document.getElementById("future-contract"),

    callContract:
        document.getElementById("call-contract"),

    putContract:
        document.getElementById("put-contract"),

    futureLtp:
        document.getElementById("future-ltp"),

    callLtp:
        document.getElementById("call-ltp"),

    putLtp:
        document.getElementById("put-ltp"),

    futureChart:
        document.getElementById("future-chart"),

    callChart:
        document.getElementById("call-chart"),

    putChart:
        document.getElementById("put-chart"),

    futureCanvas:
        document.getElementById("future-canvas"),

    callCanvas:
        document.getElementById("call-canvas"),

    putCanvas:
        document.getElementById("put-canvas"),

    futureLoading:
        document.getElementById("future-loading"),

    callLoading:
        document.getElementById("call-loading"),

    putLoading:
        document.getElementById("put-loading")

};


/* =========================================================
   INITIALIZATION
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    initializeApplication
);


async function initializeApplication() {

    if (appState.initialized) {
        return;
    }

    appState.initialized = true;

    bindEvents();

    readInitialControls();

    setConnectionStatus(false);

    await loadDashboard();

}


/* =========================================================
   INITIAL CONTROLS
   ========================================================= */

function readInitialControls() {

    if (elements.symbol) {

        const selected =
            elements.symbol.value;

        appState.symbol =
            SUPPORTED_SYMBOLS.includes(selected)
                ? selected
                : "NIFTY";

        elements.symbol.value =
            appState.symbol;
    }


    if (elements.timeframe) {

        appState.timeframe =
            elements.timeframe.value || "5m";

        elements.timeframe.value =
            appState.timeframe;
    }

}


/* =========================================================
   EVENT BINDINGS
   ========================================================= */

function bindEvents() {

    if (elements.symbol) {

        elements.symbol.addEventListener(
            "change",
            handleSymbolChange
        );

    }


    if (elements.expiry) {

        elements.expiry.addEventListener(
            "change",
            handleExpiryChange
        );

    }


    if (elements.timeframe) {

        elements.timeframe.addEventListener(
            "change",
            handleTimeframeChange
        );

    }


    if (elements.callSelector) {

        elements.callSelector.addEventListener(
            "change",
            handleCallChange
        );

    }


    if (elements.putSelector) {

        elements.putSelector.addEventListener(
            "change",
            handlePutChange
        );

    }

}


/* =========================================================
   SYMBOL CHANGE
   ========================================================= */

async function handleSymbolChange(event) {

    const newSymbol =
        event.target.value;

    if (!SUPPORTED_SYMBOLS.includes(newSymbol)) {

        event.target.value =
            appState.symbol;

        return;
    }


    appState.symbol =
        newSymbol;

    appState.expiry =
        "";

    appState.future =
        null;

    appState.call =
        null;

    appState.put =
        null;


    clearDashboard();


    showChartLoading(
        "future",
        "Loading Future..."
    );

    showChartLoading(
        "call",
        "Loading OTM Calls..."
    );

    showChartLoading(
        "put",
        "Loading OTM Puts..."
    );


    await loadDashboard();

}


/* =========================================================
   EXPIRY CHANGE
   ========================================================= */

async function handleExpiryChange(event) {

    appState.expiry =
        event.target.value;

    appState.call =
        null;

    appState.put =
        null;


    resetContractSelectors();


    showChartLoading(
        "future",
        "Loading Future..."
    );

    showChartLoading(
        "call",
        "Loading OTM Calls..."
    );

    showChartLoading(
        "put",
        "Loading OTM Puts..."
    );


    await loadDashboard();

}


/* =========================================================
   TIMEFRAME CHANGE
   ========================================================= */

async function handleTimeframeChange(event) {

    appState.timeframe =
        event.target.value || "5m";


    await refreshAllCharts();


    sendSelection();

}


/* =========================================================
   CALL CHANGE
   ========================================================= */

async function handleCallChange(event) {

    appState.call =
        getSelectedContract(
            elements.callSelector
        );


    updateContractLabels();


    await refreshCallChart();


    sendSelection();

}


/* =========================================================
   PUT CHANGE
   ========================================================= */

async function handlePutChange(event) {

    appState.put =
        getSelectedContract(
            elements.putSelector
        );


    updateContractLabels();


    await refreshPutChart();


    sendSelection();

}


/* =========================================================
   LOAD DASHBOARD
   ========================================================= */

async function loadDashboard() {

    try {

        const params =
            new URLSearchParams();


        params.set(
            "symbol",
            appState.symbol
        );


        if (appState.expiry) {

            params.set(
                "expiry",
                appState.expiry
            );

        }


        const response =
            await fetch(
                `/api/dashboard?${params.toString()}`
            );


        if (!response.ok) {

            throw new Error(
                `Dashboard request failed: ${response.status}`
            );

        }


        const data =
            await response.json();


        appState.dashboard =
            data;


        processDashboardData(data);


        setConnectionStatus(
            Boolean(
                data.connected ??
                data.broker_connected ??
                false
            )
        );


        sendSelection();


    } catch (error) {

        console.error(
            "Unable to load dashboard:",
            error
        );


        showChartLoading(
            "future",
            "Waiting for market data..."
        );

        showChartLoading(
            "call",
            "Waiting for market data..."
        );

        showChartLoading(
            "put",
            "Waiting for market data..."
        );


        setConnectionStatus(false);

    }

}


/* =========================================================
   PROCESS DASHBOARD DATA
   ========================================================= */

function processDashboardData(data) {

    if (!data) {
        return;
    }


    /*
     * EXPIRIES
     */

    const expiries =
        Array.isArray(data.expiries)
            ? data.expiries
            : [];


    populateExpirySelector(
        expiries
    );


    /*
     * FUTURE
     */

    const futures =
        Array.isArray(data.futures)
            ? data.futures
            : (
                data.future
                    ? [data.future]
                    : []
            );


    appState.future =
        futures.length
            ? futures[0]
            : null;


    /*
     * CALLS
     */

    const calls =
        Array.isArray(data.calls)
            ? data.calls
            : (
                data.call
                    ? [data.call]
                    : []
            );


    /*
     * PUTS
     */

    const puts =
        Array.isArray(data.puts)
            ? data.puts
            : (
                data.put
                    ? [data.put]
                    : []
            );


    /*
     * Populate OTM contract selectors.
     *
     * Backend should preferably return
     * OTM contracts first / filtered.
     */

    populateContractSelector(
        elements.callSelector,
        calls,
        appState.call
    );


    populateContractSelector(
        elements.putSelector,
        puts,
        appState.put
    );


    /*
     * Automatically select first OTM
     * contract returned by backend.
     */

    if (!appState.call && calls.length) {

        appState.call =
            calls[0];

        elements.callSelector.value =
            getContractValue(
                appState.call
            );

    }


    if (!appState.put && puts.length) {

        appState.put =
            puts[0];

        elements.putSelector.value =
            getContractValue(
                appState.put
            );

    }


    updateContractLabels();


    /*
     * Dashboard data can also be consumed
     * by another chart module if present.
     */

    if (
        typeof window.setDashboardData ===
        "function"
    ) {

        window.setDashboardData(
            data,
            getCurrentSelection()
        );

    }


    /*
     * Draw available data.
     */

    if (appState.future) {

        loadHistoricalChart(
            "future",
            appState.future
        );

    }


    if (appState.call) {

        loadHistoricalChart(
            "call",
            appState.call
        );

    }


    if (appState.put) {

        loadHistoricalChart(
            "put",
            appState.put
        );

    }

}


/* =========================================================
   EXPIRY SELECTOR
   ========================================================= */

function populateExpirySelector(expiries) {

    if (!elements.expiry) {
        return;
    }


    elements.expiry.innerHTML =
        "";


    if (!expiries.length) {

        const option =
            document.createElement(
                "option"
            );

        option.value =
            "";

        option.textContent =
            "Loading...";

        elements.expiry.appendChild(
            option
        );

        return;
    }


    expiries.forEach(
        expiry => {

            const option =
                document.createElement(
                    "option"
                );


            const value =
                getExpiryValue(
                    expiry
                );


            option.value =
                value;

            option.textContent =
                getExpiryLabel(
                    expiry
                );


            elements.expiry.appendChild(
                option
            );

        }
    );


    /*
     * Keep current expiry when possible.
     */

    const currentExists =
        [...elements.expiry.options]
            .some(
                option =>
                    option.value ===
                    appState.expiry
            );


    if (
        appState.expiry &&
        currentExists
    ) {

        elements.expiry.value =
            appState.expiry;

    } else {

        elements.expiry.selectedIndex =
            0;

        appState.expiry =
            elements.expiry.value;

    }

}


/* =========================================================
   CONTRACT SELECTOR
   ========================================================= */

function populateContractSelector(
    select,
    contracts,
    selected
) {

    if (!select) {
        return;
    }


    select.innerHTML =
        "";


    if (!contracts.length) {

        const option =
            document.createElement(
                "option"
            );

        option.value =
            "";

        option.textContent =
            "No contracts";

        select.appendChild(
            option
        );

        return;
    }


    contracts.forEach(
        contract => {

            const option =
                document.createElement(
                    "option"
                );


            const value =
                getContractValue(
                    contract
                );


            option.value =
                value;


            option.textContent =
                getOptionLabel(
                    contract
                );


            select.appendChild(
                option
            );

        }
    );


    if (selected) {

        const value =
            getContractValue(
                selected
            );


        const exists =
            [...select.options]
                .some(
                    option =>
                        option.value ===
                        value
                );


        if (exists) {

            select.value =
                value;

        }

    }

}


/* =========================================================
   CONTRACT VALUE
   ========================================================= */

function getContractValue(contract) {

    if (!contract) {
        return "";
    }


    return String(
        contract.scrip_code ??
        contract.broker_token ??
        contract.token ??
        contract.instrument_token ??
        contract.symbol ??
        ""
    );

}


/* =========================================================
   CONTRACT LABEL
   ========================================================= */

function getOptionLabel(contract) {

    if (!contract) {
        return "-";
    }


    if (contract.symbol) {

        return String(
            contract.symbol
        );

    }


    const optionType =
        contract.option_type ||
        contract.optionType ||
        "";


    const strike =
        contract.strike ??
        "";


    if (
        optionType &&
        strike !== ""
    ) {

        return `${strike} ${optionType}`;

    }


    return getContractValue(
        contract
    );

}


/* =========================================================
   SELECTED CONTRACT
   ========================================================= */

function getSelectedContract(select) {

    if (!select) {
        return null;
    }


    const selectedIndex =
        select.selectedIndex;


    if (selectedIndex < 0) {
        return null;
    }


    const option =
        select.options[
            selectedIndex
        ];


    if (!option) {
        return null;
    }


    return {
        symbol:
            option.textContent,

        scrip_code:
            option.value
    };

}


/* =========================================================
   EXPIRY VALUE
   ========================================================= */

function getExpiryValue(expiry) {

    if (
        typeof expiry ===
        "string"
    ) {

        return expiry;

    }


    if (!expiry) {
        return "";
    }


    return String(
        expiry.value ??
        expiry.expiry ??
        expiry.date ??
        expiry.name ??
        ""
    );

}


/* =========================================================
   EXPIRY LABEL
   ========================================================= */

function getExpiryLabel(expiry) {

    if (
        typeof expiry ===
        "string"
    ) {

        return expiry;

    }


    if (!expiry) {
        return "-";
    }


    return String(
        expiry.label ??
        expiry.expiry ??
        expiry.date ??
        expiry.name ??
        expiry.value ??
        ""
    );

}


/* =========================================================
   CONTRACT LABELS
   ========================================================= */

function updateContractLabels() {

    const futureName =
        getContractName(
            appState.future
        );


    const callName =
        getContractName(
            appState.call
        );


    const putName =
        getContractName(
            appState.put
        );


    if (elements.futureSymbol) {

        elements.futureSymbol.textContent =
            futureName;

    }


    if (elements.callSymbol) {

        elements.callSymbol.textContent =
            callName;

    }


    if (elements.putSymbol) {

        elements.putSymbol.textContent =
            putName;

    }


    if (elements.futureContract) {

        elements.futureContract.textContent =
            futureName;

    }


    if (elements.callContract) {

        elements.callContract.textContent =
            callName;

    }


    if (elements.putContract) {

        elements.putContract.textContent =
            putName;

    }

}


/* =========================================================
   CONTRACT NAME
   ========================================================= */

function getContractName(contract) {

    if (!contract) {
        return "-";
    }


    return String(
        contract.symbol ??
        contract.name ??
        contract.trading_symbol ??
        "-"
    );

}


/* =========================================================
   CLEAR DASHBOARD
   ========================================================= */

function clearDashboard() {

    appState.future =
        null;

    appState.call =
        null;

    appState.put =
        null;


    updateContractLabels();

    resetContractSelectors();

    clearCanvas(
        elements.futureCanvas
    );

    clearCanvas(
        elements.callCanvas
    );

    clearCanvas(
        elements.putCanvas
    );

}


/* =========================================================
   RESET SELECTORS
   ========================================================= */

function resetContractSelectors() {

    if (elements.callSelector) {

        elements.callSelector.innerHTML =
            `<option value="">Loading...</option>`;

    }


    if (elements.putSelector) {

        elements.putSelector.innerHTML =
            `<option value="">Loading...</option>`;

    }

}


/* =========================================================
   LOADING MESSAGE
   ========================================================= */

function showChartLoading(
    chart,
    message
) {

    let target = null;


    if (chart === "future") {

        target =
            elements.futureLoading;

    }

    if (chart === "call") {

        target =
            elements.callLoading;

    }

    if (chart === "put") {

        target =
            elements.putLoading;

    }


    if (target) {

        target.textContent =
            message;

        target.style.display =
            "block";

    }

}


/* =========================================================
   HIDE LOADING
   ========================================================= */

function hideChartLoading(chart) {

    let target = null;


    if (chart === "future") {

        target =
            elements.futureLoading;

    }

    if (chart === "call") {

        target =
            elements.callLoading;

    }

    if (chart === "put") {

        target =
            elements.putLoading;

    }


    if (target) {

        target.style.display =
            "none";

    }

}


/* =========================================================
   HISTORICAL DATA
   ========================================================= */

async function loadHistoricalChart(
    chartType,
    contract
) {

    if (!contract) {
        return;
    }


    showChartLoading(
        chartType,
        "Loading chart..."
    );


    try {

        const params =
            new URLSearchParams();


        params.set(
            "symbol",
            appState.symbol
        );


        if (appState.expiry) {

            params.set(
                "expiry",
                appState.expiry
            );

        }


        params.set(
            "timeframe",
            getApiTimeframe(
                appState.timeframe
            )
        );


        params.set(
            "refresh",
            "false"
        );


        /*
         * Instrument type
         */

        let instrumentType =
            "FUTURE";


        if (chartType === "call") {

            instrumentType =
                "CALL";

        }


        if (chartType === "put") {

            instrumentType =
                "PUT";

        }


        params.set(
            "instrument_type",
            instrumentType
        );


        /*
         * Contract fields
         */

        if (
            contract.scrip_code !==
            undefined
        ) {

            params.set(
                "scrip_code",
                contract.scrip_code
            );

        }


        if (contract.broker_token) {

            params.set(
                "broker_token",
                contract.broker_token
            );

        }


        if (contract.strike !== undefined) {

            params.set(
                "strike",
                contract.strike
            );

        }


        if (contract.option_type) {

            params.set(
                "option_type",
                contract.option_type
            );

        }


        const response =
            await fetch(
                `/api/historical?${params.toString()}`
            );


        if (!response.ok) {

            throw new Error(
                `Historical request failed: ${response.status}`
            );

        }


        const result =
            await response.json();


        const candles =
            normalizeCandles(
                result
            );


        drawChart(
            chartType,
            candles
        );


        hideChartLoading(
            chartType
        );


    } catch (error) {

        console.error(
            `${chartType} chart error:`,
            error
        );


        showChartLoading(
            chartType,
            "Waiting for market data..."
        );

    }

}


/* =========================================================
   API TIMEFRAME
   ========================================================= */

function getApiTimeframe(
    timeframe
) {

    switch (timeframe) {

        case "3m":
            return "1m";

        case "4h":
            return "60m";

        case "1h":
            return "60m";

        default:
            return timeframe;

    }

}


/* =========================================================
   REFRESH ALL CHARTS
   ========================================================= */

async function refreshAllCharts() {

    const jobs = [];


    if (appState.future) {

        jobs.push(
            loadHistoricalChart(
                "future",
                appState.future
            )
        );

    }


    if (appState.call) {

        jobs.push(
            loadHistoricalChart(
                "call",
                appState.call
            )
        );

    }


    if (appState.put) {

        jobs.push(
            loadHistoricalChart(
                "put",
                appState.put
            )
        );

    }


    await Promise.all(
        jobs
    );

}


/* =========================================================
   REFRESH CALL
   ========================================================= */

async function refreshCallChart() {

    if (!appState.call) {
        return;
    }


    await loadHistoricalChart(
        "call",
        appState.call
    );

}


/* =========================================================
   REFRESH PUT
   ========================================================= */

async function refreshPutChart() {

    if (!appState.put) {
        return;
    }


    await loadHistoricalChart(
        "put",
        appState.put
    );

}


/* =========================================================
   NORMALIZE CANDLES
   ========================================================= */

function normalizeCandles(result) {

    let data = [];


    if (Array.isArray(result)) {

        data =
            result;

    } else if (
        Array.isArray(result.candles)
    ) {

        data =
            result.candles;

    } else if (
        Array.isArray(result.data)
    ) {

        data =
            result.data;

    } else if (
        Array.isArray(result.records)
    ) {

        data =
            result.records;

    }


    return data
        .map(
            candle =>
                normalizeCandle(
                    candle
                )
        )
        .filter(
            candle =>
                candle !== null
        )
        .slice(-150);

}


/* =========================================================
   NORMALIZE SINGLE CANDLE
   ========================================================= */

function normalizeCandle(candle) {

    if (!candle) {
        return null;
    }


    const time =
        candle.time ??
        candle.datetime ??
        candle.date ??
        candle.Timestamp ??
        candle.timestamp;


    const open =
        Number(
            candle.open ??
            candle.Open ??
            candle.o
        );


    const high =
        Number(
            candle.high ??
            candle.High ??
            candle.h
        );


    const low =
        Number(
            candle.low ??
            candle.Low ??
            candle.l
        );


    const close =
        Number(
            candle.close ??
            candle.Close ??
            candle.c
        );


    if (
        !Number.isFinite(open) ||
        !Number.isFinite(high) ||
        !Number.isFinite(low) ||
        !Number.isFinite(close)
    ) {

        return null;

    }


    return {

        time,

        open,

        high,

        low,

        close

    };

}


/* =========================================================
   DRAW CHART
   ========================================================= */

function drawChart(
    chartType,
    candles
) {

    let canvas = null;


    if (chartType === "future") {

        canvas =
            elements.futureCanvas;

    }


    if (chartType === "call") {

        canvas =
            elements.callCanvas;

    }


    if (chartType === "put") {

        canvas =
            elements.putCanvas;

    }


    if (!canvas) {
        return;
    }


    if (!candles.length) {

        clearCanvas(
            canvas
        );

        return;
    }


    const context =
        canvas.getContext(
            "2d"
        );


    const rect =
        canvas.getBoundingClientRect();


    const width =
        Math.max(
            1,
            Math.floor(
                rect.width
            )
        );


    const height =
        Math.max(
            1,
            Math.floor(
                rect.height
            )
        );


    const ratio =
        window.devicePixelRatio ||
        1;


    canvas.width =
        width * ratio;


    canvas.height =
        height * ratio;


    context.setTransform(
        ratio,
        0,
        0,
        ratio,
        0,
        0
    );


    context.clearRect(
        0,
        0,
        width,
        height
    );


    /*
     * SHA calculation
     */

    const sha =
        calculateSHA(
            candles,
            3
        );


    const values =
        [];


    candles.forEach(
        candle => {

            values.push(
                candle.high,
                candle.low
            );

        }
    );


    sha.forEach(
        candle => {

            values.push(
                candle.high,
                candle.low
            );

        }
    );


    let min =
        Math.min(
            ...values
        );


    let max =
        Math.max(
            ...values
        );


    if (
        !Number.isFinite(min) ||
        !Number.isFinite(max)
    ) {

        return;

    }


    const paddingTop =
        20;

    const paddingBottom =
        20;

    const paddingLeft =
        10;

    const paddingRight =
        55;


    const chartWidth =
        width -
        paddingLeft -
        paddingRight;


    const chartHeight =
        height -
        paddingTop -
        paddingBottom;


    if (
        chartWidth <= 0 ||
        chartHeight <= 0
    ) {

        return;

    }


    const range =
        max - min ||
        1;


    function y(value) {

        return (
            paddingTop +
            (
                (max - value) /
                range
            ) *
            chartHeight
        );

    }


    /*
     * Grid
     */

    context.strokeStyle =
        "#1c232c";

    context.lineWidth =
        1;


    for (
        let i = 0;
        i <= 5;
        i++
    ) {

        const gy =
            paddingTop +
            (
                chartHeight *
                i /
                5
            );


        context.beginPath();

        context.moveTo(
            paddingLeft,
            gy
        );

        context.lineTo(
            width -
            paddingRight,
            gy
        );

        context.stroke();

    }


    /*
     * Price labels
     */

    context.fillStyle =
        "#667281";

    context.font =
        "10px Arial";


    for (
        let i = 0;
        i <= 5;
        i++
    ) {

        const value =
            max -
            (
                range *
                i /
                5
            );


        const gy =
            paddingTop +
            (
                chartHeight *
                i /
                5
            );


        context.fillText(
            formatPrice(value),
            width -
            paddingRight +
            6,
            gy + 3
        );

    }


    /*
     * Candles
     */

    const count =
        candles.length;


    const candleSpace =
        chartWidth /
        count;


    const candleWidth =
        Math.max(
            2,
            Math.min(
                8,
                candleSpace * 0.65
            )
        );


    candles.forEach(
        (
            candle,
            index
        ) => {

            const x =
                paddingLeft +
                (
                    index *
                    candleSpace
                ) +
                (
                    candleSpace /
                    2
                );


            const openY =
                y(
                    candle.open
                );


            const closeY =
                y(
                    candle.close
                );


            const highY =
                y(
                    candle.high
                );


            const lowY =
                y(
                    candle.low
                );


            const rising =
                candle.close >=
                candle.open;


            context.strokeStyle =
                rising
                    ? "#31c48d"
                    : "#ef5350";


            context.fillStyle =
                rising
                    ? "#31c48d"
                    : "#ef5350";


            context.lineWidth =
                1;


            /*
             * Wick
             */

            context.beginPath();

            context.moveTo(
                x,
                highY
            );

            context.lineTo(
                x,
                lowY
            );

            context.stroke();


            /*
             * Body
             */

            const bodyTop =
                Math.min(
                    openY,
                    closeY
                );


            const bodyHeight =
                Math.max(
                    1,
                    Math.abs(
                        closeY -
                        openY
                    )
                );


            context.fillRect(
                x -
                candleWidth / 2,
                bodyTop,
                candleWidth,
                bodyHeight
            );

        }
    );


    /*
     * SHA line
     */

    if (sha.length) {

        context.strokeStyle =
            "#f0b90b";

        context.lineWidth =
            1.5;

        context.beginPath();


        sha.forEach(
            (
                candle,
                index
            ) => {

                const x =
                    paddingLeft +
                    (
                        index *
                        candleSpace
                    ) +
                    (
                        candleSpace /
                        2
                    );


                const value =
                    candle.close;


                const py =
                    y(value);


                if (index === 0) {

                    context.moveTo(
                        x,
                        py
                    );

                } else {

                    context.lineTo(
                        x,
                        py
                    );

                }

            }
        );


        context.stroke();

    }

}


/* =========================================================
   SHA / SMOOTHED HEIKIN ASHI
   ========================================================= */

function calculateSHA(
    candles,
    period = 3
) {

    if (!candles.length) {
        return [];
    }


    const ha = [];


    candles.forEach(
        (
            candle,
            index
        ) => {

            const close =
                (
                    candle.open +
                    candle.high +
                    candle.low +
                    candle.close
                ) / 4;


            let open;


            if (index === 0) {

                open =
                    (
                        candle.open +
                        candle.close
                    ) / 2;

            } else {

                open =
                    (
                        ha[index - 1].open +
                        ha[index - 1].close
                    ) / 2;

            }


            const high =
                Math.max(
                    candle.high,
                    open,
                    close
                );


            const low =
                Math.min(
                    candle.low,
                    open,
                    close
                );


            ha.push({

                open,
                high,
                low,
                close

            });

        }
    );


    /*
     * EMA smoothing
     */

    const alpha =
        2 /
        (
            period +
            1
        );


    const result =
        [];


    let previous =
        ha[0].close;


    ha.forEach(
        (
            candle,
            index
        ) => {

            const smoothed =
                index === 0
                    ? candle.close
                    : (
                        (
                            candle.close -
                            previous
                        ) *
                        alpha
                    ) +
                    previous;


            previous =
                smoothed;


            result.push({

                open:
                    smoothed,

                high:
                    smoothed,

                low:
                    smoothed,

                close:
                    smoothed

            });

        }
    );


    return result;

}


/* =========================================================
   PRICE FORMAT
   ========================================================= */

function formatPrice(value) {

    if (
        !Number.isFinite(value)
    ) {

        return "--";

    }


    return value.toLocaleString(
        "en-IN",
        {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }
    );

}


/* =========================================================
   CLEAR CANVAS
   ========================================================= */

function clearCanvas(canvas) {

    if (!canvas) {
        return;
    }


    const context =
        canvas.getContext(
            "2d"
        );


    context.clearRect(
        0,
        0,
        canvas.width,
        canvas.height
    );

}


/* =========================================================
   CONNECTION STATUS
   ========================================================= */

function setConnectionStatus(
    connected
) {

    appState.connected =
        Boolean(
            connected
        );


    if (
        !elements.connectionStatus
    ) {

        return;
    }


    if (appState.connected) {

        elements.connectionStatus.textContent =
            "● Connected";

        elements.connectionStatus.className =
            "status connected";

    } else {

        elements.connectionStatus.textContent =
            "● Disconnected";

        elements.connectionStatus.className =
            "status disconnected";

    }

}


/* =========================================================
   CURRENT SELECTION
   ========================================================= */

function getCurrentSelection() {

    return {

        symbol:
            appState.symbol,

        expiry:
            appState.expiry,

        timeframe:
            appState.timeframe,

        future:
            appState.future,

        call:
            appState.call,

        put:
            appState.put

    };

}


/* =========================================================
   WEBSOCKET SELECTION
   ========================================================= */

function sendSelection() {

    const selection =
        getCurrentSelection();


    if (
        window.tradingWebSocket &&
        typeof
        window.tradingWebSocket.setSelection ===
        "function"
    ) {

        window.tradingWebSocket.setSelection(
            selection
        );

    }

}


/* =========================================================
   LIVE MARKET TICK
   ========================================================= */

window.updateMarketTick =
    function (data) {

        if (!data) {
            return;
        }


        if (
            data.future &&
            data.future.ltp !==
            undefined
        ) {

            updateMarketValue(
                elements.futureLtp,
                data.future.ltp
            );

        }


        if (
            data.call &&
            data.call.ltp !==
            undefined
        ) {

            updateMarketValue(
                elements.callLtp,
                data.call.ltp
            );

        }


        if (
            data.put &&
            data.put.ltp !==
            undefined
        ) {

            updateMarketValue(
                elements.putLtp,
                data.put.ltp
            );

        }

    };


/* =========================================================
   MARKET VALUE UPDATE
   ========================================================= */

function updateMarketValue(
    element,
    value
) {

    if (!element) {
        return;
    }


    element.textContent =
        formatPrice(
            Number(value)
        );

}


/* =========================================================
   GLOBAL API FOR OTHER MODULES
   ========================================================= */

window.getCurrentSelection =
    getCurrentSelection;


window.refreshCharts =
    async function (options = {}) {

        if (options.timeframe) {

            appState.timeframe =
                options.timeframe;

        }


        await refreshAllCharts();

    };


window.refreshCallChart =
    refreshCallChart;


window.refreshPutChart =
    refreshPutChart;


window.tradingDashboard = {

    state:
        appState,

    getSelection:
        getCurrentSelection,

    refresh:
        refreshAllCharts

};


/* =========================================================
   RESIZE
   ========================================================= */

window.addEventListener(
    "resize",
    function () {

        refreshAllCharts();

    }
);
