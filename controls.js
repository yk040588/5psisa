/* =========================================================
   5PAISA TRADING DASHBOARD
   controls.js
   PHASE 1
   ========================================================= */

"use strict";


/* =========================================================
   CONFIGURATION
   ========================================================= */

const TRADING_CONTROLS_CONFIG = {

    supportedSymbols: [
        "NIFTY",
        "BANKNIFTY",
        "SENSEX",
        "CRUDEOIL",
        "NATURALGAS"
    ],

    maxOTMCalls: 15,

    maxOTMPuts: 15,

    tradingEnabled: false,

    ordersEnabled: false

};


/* =========================================================
   INTERNAL STATE
   ========================================================= */

const controlsState = {

    connected: false,

    symbol: "NIFTY",

    expiry: "",

    timeframe: "5m",

    future: null,

    call: null,

    put: null,

    calls: [],

    puts: [],

    futures: [],

    lastTicks: {},

    websocket: null

};


/* =========================================================
   DOM HELPERS
   ========================================================= */

function getElement(id) {

    return document.getElementById(id);

}


function setText(id, value) {

    const element = getElement(id);

    if (!element) {
        return;
    }

    element.textContent =
        value === null ||
        value === undefined ||
        value === ""
            ? "-"
            : String(value);

}


function setValue(id, value) {

    const element = getElement(id);

    if (!element) {
        return;
    }

    element.value =
        value === null ||
        value === undefined
            ? ""
            : String(value);

}


/* =========================================================
   NUMBER FORMAT
   ========================================================= */

function formatNumber(value, decimals = 2) {

    const number = Number(value);

    if (!Number.isFinite(number)) {

        return value === null ||
               value === undefined ||
               value === ""
            ? "-"
            : String(value);

    }

    return number.toFixed(decimals);

}


/* =========================================================
   CONNECTION STATUS
   ========================================================= */

function setConnectionStatus(connected) {

    const element =
        getElement("connection-status");

    controlsState.connected =
        Boolean(connected);

    if (!element) {
        return;
    }

    element.textContent =
        connected
            ? "● Connected"
            : "● Disconnected";

    element.classList.toggle(
        "connected",
        Boolean(connected)
    );

    element.classList.toggle(
        "disconnected",
        !connected
    );

}


/* =========================================================
   MARKET LTP
   ========================================================= */

function updateMarketValue(id, value) {

    const element =
        getElement(id);

    if (!element) {
        return;
    }

    element.textContent =
        formatNumber(value);

}


/* =========================================================
   FUTURE / CALL / PUT LTP
   ========================================================= */

function updateFutureLtp(value) {

    controlsState.lastTicks.future =
        value;

    updateMarketValue(
        "future-ltp",
        value
    );

}


function updateCallLtp(value) {

    controlsState.lastTicks.call =
        value;

    updateMarketValue(
        "call-ltp",
        value
    );

}


function updatePutLtp(value) {

    controlsState.lastTicks.put =
        value;

    updateMarketValue(
        "put-ltp",
        value
    );

}


/* =========================================================
   CONTRACT NAME
   ========================================================= */

function getContractSymbol(contract) {

    if (!contract) {
        return "-";
    }

    return (
        contract.symbol ??
        contract.trading_symbol ??
        contract.tradingSymbol ??
        contract.name ??
        contract.scrip_name ??
        contract.scripName ??
        "-"
    );

}


function getContractStrike(contract) {

    if (!contract) {
        return null;
    }

    return (
        contract.strike ??
        contract.StrikeRate ??
        contract.strike_price ??
        contract.strikePrice ??
        null
    );

}


function getContractOptionType(contract) {

    if (!contract) {
        return "";
    }

    return String(
        contract.option_type ??
        contract.optionType ??
        contract.OptionType ??
        ""
    ).toUpperCase();

}


/* =========================================================
   UPDATE CONTRACT LABELS
   ========================================================= */

function updateContractLabels(data = null) {

    if (data) {

        controlsState.future =
            data.future ??
            data.futures?.[0] ??
            controlsState.future;

        controlsState.call =
            data.call ??
            data.calls?.[0] ??
            controlsState.call;

        controlsState.put =
            data.put ??
            data.puts?.[0] ??
            controlsState.put;

    }


    setText(
        "future-symbol",
        getContractSymbol(
            controlsState.future
        )
    );


    setText(
        "call-symbol",
        getContractSymbol(
            controlsState.call
        )
    );


    setText(
        "put-symbol",
        getContractSymbol(
            controlsState.put
        )
    );


    setText(
        "future-contract",
        getContractSymbol(
            controlsState.future
        )
    );


    setText(
        "call-contract",
        getContractSymbol(
            controlsState.call
        )
    );


    setText(
        "put-contract",
        getContractSymbol(
            controlsState.put
        )
    );


    if (controlsState.lastTicks.future !== undefined) {

        updateFutureLtp(
            controlsState.lastTicks.future
        );

    }


    if (controlsState.lastTicks.call !== undefined) {

        updateCallLtp(
            controlsState.lastTicks.call
        );

    }


    if (controlsState.lastTicks.put !== undefined) {

        updatePutLtp(
            controlsState.lastTicks.put
        );

    }

}


