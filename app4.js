(function () {

    const state = {

        symbol: "NIFTY",

        expiry: null,

        timeframe: "5m",

        future: null,

        call: null,

        put: null,

        dashboard: null,

        initialized: false

    };


    const supportedSymbols = [
        "NIFTY",
        "BANKNIFTY",
        "SENSEX",
        "CRUDEOIL",
        "NATURALGAS"
    ];


    function element(id) {
        return document.getElementById(id);
    }


    function getCurrentSelection() {

        return {

            symbol:
                state.symbol,

            expiry:
                state.expiry,

            timeframe:
                state.timeframe,

            future:
                state.future,

            call:
                state.call,

            put:
                state.put
        };
    }


    async function loadDashboard() {

        const params =
            new URLSearchParams({

                symbol:
                    state.symbol,

                expiry:
                    state.expiry || ""
            });


        try {

            const response =
                await fetch(
                    `/api/dashboard?${params}`
                );

            if (!response.ok) {

                throw new Error(
                    await response.text()
                );
            }


            const data =
                await response.json();


            state.dashboard =
                data;


            state.expiry =
                data.expiry
                ||
                state.expiry;


            populateExpiries(
                data.expiries || []
            );


            state.future =
                data.future
                ||
                (
                    data.futures?.[0]
                    ||
                    null
                );


            populateOptions(
                "callSelect",
                data.calls || [],
                state.call
            );


            populateOptions(
                "putSelect",
                data.puts || [],
                state.put
            );


            if (!state.call) {

                state.call =
                    data.calls?.[0]
                    ||
                    null;
            }


            if (!state.put) {

                state.put =
                    data.puts?.[0]
                    ||
                    null;
            }


            updateLabels();


            if (
                window.setDashboardData
            ) {

                window.setDashboardData(
                    {
                        ...data,

                        future:
                            state.future,

                        call:
                            state.call,

                        put:
                            state.put
                    },
                    getCurrentSelection()
                );
            }


            if (
                window.tradingWebSocket
            ) {

                window.tradingWebSocket
                    .setSelection(
                        getCurrentSelection()
                    );
            }


            state.initialized = true;


        } catch (error) {

            console.error(
                "Dashboard error:",
                error
            );


            const status =
                element(
                    "statusMessage"
                );

            if (status) {

                status.textContent =
                    "Dashboard error: "
                    +
                    error.message;
            }
        }
    }


    function populateExpiries(
        expiries
    ) {

        const select =
            element(
                "expirySelect"
            );

        if (!select) {
            return;
        }


        select.innerHTML = "";


        expiries.forEach(
            expiry => {

                const option =
                    document.createElement(
                        "option"
                    );

                option.value =
                    expiry;

                option.textContent =
                    expiry;

                select.appendChild(
                    option
                );
            }
        );


        if (state.expiry) {

            select.value =
                state.expiry;

        } else if (
            expiries.length
        ) {

            state.expiry =
                expiries[0];

            select.value =
                state.expiry;
        }
    }


    function populateOptions(
        selectId,
        options,
        selected
    ) {

        const select =
            element(selectId);

        if (!select) {
            return;
        }


        select.innerHTML = "";


        options.forEach(
            optionData => {

                const option =
                    document.createElement(
                        "option"
                    );

                option.value =
                    String(
                        optionData.scrip_code
                        ??
                        optionData.broker_token
                    );

                option.textContent =
                    optionData.symbol;

                option.dataset.symbol =
                    optionData.symbol;

                option.dataset.strike =
                    optionData.strike ?? "";

                option.dataset.scripCode =
                    optionData.scrip_code
                    ??
                    optionData.broker_token;

                select.appendChild(
                    option
                );
            }
        );


        if (selected) {

            select.value =
                String(
                    selected.scrip_code
                    ??
                    selected.broker_token
                );
        }
    }


    function findSelectedContract(
        selectId
    ) {

        const select =
            element(selectId);

        if (!select) {
            return null;
        }


        const option =
            select.options[
                select.selectedIndex
            ];

        if (!option) {
            return null;
        }


        const scripCode =
            Number(
                option.dataset.scripCode
            );


        return {

            symbol:
                option.dataset.symbol,

            strike:
                option.dataset.strike
                    ? Number(
                        option.dataset.strike
                    )
                    : null,

            scrip_code:
                scripCode
        };
    }


    function updateLabels() {

        const futureName =
            element(
                "futureName"
            );

        const callName =
            element(
                "callName"
            );

        const putName =
            element(
                "putName"
            );


        if (futureName) {

            futureName.textContent =
                state.future?.symbol
                ||
                "-";
        }


        if (callName) {

            callName.textContent =
                state.call?.symbol
                ||
                "-";
        }


        if (putName) {

            putName.textContent =
                state.put?.symbol
                ||
                "-";
        }
    }


    function bindEvents() {

        const symbolSelect =
            element(
                "symbolSelect"
            );

        const expirySelect =
            element(
                "expirySelect"
            );

        const timeframeSelect =
            element(
                "timeframeSelect"
            );

        const callSelect =
            element(
                "callSelect"
            );

        const putSelect =
            element(
                "putSelect"
            );


        if (symbolSelect) {

            symbolSelect.addEventListener(
                "change",
                async function () {

                    state.symbol =
                        this.value;

                    state.expiry =
                        null;

                    state.call =
                        null;

                    state.put =
                        null;

                    await loadDashboard();
                }
            );
        }


        if (expirySelect) {

            expirySelect.addEventListener(
                "change",
                async function () {

                    state.expiry =
                        this.value;

                    state.call =
                        null;

                    state.put =
                        null;

                    await loadDashboard();
                }
            );
        }


        if (timeframeSelect) {

            timeframeSelect.addEventListener(
                "change",
                async function () {

                    state.timeframe =
                        this.value;

                    await window
                        .refreshCharts?.({
                            timeframe:
                                state.timeframe
                        });

                    window
                        .tradingWebSocket
                        ?.setSelection(
                            getCurrentSelection()
                        );
                }
            );
        }


        if (callSelect) {

            callSelect.addEventListener(
                "change",
                async function () {

                    state.call =
                        findSelectedContract(
                            "callSelect"
                        );

                    updateLabels();

                    await window
                        .refreshCallChart?.();

                    window
                        .tradingWebSocket
                        ?.setSelection(
                            getCurrentSelection()
                        );
                }
            );
        }


        if (putSelect) {

            putSelect.addEventListener(
                "change",
                async function () {

                    state.put =
                        findSelectedContract(
                            "putSelect"
                        );

                    updateLabels();

                    await window
                        .refreshPutChart?.();

                    window
                        .tradingWebSocket
                        ?.setSelection(
                            getCurrentSelection()
                        );
                }
            );
        }
    }


    function initialize() {

        const symbolSelect =
            element(
                "symbolSelect"
            );

        if (symbolSelect) {

            symbolSelect.value =
                supportedSymbols.includes(
                    state.symbol
                )
                    ? state.symbol
                    : "NIFTY";
        }


        const timeframeSelect =
            element(
                "timeframeSelect"
            );

        if (timeframeSelect) {

            timeframeSelect.value =
                state.timeframe;
        }


        bindEvents();

        loadDashboard();
    }


    window.updateMarketTick =
        function (data) {

            if (!data) {
                return;
            }

            if (data.future?.ltp) {

                window.updateMarketValue?.(
                    "futureLtp",
                    data.future.ltp
                );
            }

            if (data.call?.ltp) {

                window.updateMarketValue?.(
                    "callLtp",
                    data.call.ltp
                );
            }

            if (data.put?.ltp) {

                window.updateMarketValue?.(
                    "putLtp",
                    data.put.ltp
                );
            }
        };


    window.getCurrentSelection =
        getCurrentSelection;


    window.tradingDashboard = {
        state
    };


    document.addEventListener(
        "DOMContentLoaded",
        initialize
    );

})();
