(function () {

    function setConnectionStatus(
        connected
    ) {

        const element =
            document.getElementById(
                "connectionStatus"
            );

        if (!element) {
            return;
        }

        if (connected) {

            element.textContent =
                "● Connected";

            element.classList.remove(
                "disconnected"
            );

            element.classList.add(
                "connected"
            );

        } else {

            element.textContent =
                "● Disconnected";

            element.classList.remove(
                "connected"
            );

            element.classList.add(
                "disconnected"
            );
        }
    }


    function updateMarketValue(
        id,
        value
    ) {

        const element =
            document.getElementById(id);

        if (!element) {
            return;
        }

        if (
            value === null
            ||
            value === undefined
        ) {

            element.textContent = "-";

            return;
        }

        const number =
            Number(value);

        element.textContent =
            Number.isFinite(number)
                ? number.toFixed(2)
                : String(value);
    }


    function updateContractLabels(
        data
    ) {

        const futureName =
            document.getElementById(
                "futureName"
            );

        const callName =
            document.getElementById(
                "callName"
            );

        const putName =
            document.getElementById(
                "putName"
            );


        if (futureName) {
            futureName.textContent =
                data?.future?.symbol || "-";
        }

        if (callName) {
            callName.textContent =
                data?.call?.symbol || "-";
        }

        if (putName) {
            putName.textContent =
                data?.put?.symbol || "-";
        }
    }


    window.setConnectionStatus =
        setConnectionStatus;

    window.updateMarketValue =
        updateMarketValue;

    window.updateContractLabels =
        updateContractLabels;


    window.TradingControls = {
        setConnectionStatus,
        updateMarketValue,
        updateContractLabels
    };

})();