/* =========================================================
   CONTRACT IDENTIFIER
   ========================================================= */

function getContractId(contract) {

    if (!contract) {
        return "";
    }

    return String(
        contract.scrip_code ??
        contract.scripCode ??
        contract.ScripCode ??
        contract.broker_token ??
        contract.token ??
        contract.instrument_token ??
        contract.instrumentToken ??
        contract.symbol ??
        ""
    );

}


/* =========================================================
   CONTRACT LABEL FOR SELECTOR
   ========================================================= */

function getContractLabel(contract) {

    if (!contract) {
        return "-";
    }


    const symbol =
        getContractSymbol(contract);

    const strike =
        getContractStrike(contract);

    const optionType =
        getContractOptionType(contract);


    if (
        symbol &&
        symbol !== "-"
    ) {

        return symbol;

    }


    if (
        strike !== null &&
        strike !== undefined &&
        optionType
    ) {

        return `${strike} ${optionType}`;

    }


    if (
        strike !== null &&
        strike !== undefined
    ) {

        return String(strike);

    }


    return getContractId(contract);

}


/* =========================================================
   OTM CONTRACT FILTER
   ========================================================= */

/*
 * Backend should preferably send only OTM contracts.
 *
 * This frontend safety filter keeps a maximum of:
 *
 * 15 Calls
 * 15 Puts
 *
 * It does NOT calculate the underlying ATM strike.
 * ATM/OTM determination must be done by backend using
 * the actual Future/LTP and instrument master.
 */

function limitOTMContracts(
    contracts,
    optionType,
    maxCount = 15
) {

    if (!Array.isArray(contracts)) {
        return [];
    }


    const normalizedType =
        String(optionType || "")
            .toUpperCase();


    const filtered =
        contracts.filter(
            contract => {

                const type =
                    getContractOptionType(
                        contract
                    );

                return (
                    !type ||
                    type === normalizedType
                );

            }
        );


    return filtered.slice(
        0,
        maxCount
    );

}


/* =========================================================
   POPULATE CALL / PUT SELECTOR
   ========================================================= */

function populateContractSelector(
    selectorId,
    contracts,
    selectedContract = null
) {

    const select =
        getElement(selectorId);

    if (!select) {
        return;
    }


    select.innerHTML = "";


    if (
        !Array.isArray(contracts) ||
        contracts.length === 0
    ) {

        const option =
            document.createElement("option");

        option.value = "";

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
                getContractId(
                    contract
                );

            option.value =
                value;

            option.textContent =
                getContractLabel(
                    contract
                );

            select.appendChild(
                option
            );

        }
    );


    if (selectedContract) {

        const selectedValue =
            getContractId(
                selectedContract
            );

        const exists =
            Array.from(
                select.options
            ).some(
                option =>
                    option.value ===
                    selectedValue
            );

        if (exists) {

            select.value =
                selectedValue;

        }

    }

}


/* =========================================================
   SET DASHBOARD DATA
   ========================================================= */

function setDashboardData(data) {

    if (!data) {
        return;
    }


    controlsState.symbol =
        data.symbol ??
        controlsState.symbol;


    controlsState.expiry =
        data.expiry ??
        controlsState.expiry;


    controlsState.futures =
        Array.isArray(data.futures)
            ? data.futures
            : data.future
                ? [data.future]
                : [];


    controlsState.calls =
        limitOTMContracts(
            data.calls ??
            (
                data.call
                    ? [data.call]
                    : []
            ),
            "CE",
            TRADING_CONTROLS_CONFIG.maxOTMCalls
        );


    controlsState.puts =
        limitOTMContracts(
            data.puts ??
            (
                data.put
                    ? [data.put]
                    : []
            ),
            "PE",
            TRADING_CONTROLS_CONFIG.maxOTMPuts
        );


    controlsState.future =
        controlsState.futures[0] ??
        null;


    if (
        !controlsState.call ||
        !controlsState.calls.some(
            contract =>
                getContractId(contract) ===
                getContractId(
                    controlsState.call
                )
        )
    ) {

        controlsState.call =
            controlsState.calls[0] ??
            null;

    }


    if (
        !controlsState.put ||
        !controlsState.puts.some(
            contract =>
                getContractId(contract) ===
                getContractId(
                    controlsState.put
                )
        )
    ) {

        controlsState.put =
            controlsState.puts[0] ??
            null;

    }


    populateContractSelector(
        "call-selector",
        controlsState.calls,
        controlsState.call
    );


    populateContractSelector(
        "put-selector",
        controlsState.puts,
        controlsState.put
    );


    updateContractLabels();


    updateSHAStatus();

}


