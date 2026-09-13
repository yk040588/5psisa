from __future__ import annotations


def sma(values, period: int):

    if period <= 0:
        raise ValueError("period must be > 0")

    result = []

    for i in range(len(values)):

        if i + 1 < period:
            result.append(None)
            continue

        window = values[
            i + 1 - period:i + 1
        ]

        result.append(
            sum(window) / period
        )

    return result


def ema(values, period: int):

    if period <= 0:
        raise ValueError("period must be > 0")

    if not values:
        return []

    alpha = 2 / (period + 1)

    result = []

    previous = None

    for value in values:

        if previous is None:
            previous = float(value)
        else:
            previous = (
                alpha * float(value)
                + (1 - alpha) * previous
            )

        result.append(previous)

    return result


def smoothed_heikin_ashi(
    candles,
    period: int = 3,
):

    if not candles:
        return []

    ha = []

    previous_ha_open = None
    previous_ha_close = None

    for candle in candles:

        o = float(candle["open"])
        h = float(candle["high"])
        l = float(candle["low"])
        c = float(candle["close"])

        ha_close = (
            o + h + l + c
        ) / 4

        if previous_ha_open is None:

            ha_open = (
                o + c
            ) / 2

        else:

            ha_open = (
                previous_ha_open
                + previous_ha_close
            ) / 2

        ha_high = max(
            h,
            ha_open,
            ha_close,
        )

        ha_low = min(
            l,
            ha_open,
            ha_close,
        )

        ha.append(
            {
                "timestamp": candle["timestamp"],
                "open": ha_open,
                "high": ha_high,
                "low": ha_low,
                "close": ha_close,
            }
        )

        previous_ha_open = ha_open
        previous_ha_close = ha_close

    closes = [
        x["close"]
        for x in ha
    ]

    smoothed_close = ema(
        closes,
        period,
    )

    opens = [
        x["open"]
        for x in ha
    ]

    smoothed_open = ema(
        opens,
        period,
    )

    highs = [
        x["high"]
        for x in ha
    ]

    smoothed_high = ema(
        highs,
        period,
    )

    lows = [
        x["low"]
        for x in ha
    ]

    smoothed_low = ema(
        lows,
        period,
    )

    result = []

    for i, item in enumerate(ha):

        result.append(
            {
                "timestamp": item["timestamp"],
                "open": smoothed_open[i],
                "high": smoothed_high[i],
                "low": smoothed_low[i],
                "close": smoothed_close[i],
            }
        )

    return result
