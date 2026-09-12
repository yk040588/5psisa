```javascript
/* =========================================================
   TRADING DASHBOARD
   app.js
   Main application state and UI coordination
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

    call: "",

    put: "",

    future: "",

    connected: false,

    dashboard: null,

    initialized: false

};


/* =========================================================
   DOM REFERENCES
   ========================================================= */

const elements = {

    symbol: document.getElementById("symbol"),

    expiry: document.getElementById("expiry"),

    timeframe: document.getElementById("timeframe"),

    callSelector: document.getElementById("call-selector"),

    putSelector: document.getElementById("put-selector"),

    connectionStatus:
        document.getElementById("connection-status"),

    futureSymbol:
        document.getElementById("future-symbol"),

    futureLtp:
        document.getElementById("future-ltp"),

    callLtp:
        document.getElementById("call-ltp"),

    putLtp:
        document.getElementById("put-ltp"),

    futureContract:
        document.getElementById("future-contract"),

    callContract:
        document.getElementById("call-contract"),

    putContract:
        document.getElementById("put-contract"),

    futureChart:
        document.getElementById("future-chart"),

    callChart:
        document.getElementById("call-chart"),

    putChart:
        document.getElementById("put-chart")

};


/* =========================================================
   INITIALIZATION
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    initializeApplication();

});


async function initializeApplication() {

    if (appState.initialized) {
        return;
    }

    appState.initialized = true;

    bindEvents();

    readInitialControls();

    await loadDashboard();

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
   INITIAL CONTROL VALUES
   ========================================================= */

function readInitialControls() {

    if (elements.symbol) {
        appState.symbol =
            elements.symbol.value || "NIFTY";
    }

    if (elements.timeframe) {
        appState.timeframe =
            elements.timeframe.value || "5m";
    }

}


/* =========================================================
   SYMBOL CHANGE
   ========================================================= */

async function handleSymbolChange(event) {

    const newSymbol = event.target.value;

    if (!SUPPORTED_SYMBOLS.includes(newSymbol)) {
        return;
    }

    appState.symbol = newSymbol;

    appState.expiry = "";
    appState.call = "";
    appState.put = "";
    appState.future = "";

    clearContractInformation();

    resetContractSelectors();

    showChartLoading(
        "future",
        "Loading Future..."
    );

    showChartLoading(
        "call",
        "Loading Calls..."
    );

    showChartLoading(
        "put",
        "Loading Puts..."
    );

    await loadDashboard();

}


/* =========================================================
   EXPIRY CHANGE
   ========================================================= */

async function handleExpiryChange(event) {

    appState.expiry = event.target.value;

    appState.call = "";
    appState.put = "";

    resetContractSelectors();

    showChartLoading(
        "future",
        "Loading Future..."
    );

    showChartLoading(
        "call",
        "Loading Calls..."
    );

    showChartLoading(
        "put",
        "Loading Puts..."
    );

    await loadDashboard();

}


/* =========================================================
   TIMEFRAME CHANGE
   ========================================================= */

async function handleTimeframeChange(event) {

    appState.timeframe = event.target.value;

    /*
     * We do not need to change the selected contracts.
     * Only the candle timeframe changes.
     */

    if (typeof window.refreshCharts === "function") {

        window.refreshCharts({
            timeframe: appState.timeframe
        });

    }

    /*
     * If charts.js does not yet implement refreshCharts,
     * send the selection through the WebSocket layer.
     */

    sendSelection();

}


/* =========================================================
   CALL CHANGE
   ========================================================= */

async function handleCallChange(event) {

    appState.call = event.target.value;

    updateContractLabels();

    showChartLoading(
        "call",
        "Loading Call data..."
    );

    if (typeof window.refreshCallChart === "function") {

        await window.refreshCallChart(
            appState.call,
            appState.timeframe
        );

    }

    sendSelection();

}


/* =========================================================
   PUT CHANGE
   ========================================================= */

async function handlePutChange(event) {

    appState.put = event.target.value;

    updateContractLabels();

    showChartLoading(
        "put",
        "Loading Put data..."
    );

    if (typeof window.refreshPutChart === "function") {

        await window.refreshPutChart(
            appState.put,
            appState.timeframe
        );

    }

    sendSelection();

}


/* =========================================================
   LOAD DASHBOARD
   ========================================================= */

async function loadDashboard() {

    try {

        const params = new URLSearchParams();

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

        const response = await fetch(
            `/api/dashboard?${params.toString()}`
        );


        if (!response.ok) {

            throw new Error(
                `Dashboard request failed: ${response.status}`
            );

        }


        const data = await response.json();

        appState.dashboard = data;


        processDashboardData(data);


        /*
         * Inform WebSocket layer about current selection.
         */

        sendSelection();


    } catch (error) {

        console.error(
            "Unable to load dashboard:",
            error
        );

        handleDashboardError(error);

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
     * Support the current backend structure
     * as well as future expanded structures.
     */

    const futures =
        data.futures ||
        data.future ||
        [];

    const calls =
        data.calls ||
        data.call ||
        [];

    const puts =
        data.puts ||
        data.put ||
        [];


    /*
     * ---------------------------------------------
     * EXPIRIES
     * ---------------------------------------------
     */

    const expiries =
        data.expiries ||
        data.expiry ||
        [];


    if (Array.isArray(expiries)) {

        populateExpirySelector(expiries);

    }


    /*
     * ---------------------------------------------
     * FUTURE
     * ---------------------------------------------
     */

    const future =
        Array.isArray(futures)
            ? futures[0]
            : futures;


    if (future) {

        appState.future =
            getContractValue(future);

        updateFutureInformation(future);

    }


    /*
     * ---------------------------------------------
     * CALLS
     * ---------------------------------------------
     */

    if (Array.isArray(calls)) {

        populateCallSelector(calls);

    }


    /*
     * ---------------------------------------------
     * PUTS
     * ---------------------------------------------
     */

    if (Array.isArray(puts)) {

        populatePutSelector(puts);

    }


    updateContractLabels();


    /*
     * Give chart module the current dashboard.
     */

    if (typeof window.setDashboardData === "function") {

        window.setDashboardData(
            data,
            getCurrentSelection()
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


    const previous =
        appState.expiry;


    elements.expiry.innerHTML = "";


    if (!expiries.length) {

        const option =
            document.createElement("option");

        option.value = "";
        option.textContent = "No expiry";

        elements.expiry.appendChild(option);

        appState.expiry = "";

        return;

    }


    expiries.forEach(expiry => {

        const value =
            getExpiryValue(expiry);

        const label =
            getExpiryLabel(expiry);


        const option =
            document.createElement("option");

        option.value = value;
        option.textContent = label;

        elements.expiry.appendChild(option);

    });


    /*
     * Keep existing expiry if it still exists.
     * Otherwise select the first expiry.
     */

    const exists =
        expiries.some(
            expiry =>
                getExpiryValue(expiry) === previous
        );


    if (exists) {

        elements.expiry.value = previous;

        appState.expiry = previous;

    } else {

        elements.expiry.selectedIndex = 0;

        appState.expiry =
            elements.expiry.value;

    }

}


/* =========================================================
   CALL SELECTOR
   ========================================================= */

function populateCallSelector(calls) {

    if (!elements.callSelector) {
        return;
    }


    const previous =
        appState.call;


    elements.callSelector.innerHTML = "";


    calls.forEach(contract => {

        const option =
            document.createElement("option");


        const value =
            getContractValue(contract);

        const label =
            getOptionLabel(contract);


        option.value = value;
        option.textContent = label;


        elements.callSelector.appendChild(
            option
        );

    });


    if (!calls.length) {

        const option =
            document.createElement("option");

        option.value = "";
        option.textContent = "No Call";

        elements.callSelector.appendChild(
            option
        );

        appState.call = "";

        return;

    }


    const exists =
        calls.some(
            contract =>
                getContractValue(contract) === previous
        );


    if (exists) {

        elements.callSelector.value =
            previous;

        appState.call =
            previous;

    } else {

        /*
         * Automatically select the first OTM Call.
         */

        elements.callSelector.selectedIndex = 0;

        appState.call =
            elements.callSelector.value;

    }

}


/* =========================================================
   PUT SELECTOR
   ========================================================= */

function populatePutSelector(puts) {

    if (!elements.putSelector) {
        return;
    }


    const previous =
        appState.put;


    elements.putSelector.innerHTML = "";


    puts.forEach(contract => {

        const option =
            document.createElement("option");


        const value =
            getContractValue(contract);

        const label =
            getOptionLabel(contract);


        option.value = value;
        option.textContent = label;


        elements.putSelector.appendChild(
            option
        );

    });


    if (!puts.length) {

        const option =
            document.createElement("option");

        option.value = "";
        option.textContent = "No Put";

        elements.putSelector.appendChild(
            option
        );

        appState.put = "";

        return;

    }


    const exists =
        puts.some(
            contract =>
                getContractValue(contract) === previous
        );


    if (exists) {

        elements.putSelector.value =
            previous;

        appState.put =
            previous;

    } else {

        /*
         * Automatically select the first OTM Put.
         */

        elements.putSelector.selectedIndex = 0;

        appState.put =
            elements.putSelector.value;

    }

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
   CONTRACT LABELS
   ========================================================= */

function updateContractLabels() {

    if (elements.futureContract) {

        elements.futureContract.textContent =
            appState.future || "-";

    }


    if (elements.callContract) {

        elements.callContract.textContent =
            appState.call || "-";

    }


    if (elements.putContract) {

        elements.putContract.textContent =
            appState.put || "-";

    }

}


/* =========================================================
   FUTURE INFORMATION
   ========================================================= */

function updateFutureInformation(future) {

    if (!future) {
        return;
    }


    const name =
        future.symbol ||
        future.name ||
        future.contract ||
        future.trading_symbol ||
        future.scrip_name ||
        "-";


    const ltp =
        future.ltp ??
        future.last_price ??
        future.lastPrice ??
        future.close ??
        "-";


    if (elements.futureSymbol) {

        elements.futureSymbol.textContent =
            name;

    }


    if (elements.futureLtp) {

        elements.futureLtp.textContent =
            formatPrice(ltp);

    }

}


/* =========================================================
   LIVE TICK UPDATE
   ========================================================= */

function updateMarketTick(tick) {

    if (!tick) {
        return;
    }


    const instrument =
        String(
            tick.instrument ||
            tick.type ||
            ""
        ).toLowerCase();


    const ltp =
        tick.ltp ??
        tick.last_price ??
        tick.lastPrice ??
        tick.price;


    if (ltp === undefined) {
        return;
    }


    if (
        instrument === "future" ||
        instrument === "futures"
    ) {

        if (elements.futureLtp) {

            elements.futureLtp.textContent =
                formatPrice(ltp);

        }

    }


    else if (
        instrument === "call" ||
        instrument === "ce"
    ) {

        if (elements.callLtp) {

            elements.callLtp.textContent =
                formatPrice(ltp);

        }

    }


    else if (
        instrument === "put" ||
        instrument === "pe"
    ) {

        if (elements.putLtp) {

            elements.putLtp.textContent =
                formatPrice(ltp);

        }

    }

}


/* =========================================================
   CONNECTION STATUS
   ========================================================= */

function setConnectionStatus(connected) {

    appState.connected =
        Boolean(connected);


    if (!elements.connectionStatus) {
        return;
    }


    if (appState.connected) {

        elements.connectionStatus.textContent =
            "● Connected";

        elements.connectionStatus.classList.remove(
            "disconnected"
        );

        elements.connectionStatus.classList.add(
            "connected"
        );

    } else {

        elements.connectionStatus.textContent =
            "● Disconnected";

        elements.connectionStatus.classList.remove(
            "connected"
        );

        elements.connectionStatus.classList.add(
            "disconnected"
        );

    }

}


/* =========================================================
   LOADING
   ========================================================= */

function showChartLoading(type, message) {

    let container = null;


    if (type === "future") {
        container = elements.futureChart;
    }

    if (type === "call") {
        container = elements.callChart;
    }

    if (type === "put") {
        container = elements.putChart;
    }


    if (!container) {
        return;
    }


    /*
     * Do not destroy an existing chart.
     * Just update/create a loading indicator.
     */

    let loader =
        container.querySelector(".chart-loading");


    if (!loader) {

        loader =
            document.createElement("div");

        loader.className =
            "chart-loading";

        container.appendChild(loader);

    }


    loader.textContent =
        message || "Loading...";

    loader.style.display =
        "block";

}


/* =========================================================
   HIDE LOADING
   ========================================================= */

function hideChartLoading(type) {

    let container = null;


    if (type === "future") {
        container = elements.futureChart;
    }

    if (type === "call") {
        container = elements.callChart;
    }

    if (type === "put") {
        container = elements.putChart;
    }


    if (!container) {
        return;
    }


    const loader =
        container.querySelector(".chart-loading");


    if (loader) {

        loader.style.display =
            "none";

    }

}


/* =========================================================
   CLEAR CONTRACT INFORMATION
   ========================================================= */

function clearContractInformation() {

    appState.future = "";

    if (elements.futureSymbol) {
        elements.futureSymbol.textContent = "-";
    }

    if (elements.futureLtp) {
        elements.futureLtp.textContent = "-";
    }

    if (elements.callLtp) {
        elements.callLtp.textContent = "-";
    }

    if (elements.putLtp) {
        elements.putLtp.textContent = "-";
    }

    if (elements.futureContract) {
        elements.futureContract.textContent = "-";
    }

    if (elements.callContract) {
        elements.callContract.textContent = "-";
    }

    if (elements.putContract) {
        elements.putContract.textContent = "-";
    }

}


/* =========================================================
   DASHBOARD ERROR
   ========================================================= */

function handleDashboardError(error) {

    console.error(error);


    if (elements.futureChart) {

        showChartLoading(
            "future",
            "Unable to load Future data"
        );

    }


    if (elements.callChart) {

        showChartLoading(
            "call",
            "Unable to load Call data"
        );

    }


    if (elements.putChart) {

        showChartLoading(
            "put",
            "Unable to load Put data"
        );

    }

}


/* =========================================================
   WEBSOCKET SELECTION
   ========================================================= */

function sendSelection() {

    const selection = getCurrentSelection();


    /*
     * websocket.js is responsible for the actual
     * WebSocket connection.
     */

    if (
        typeof window.sendWebSocketMessage ===
        "function"
    ) {

        window.sendWebSocketMessage({

            type: "selection",

            data: selection

        });

        return;

    }


    /*
     * Alternative function name for websocket.js.
     */

    if (
        typeof window.sendSelectionMessage ===
        "function"
    ) {

        window.sendSelectionMessage(
            selection
        );

    }

}


/* =========================================================
   CURRENT SELECTION
   ========================================================= */

function getCurrentSelection() {

    return {

        symbol: appState.symbol,

        expiry: appState.expiry,

        timeframe: appState.timeframe,

        future: appState.future,

        call: appState.call,

        put: appState.put

    };

}


/* =========================================================
   CONTRACT HELPERS
   ========================================================= */

function getContractValue(contract) {

    if (contract === null ||
        contract === undefined) {

        return "";

    }


    if (typeof contract === "string" ||
        typeof contract === "number") {

        return String(contract);

    }


    return String(
        contract.symbol ||
        contract.trading_symbol ||
        contract.tradingSymbol ||
        contract.contract ||
        contract.broker_token ||
        contract.token ||
        contract.scrip_code ||
        ""
    );

}


function getOptionLabel(contract) {

    if (
        contract === null ||
        contract === undefined
    ) {

        return "";

    }


    if (
        typeof contract === "string" ||
        typeof contract === "number"
    ) {

        return String(contract);

    }


    const symbol =
        contract.symbol ||
        contract.trading_symbol ||
        contract.tradingSymbol ||
        "";


    const strike =
        contract.strike ??
        contract.strike_price ??
        contract.strikePrice;


    const optionType =
        contract.option_type ||
        contract.optionType ||
        contract.type ||
        "";


    if (strike !== undefined &&
        strike !== null &&
        optionType) {

        return `${strike} ${optionType}`;

    }


    if (symbol) {
        return symbol;
    }


    return getContractValue(contract);

}


function getExpiryValue(expiry) {

    if (
        expiry === null ||
        expiry === undefined
    ) {

        return "";

    }


    if (
        typeof expiry === "string" ||
        typeof expiry === "number"
    ) {

        return String(expiry);

    }


    return String(
        expiry.expiry ||
        expiry.date ||
        expiry.expiry_date ||
        expiry.expiryDate ||
        expiry.value ||
        ""
    );

}


function getExpiryLabel(expiry) {

    if (
        expiry === null ||
        expiry === undefined
    ) {

        return "";

    }


    if (
        typeof expiry === "string" ||
        typeof expiry === "number"
    ) {

        return String(expiry);

    }


    return String(
        expiry.label ||
        expiry.expiry ||
        expiry.date ||
        expiry.expiry_date ||
        expiry.expiryDate ||
        expiry.value ||
        ""
    );

}


/* =========================================================
   PRICE FORMATTER
   ========================================================= */

function formatPrice(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {

        return "-";

    }


    const number =
        Number(value);


    if (!Number.isFinite(number)) {

        return String(value);

    }


    return number.toLocaleString(
        "en-IN",
        {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }
    );

}


/* =========================================================
   PUBLIC API
   ========================================================= */

window.tradingDashboard = {

    state: appState,

    getSelection:
        getCurrentSelection,

    loadDashboard:
        loadDashboard,

    updateMarketTick:
        updateMarketTick,

    setConnectionStatus:
        setConnectionStatus,

    hideChartLoading:
        hideChartLoading,

    showChartLoading:
        showChartLoading

};


/* =========================================================
   GLOBAL COMPATIBILITY FUNCTIONS
   ========================================================= */

window.updateMarketTick =
    updateMarketTick;

window.setConnectionStatus =
    setConnectionStatus;

window.getCurrentSelection =
    getCurrentSelection;
```
