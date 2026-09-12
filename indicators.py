"""
indicators.py

Technical indicators used by the trading dashboard.

Currently:
    - Heikin Ashi
    - Smoothed Heikin Ashi (SHA)

SHA will be applied independently to:
    1. Future chart
    2. Call chart
    3. Put chart
"""

from typing import Any, Optional


# ============================================================
# Basic validation
# ============================================================

REQUIRED_OHLC = (
    "open",
    "high",
    "low",
    "close",
)


def _validate_candles(
    candles: list[dict[str, Any]],
) -> None:

    for index, candle in enumerate(candles):

        for field in REQUIRED_OHLC:

            if candle.get(field) is None:
                raise ValueError(
                    f"Candle {index} is missing '{field}'."
                )


# ============================================================
# Heikin Ashi
# ============================================================

def heikin_ashi(
    candles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Calculate standard Heikin Ashi candles.

    Formula:

        HA Close =
            (Open + High + Low + Close) / 4

        HA Open =
            (Previous HA Open + Previous HA Close) / 2

        HA High =
            max(High, HA Open, HA Close)

        HA Low =
            min(Low, HA Open, HA Close)

    The first HA Open is initialized using the original
    candle's Open and Close.
    """

    if not candles:
        return []

    _validate_candles(candles)

    result = []

    previous_ha_open: Optional[float] = None
    previous_ha_close: Optional[float] = None

    for candle in candles:

        open_price = float(candle["open"])
        high_price = float(candle["high"])
        low_price = float(candle["low"])
        close_price = float(candle["close"])

        # HA Close
        ha_close = (
            open_price
            + high_price
            + low_price
            + close_price
        ) / 4.0

        # HA Open
        if previous_ha_open is None:

            ha_open = (
                open_price + close_price
            ) / 2.0

        else:

            ha_open = (
                previous_ha_open
                + previous_ha_close
            ) / 2.0

        # HA High
        ha_high = max(
            high_price,
            ha_open,
            ha_close,
        )

        # HA Low
        ha_low = min(
            low_price,
            ha_open,
            ha_close,
        )

        result.append({
            "time": candle.get("time"),
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
            "volume": candle.get("volume"),
        })

        previous_ha_open = ha_open
        previous_ha_close = ha_close

    return result


# ============================================================
# Simple Moving Average
# ============================================================

def sma(
    values: list[float],
    period: int,
) -> list[Optional[float]]:
    """
    Simple Moving Average.

    Returns None until enough data exists.
    """

    if period <= 0:
        raise ValueError(
            "SMA period must be greater than zero."
        )

    result = []

    for index in range(len(values)):

        if index + 1 < period:

            result.append(None)
            continue

        window = values[
            index + 1 - period:
            index + 1
        ]

        result.append(
            sum(window) / period
        )

    return result


# ============================================================
# Exponential Moving Average
# ============================================================

def ema(
    values: list[float],
    period: int,
) -> list[Optional[float]]:
    """
    Exponential Moving Average.

    Standard recursive EMA calculation.
    """

    if period <= 0:
        raise ValueError(
            "EMA period must be greater than zero."
        )

    if not values:
        return []

    result = [None] * len(values)

    multiplier = 2.0 / (period + 1)

    # Seed with SMA.
    if len(values) < period:
        return result

    initial_average = (
        sum(values[:period]) / period
    )

    result[period - 1] = initial_average

    previous = initial_average

    for index in range(period, len(values)):

        current = (
            (values[index] - previous)
            * multiplier
        ) + previous

        result[index] = current
        previous = current

    return result


# ============================================================
# Smoothed OHLC
# ============================================================

def smooth_ohlc(
    candles: list[dict[str, Any]],
    period: int = 3,
    method: str = "ema",
) -> list[dict[str, Any]]:
    """
    Smooth OHLC values before the Heikin Ashi calculation.

    This is a generic SHA building block.

    IMPORTANT:
        The exact TradingView SHA implementation should replace
        this function's parameters/calculation once the complete
        Pine Script is provided.
    """

    if not candles:
        return []

    if period <= 0:
        raise ValueError(
            "Smoothing period must be greater than zero."
        )

    method = method.lower()

    if method not in {"ema", "sma"}:
        raise ValueError(
            "Smoothing method must be 'ema' or 'sma'."
        )

    smoothed = []

    for field in REQUIRED_OHLC:

        values = [
            float(candle[field])
            for candle in candles
        ]

        if method == "ema":
            values_smoothed = ema(
                values,
                period,
            )

        else:
            values_smoothed = sma(
                values,
                period,
            )

        for index, value in enumerate(
            values_smoothed
        ):

            if len(smoothed) <= index:
                smoothed.append(
                    {
                        "time": candles[index].get(
                            "time"
                        ),
                        "open": None,
                        "high": None,
                        "low": None,
                        "close": None,
                        "volume": candles[index].get(
                            "volume"
                        ),
                    }
                )

            if value is not None:
                smoothed[index][field] = value

    # Remove incomplete initial candles.
    return [
        candle
        for candle in smoothed
        if all(
            candle[field] is not None
            for field in REQUIRED_OHLC
        )
    ]


# ============================================================
# Smoothed Heikin Ashi
# ============================================================

def smoothed_heikin_ashi(
    candles: list[dict[str, Any]],
    smoothing_period: int = 3,
    smoothing_method: str = "ema",
) -> list[dict[str, Any]]:
    """
    Calculate Smoothed Heikin Ashi.

    Current generic pipeline:

        Raw OHLC
             ↓
        OHLC smoothing
             ↓
        Heikin Ashi
             ↓
        SHA candles

    The exact pipeline will be updated to match the user's
    complete TradingView Pine Script when provided.
    """

    if not candles:
        return []

    smoothed = smooth_ohlc(
        candles=candles,
        period=smoothing_period,
        method=smoothing_method,
    )

    return heikin_ashi(smoothed)


# ============================================================
# Candle direction
# ============================================================

def candle_direction(
    candle: dict[str, Any],
) -> str:
    """
    Return bullish / bearish / neutral.
    """

    open_price = candle.get("open")
    close_price = candle.get("close")

    if open_price is None or close_price is None:
        return "neutral"

    if close_price > open_price:
        return "bullish"

    if close_price < open_price:
        return "bearish"

    return "neutral"


# ============================================================
# Add SHA to chart data
# ============================================================

def add_sha(
    candles: list[dict[str, Any]],
    smoothing_period: int = 3,
    smoothing_method: str = "ema",
) -> list[dict[str, Any]]:
    """
    Convenience function used by the chart/data layer.

    Returns SHA candles with direction information.
    """

    sha_candles = smoothed_heikin_ashi(
        candles=candles,
        smoothing_period=smoothing_period,
        smoothing_method=smoothing_method,
    )

    for candle in sha_candles:

        candle["direction"] = candle_direction(
            candle
        )

    return sha_candles


# ============================================================
# Apply SHA to all three dashboard charts
# ============================================================

def calculate_dashboard_sha(
    future_candles: list[dict[str, Any]],
    call_candles: list[dict[str, Any]],
    put_candles: list[dict[str, Any]],
    smoothing_period: int = 3,
    smoothing_method: str = "ema",
) -> dict[str, list[dict[str, Any]]]:
    """
    Calculate SHA independently for all three charts.
    """

    return {
        "future": add_sha(
            future_candles,
            smoothing_period,
            smoothing_method,
        ),

        "call": add_sha(
            call_candles,
            smoothing_period,
            smoothing_method,
        ),

        "put": add_sha(
            put_candles,
            smoothing_period,
            smoothing_method,
        ),
    }
