(function () {

    let socket = null;

    let reconnectTimer = null;

    let currentSelection = null;


    function getSocketUrl() {

        const protocol =
            location.protocol === "https:"
                ? "wss:"
                : "ws:";

        return (
            `${protocol}//${location.host}/ws`
        );
    }


    function connect() {

        if (
            socket
            &&
            (
                socket.readyState ===
                WebSocket.OPEN
                ||
                socket.readyState ===
                WebSocket.CONNECTING
            )
        ) {
            return;
        }


        try {

            socket =
                new WebSocket(
                    getSocketUrl()
                );

        } catch (error) {

            console.error(
                "WebSocket creation error:",
                error
            );

            scheduleReconnect();

            return;
        }


        socket.onopen = function () {

            window.setConnectionStatus?.(
                true
            );

            sendSelection();
        };


        socket.onclose = function () {

            window.setConnectionStatus?.(
                false
            );

            scheduleReconnect();
        };


        socket.onerror = function (error) {

            console.error(
                "WebSocket error:",
                error
            );
        };


        socket.onmessage = function (
            event
        ) {

            let message;

            try {

                message =
                    JSON.parse(
                        event.data
                    );

            } catch (error) {

                console.error(
                    "Invalid WebSocket data:",
                    event.data
                );

                return;
            }


            if (
                message.type ===
                "connection"
            ) {

                window.setConnectionStatus?.(
                    message.status ===
                    "connected"
                );

                return;
            }


            if (
                message.type ===
                "ack"
            ) {

                return;
            }


            if (
                message.type ===
                "market_data"
            ) {

                handleMarketData(
                    message
                );
            }
        };
    }


    function scheduleReconnect() {

        if (reconnectTimer) {
            return;
        }

        reconnectTimer =
            setTimeout(
                function () {

                    reconnectTimer =
                        null;

                    connect();

                },
                3000
            );
    }


    function sendSelection(
        selection
    ) {

        if (selection) {
            currentSelection =
                selection;
        }

        if (
            !socket
            ||
            socket.readyState !==
            WebSocket.OPEN
        ) {
            return;
        }


        socket.send(
            JSON.stringify({
                type: "selection",
                selection:
                    currentSelection || {}
            })
        );
    }


    function handleMarketData(
        message
    ) {

        const data =
            message.data || {};

        const future =
            data.future;

        const call =
            data.call;

        const put =
            data.put;


        window.updateMarketValue?.(
            "futureLtp",
            future?.ltp
        );

        window.updateMarketValue?.(
            "callLtp",
            call?.ltp
        );

        window.updateMarketValue?.(
            "putLtp",
            put?.ltp
        );


        window.updateContractLabels?.(
            data
        );


        window.updateChartTick?.(
            data
        );


        const status =
            document.getElementById(
                "statusMessage"
            );

        if (status) {

            if (
                future?.ltp
                ||
                call?.ltp
                ||
                put?.ltp
            ) {

                status.textContent =
                    "Live market data received";

            } else {

                status.textContent =
                    "Connected — waiting for market data...";
            }
        }
    }


    function setSelection(
        selection
    ) {

        currentSelection =
            selection;

        sendSelection();
    }


    window.tradingWebSocket = {

        connect,

        sendSelection,

        setSelection,

        get socket() {
            return socket;
        }

    };


    document.addEventListener(
        "DOMContentLoaded",
        () => {
            connect();
        }
    );

})();