/* =========================================================
   SHA STATUS
   ========================================================= */

function updateSHAStatus() {

    /*
     * Phase 1:
     * SHA is enabled by default on all
     * three charts.
     *
     * Actual SHA calculation/rendering
     * belongs to charts.js / indicators.js.
     */


    setSHAState(
        "future-chart",
        true
    );

    setSHAState(
        "call-chart",
        true
    );

    setSHAState(
        "put-chart",
        true
    );

}


function setSHAState(
    chartId,
    enabled
) {

    const chart =
        getElement(chartId);

    if (!chart) {
        return;
    }

    chart.dataset.sha =
        enabled
            ? "enabled"
            : "disabled";

}


/* =========================================================
   SELECT CURRENT CONTRACT
   ========================================================= */

function selectContract(
    type,
    contract
) {

    if (!contract) {
        return;
    }


    if (type === "future") {

        controlsState.future =
            contract;

    }


    if (type === "call") {

        controlsState.call =
            contract;

        setValue(
            "call-selector",
            getContractId(
                contract
            )
        );

    }


    if (type === "put") {

        controlsState.put =
            contract;

        setValue(
            "put-selector",
            getContractId(
                contract
            )
        );

    }


    updateContractLabels();


    emitSelectionChange();

}


/* =========================================================
   SELECTION STATE
   ========================================================= */

function getSelection() {

    return {

        symbol:
            controlsState.symbol,

        expiry:
            controlsState.expiry,

        timeframe:
            controlsState.timeframe,

        future:
            controlsState.future,

        call:
            controlsState.call,

        put:
            controlsState.put,

        callScripCode:
            getContractId(
                controlsState.call
            ),

        putScripCode:
            getContractId(
                controlsState.put
            ),

        futureScripCode:
            getContractId(
                controlsState.future
            )

    };

}


function emitSelectionChange() {

    window.dispatchEvent(
        new CustomEvent(
            "trading-dashboard-selection",
            {
                detail:
                    getSelection()
            }
        )
    );

}


/* =========================================================
   LIVE TICK NORMALIZATION
   ========================================================= */

function normalizeTick(tick) {

    if (!tick) {
        return null;
    }


    return {

        token:
            tick.Token ??
            tick.token ??
            tick.ScripCode ??
            tick.scripCode ??
            tick.instrument_token ??
            tick.instrumentToken,

        lastRate:
            Number(
                tick.LastRate ??
                tick.lastRate ??
                tick.LTP ??
                tick.ltp ??
                tick.last_price ??
                tick.lastPrice
            ),

        lastQty:
            tick.LastQty ??
            tick.lastQty ??
            tick.last_qty,

        high:
            tick.High ??
            tick.high,

        low:
            tick.Low ??
            tick.low,

        open:
            tick.OpenRate ??
            tick.openRate ??
            tick.open,

        previousClose:
            tick.PClose ??
            tick.pClose ??
            tick.previousClose,

        tickTime:
            tick.TickDt ??
            tick.tickDt ??
            tick.timestamp ??
            tick.time

    };

}


/* =========================================================
   APPLY LIVE TICK
   ========================================================= */

function applyLiveTick(
    tick,
    type = null
) {

    const normalized =
        normalizeTick(
            tick
        );

    if (!normalized) {
        return;
    }


    if (
        !Number.isFinite(
            normalized.lastRate
        )
    ) {

        return;

    }


    const token =
        String(
            normalized.token ??
            ""
        );


    const futureToken =
        getContractId(
            controlsState.future
        );

    const callToken =
        getContractId(
            controlsState.call
        );

    const putToken =
        getContractId(
            controlsState.put
        );


    if (
        type === "future" ||
        (
            token &&
            token === futureToken
        )
    ) {

        updateFutureLtp(
            normalized.lastRate
        );

        notifyChartTick(
            "future",
            normalized
        );

        return;

    }


    if (
        type === "call" ||
        (
            token &&
            token === callToken
        )
    ) {

        updateCallLtp(
            normalized.lastRate
        );

        notifyChartTick(
            "call",
            normalized
        );

        return;

    }


    if (
        type === "put" ||
        (
            token &&
            token === putToken
        )
    ) {

        updatePutLtp(
            normalized.lastRate
        );

        notifyChartTick(
            "put",
            normalized
        );

    }

}


/* =========================================================
   CHART TICK BRIDGE
   ========================================================= */

