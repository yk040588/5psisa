(function () {

    function sma(values, period) {

        const result = [];

        for (let i = 0; i < values.length; i++) {

            if (i + 1 < period) {
                result.push(null);
                continue;
            }

            let sum = 0;

            for (
                let j = i + 1 - period;
                j <= i;
                j++
            ) {
                sum += Number(values[j]);
            }

            result.push(sum / period);
        }

        return result;
    }


    function ema(values, period) {

        if (!values.length) {
            return [];
        }

        const alpha = 2 / (period + 1);

        const result = [];

        let previous = null;

        values.forEach(value => {

            if (previous === null) {
                previous = Number(value);
            } else {
                previous =
                    alpha * Number(value)
                    +
                    (1 - alpha) * previous;
            }

            result.push(previous);
        });

        return result;
    }


    function smooth(values, period) {
        return ema(values, period);
    }


    function smoothedHeikinAshi(
        candles,
        period = 3
    ) {

        if (!candles || !candles.length) {
            return [];
        }

        const ha = [];

        let previousOpen = null;
        let previousClose = null;

        candles.forEach(candle => {

            const o = Number(candle.open);
            const h = Number(candle.high);
            const l = Number(candle.low);
            const c = Number(candle.close);

            const close =
                (o + h + l + c) / 4;

            const open =
                previousOpen === null
                    ? (o + c) / 2
                    : (
                        previousOpen
                        +
                        previousClose
                    ) / 2;

            const high =
                Math.max(
                    h,
                    open,
                    close
                );

            const low =
                Math.min(
                    l,
                    open,
                    close
                );

            ha.push({
                timestamp: candle.timestamp,
                open,
                high,
                low,
                close
            });

            previousOpen = open;
            previousClose = close;
        });


        const opens = ema(
            ha.map(x => x.open),
            period
        );

        const highs = ema(
            ha.map(x => x.high),
            period
        );

        const lows = ema(
            ha.map(x => x.low),
            period
        );

        const closes = ema(
            ha.map(x => x.close),
            period
        );


        return ha.map((item, index) => ({

            timestamp: item.timestamp,

            open: opens[index],

            high: highs[index],

            low: lows[index],

            close: closes[index]

        }));
    }


    function rsi(values, period = 14) {

        if (values.length <= period) {
            return [];
        }

        const result =
            new Array(values.length)
                .fill(null);

        let gain = 0;
        let loss = 0;

        for (
            let i = 1;
            i <= period;
            i++
        ) {

            const change =
                values[i] - values[i - 1];

            if (change >= 0) {
                gain += change;
            } else {
                loss -= change;
            }
        }

        let avgGain = gain / period;
        let avgLoss = loss / period;

        result[period] =
            avgLoss === 0
                ? 100
                : 100 -
                    (
                        100 /
                        (
                            1 +
                            avgGain / avgLoss
                        )
                    );

        for (
            let i = period + 1;
            i < values.length;
            i++
        ) {

            const change =
                values[i] - values[i - 1];

            const currentGain =
                change > 0 ? change : 0;

            const currentLoss =
                change < 0 ? -change : 0;

            avgGain =
                (
                    avgGain * (period - 1)
                    +
                    currentGain
                ) / period;

            avgLoss =
                (
                    avgLoss * (period - 1)
                    +
                    currentLoss
                ) / period;

            result[i] =
                avgLoss === 0
                    ? 100
                    : 100 -
                        (
                            100 /
                            (
                                1 +
                                avgGain / avgLoss
                            )
                        );
        }

        return result;
    }


    window.TradingIndicators = {
        sma,
        ema,
        smooth,
        rsi,
        smoothedHeikinAshi
    };

})();