function notifyChartTick(
    chartType,
    tick
) {

    /*
     * Existing charts.js exposes
     * updateChartTick().
     */

    if (
        typeof window.updateChartTick ===
        "function"
    ) {

        window.updateChartTick({

            type:
                chartType,

            future:
                chartType === "future"
                    ? {
                        ltp:
                            tick.lastRate
                    }
                    : undefined,

            call:
                chartType === "call"
                    ? {
                        ltp:
                            tick.lastRate
                    }
                    : undefined,

            put:
                chartType === "put"
                    ? {
                        ltp:
                            tick.lastRate
                    }
                    : undefined,

            ltp:
                tick.lastRate,

            timestamp:
                tick.tickTime

        });

    }


    /*
     * Also broadcast a clean browser event
     * for a future improved charts.js.
     */

    window.dispatchEvent(
        new CustomEvent(
            "trading-dashboard-tick",
            {
                detail: {

                    type:
                        chartType,

                    ltp:
                        tick.lastRate,

                    timestamp:
                        tick.tickTime,

                    token:
                        tick.token

                }
            }
        )
    );

}


/* =========================================================
   XSTREAM MARKETFEED MESSAGE
   ========================================================= */

function handleMarketFeedMessage(message) {

    if (!message) {
        return;
    }


    let data =
        message;


    if (
        typeof message === "string"
    ) {

        try {

            data =
                JSON.parse(
                    message
                );

        } catch (error) {

            console.error(
                "Invalid market feed JSON:",
                error
            );

            return;

        }

    }


    /*
     * MarketFeedV3 can return one
     * object or an array of objects.
     */

    const ticks =
        Array.isArray(data)
            ? data
            : Array.isArray(
                data.Data
            )
                ? data.Data
                : Array.isArray(
                    data.data
                )
                    ? data.data
                    : [data];


    ticks.forEach(
        tick =>
            applyLiveTick(
                tick
            )
    );

}


/* =========================================================
   WEBSOCKET REGISTRATION
   ========================================================= */

function registerMarketWebSocket(
    websocket
) {

    if (!websocket) {
        return;
    }


    controlsState.websocket =
        websocket;


    websocket.addEventListener(
        "open",
        () => {

            setConnectionStatus(
                true
            );

        }
    );


    websocket.addEventListener(
        "close",
        () => {

            setConnectionStatus(
                false
            );

        }
    );


    websocket.addEventListener(
        "error",
        () => {

            setConnectionStatus(
                false
            );

        }
    );


    websocket.addEventListener(
        "message",
        event => {

            handleMarketFeedMessage(
                event.data
            );

        }
    );

}


/* =========================================================
   MANUAL CONNECTION UPDATE
   ========================================================= */

function updateConnectionState(
    connected
) {

    setConnectionStatus(
        Boolean(connected)
    );

}


/* =========================================================
   RESET
   ========================================================= */

function resetControls() {

    controlsState.future =
        null;

    controlsState.call =
        null;

    controlsState.put =
        null;

    controlsState.calls =
        [];

    controlsState.puts =
        [];

    controlsState.futures =
        [];

    controlsState.lastTicks =
        {};

    updateContractLabels();

}


/* =========================================================
   TRADING STATUS
   ========================================================= */

function isTradingEnabled() {

    return (
        TRADING_CONTROLS_CONFIG.tradingEnabled &&
        TRADING_CONTROLS_CONFIG.ordersEnabled
    );

}


/*
 * Phase 1 intentionally blocks order UI.
 */

function canPlaceOrder() {

    return isTradingEnabled();

}


/* =========================================================
   PUBLIC API
   ========================================================= */

window.setConnectionStatus =
    setConnectionStatus;

window.updateMarketValue =
    updateMarketValue;

window.updateContractLabels =
    updateContractLabels;

window.setDashboardControlsData =
    setDashboardData;

window.applyMarketTick =
    applyLiveTick;

window.handleMarketFeedMessage =
    handleMarketFeedMessage;

window.registerMarketWebSocket =
    registerMarketWebSocket;

window.updateConnectionState =
    updateConnectionState;

window.getTradingDashboardSelection =
    getSelection;

window.selectTradingContract =
    selectContract;

window.resetTradingControls =
    resetControls;

window.canPlaceOrder =
    canPlaceOrder;


/* =========================================================
   TRADING CONTROLS OBJECT
   ========================================================= */

window.TradingControls = {

    setConnectionStatus,

    updateMarketValue,

    updateContractLabels,

    setDashboardData,

    applyLiveTick,

    handleMarketFeedMessage,

    registerMarketWebSocket,

    updateConnectionState,

    getSelection,

    selectContract,

    resetControls,

    canPlaceOrder

};


/* =========================================================
   INITIAL UI STATE
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        setConnectionStatus(
            false
        );

        updateSHAStatus();

    }
);
