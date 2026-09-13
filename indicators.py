```python
"""
Phase 1 Trading Dashboard - Technical Indicators

Purpose
-------
Provides local technical-indicator calculations for the 5paisa dashboard.

Phase 1 SHA
-----------
Our own implementation inspired by the standard Heikin-Ashi + EMA concept.

Pipeline:
    Raw OHLC
        ↓
    EMA smoothing of OHLC
        ↓
    Heikin-Ashi calculation
        ↓
    SHA output

There is NO TradingView dependency.
There is NO TradingView API.
There is NO paid indicator/library.

The same SHA calculation is used independently for:
    1. Future
    2. Call
    3. Put

Input candles are expected internally as:

{
    "timestamp": ...,
    "open": ...,
    "high": ...,
    "low": ...,
    "close": ...,
    "volume": ...
}

The normalizer also accepts common 5paisa/Xstream field names such as:
    Timestamp, Open, High, Low, Close, Volume

The functions are deliberately pure/local so they work with:
    - historical data
    - cached data
    - live-updated candles
    - offline data already available locally
"""

from __future__ import annotations

from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_OHLC = ("open", "high", "low", "close")

DEFAULT_SHA_PERIOD = 3


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def _to_float(value: Any) -> float | None:
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_value(candle: dict[str, Any], *names: str) -> Any:
    """
    Return the first available value from the supplied field names.

    Supports both our internal lowercase format and common Xstream names.
    """

    for name in names:
        if name in candle:
            return candle[name]

    return None


def _get_timestamp(candle: dict[str, Any]) -> Any:
    """Extract timestamp from internal or Xstream-style candle data."""

    return _get_value(
        candle,
        "timestamp",
        "time",
        "Timestamp",
        "Time",
        "datetime",
        "DateTime",
    )


def normalize_candle(candle: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize one candle into the dashboard's internal format.

    Supported input examples:

        {
            "timestamp": ...,
            "open": ...,
            "high": ...,
            "low": ...,
            "close": ...,
            "volume": ...
        }

    or Xstream-style:

        {
            "Timestamp": ...,
            "Open": ...,
            "High": ...,
            "Low": ...,
            "Close": ...,
            "Volume": ...
        }
    """

    if not isinstance(candle, dict):
        raise TypeError("Candle must be a dictionary.")

    open_price = _to_float(
        _get_value(candle, "open", "Open", "OPEN")
    )
    high_price = _to_float(
        _get_value(candle, "high", "High", "HIGH")
    )
    low_price = _to_float(
        _get_value(candle, "low", "Low", "LOW")
    )
    close_price = _to_float(
        _get_value(candle, "close", "Close", "CLOSE")
    )

    if (
        open_price is None
        or high_price is None
        or low_price is None
        or close_price is None
    ):
        raise ValueError(
            "Candle must contain valid open, high, low and close values."
        )

    volume = _to_float(
        _get_value(
            candle,
            "volume",
            "Volume",
            "VOL",
            "vol",
        )
    )

    normalized: dict[str, Any] = {
        "timestamp": _get_timestamp(candle),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
    }

    if volume is not None:
        normalized["volume"] = volume

    return normalized


def normalize_candles(
    candles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize a complete candle series."""

    if candles is None:
        return []

    result: list[dict[str, Any]] = []

    for candle in candles:
        result.append(normalize_candle(candle))

    return result


def _validate_period(period: int) -> int:
    """Validate an indicator period."""

    if not isinstance(period, int):
        raise TypeError("Period must be an integer.")

    if period <= 0:
        raise ValueError("Period must be greater than zero.")

    return period


# ---------------------------------------------------------------------------
# Simple Moving Average
# ---------------------------------------------------------------------------

def sma(
    values: Iterable[float | None],
    period: int,
) -> list[float | None]:
    """
    Calculate Simple Moving Average.

    Until enough values are available, None is returned.

    Example:
        values = [10, 20, 30]
        period = 2

        result = [None, 15, 25]
    """

    period = _validate_period(period)

    source = list(values)

    result: list[float | None] = [None] * len(source)

    window: list[float] = []

    for index, value in enumerate(source):
        if value is None:
            window.clear()
            continue

        window.append(float(value))

        if len(window) > period:
            window.pop(0)

        if len(window) == period:
            result[index] = sum(window) / period

    return result


# ---------------------------------------------------------------------------
# Exponential Moving Average
# ---------------------------------------------------------------------------

def ema(
    values: Iterable[float | None],
    period: int,
) -> list[float | None]:
    """
    Calculate EMA using SMA seeding.

    Formula after the initial seed:

        EMA = (Value - Previous EMA) * Multiplier + Previous EMA

    Multiplier:

        2 / (period + 1)

    The first EMA value is seeded from the first complete SMA period.

    This gives a stable and deterministic result for historical candles.
    """

    period = _validate_period(period)

    source = list(values)

    result: list[float | None] = [None] * len(source)

    multiplier = 2.0 / (period + 1.0)

    valid_values: list[float] = []

    previous_ema: float | None = None

    for index, value in enumerate(source):

        if value is None:
            continue

        current = float(value)

        valid_values.append(current)

        # Initial EMA seed = SMA of first period values.
        if previous_ema is None:

            if len(valid_values) < period:
                continue

            previous_ema = sum(valid_values[-period:]) / period
            result[index] = previous_ema
            continue

        # Standard recursive EMA.
        previous_ema = (
            (current - previous_ema) * multiplier
            + previous_ema
        )

        result[index] = previous_ema

    return result


# ---------------------------------------------------------------------------
# Standard Heikin-Ashi
# ---------------------------------------------------------------------------

def heikin_ashi(
    candles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Calculate standard Heikin-Ashi candles.

    HA Close:

        (Open + High + Low + Close) / 4

    HA Open:

        First candle:
            (Open + Close) / 2

        Following candles:
            (Previous HA Open + Previous HA Close) / 2

    HA High:

        max(High, HA Open, HA Close)

    HA Low:

        min(Low, HA Open, HA Close)

    Original timestamp and volume are preserved.
    """

    normalized = normalize_candles(candles)

    if not normalized:
        return []

    result: list[dict[str, Any]] = []

    previous_ha_open: float | None = None
    previous_ha_close: float | None = None

    for candle in normalized:

        open_price = candle["open"]
        high_price = candle["high"]
        low_price = candle["low"]
        close_price = candle["close"]

        ha_close = (
            open_price
            + high_price
            + low_price
            + close_price
        ) / 4.0

        if previous_ha_open is None:
            ha_open = (open_price + close_price) / 2.0
        else:
            ha_open = (
                previous_ha_open
                + previous_ha_close
            ) / 2.0

        ha_high = max(
            high_price,
            ha_open,
            ha_close,
        )

        ha_low = min(
            low_price,
            ha_open,
            ha_close,
        )

        output: dict[str, Any] = {
            "timestamp": candle.get("timestamp"),
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
        }

        if "volume" in candle:
            output["volume"] = candle["volume"]

        result.append(output)

        previous_ha_open = ha_open
        previous_ha_close = ha_close

    return result


# ---------------------------------------------------------------------------
# SHA - Our Phase 1 implementation
# ---------------------------------------------------------------------------

def smoothed_heikin_ashi(
    candles: Iterable[dict[str, Any]],
    smoothing_period: int = DEFAULT_SHA_PERIOD,
    smoothing_method: str = "ema",
) -> list[dict[str, Any]]:
    """
    Calculate our Phase 1 Smoothed Heikin-Ashi (SHA).

    IMPORTANT
    ---------
    This is our own local implementation.

    It uses the well-known mathematical concepts of:
        1. OHLC smoothing
        2. Heikin-Ashi calculation

    No TradingView code, API, library or paid service is used.

    Pipeline:

        Raw OHLC
            ↓
        EMA/SMA smoothing
            ↓
        Heikin-Ashi
            ↓
        SHA candles

    Parameters
    ----------
    candles:
        Raw OHLC candles.

    smoothing_period:
        Default = 3.

    smoothing_method:
        "ema" or "sma"

    Returns
    -------
    list[dict]
        SHA candles with:
            timestamp
            open
            high
            low
            close
            volume (when available)
    """

    period = _validate_period(smoothing_period)

    method = str(smoothing_method).lower().strip()

    if method not in {"ema", "sma"}:
        raise ValueError(
            "smoothing_method must be either 'ema' or 'sma'."
        )

    normalized = normalize_candles(candles)

    if not normalized:
        return []

    opens = [candle["open"] for candle in normalized]
    highs = [candle["high"] for candle in normalized]
    lows = [candle["low"] for candle in normalized]
    closes = [candle["close"] for candle in normalized]

    if method == "ema":
        smooth_open = ema(opens, period)
        smooth_high = ema(highs, period)
        smooth_low = ema(lows, period)
        smooth_close = ema(closes, period)
    else:
        smooth_open = sma(opens, period)
        smooth_high = sma(highs, period)
        smooth_low = sma(lows, period)
        smooth_close = sma(closes, period)

    smoothed_ohlc: list[dict[str, Any]] = []

    for index, candle in enumerate(normalized):

        o = smooth_open[index]
        h = smooth_high[index]
        l = smooth_low[index]
        c = smooth_close[index]

        # Initial smoothing period does not have a complete value.
        if (
            o is None
            or h is None
            or l is None
            or c is None
        ):
            continue

        smoothed_ohlc.append(
            {
                "timestamp": candle.get("timestamp"),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                **(
                    {"volume": candle["volume"]}
                    if "volume" in candle
                    else {}
                ),
            }
        )

    if not smoothed_ohlc:
        return []

    return heikin_ashi(smoothed_ohlc)


# ---------------------------------------------------------------------------
# SHA with direction
# ---------------------------------------------------------------------------

def add_sha_direction(
    candles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Add candle direction to SHA candles.

    direction:
        "bullish"
        "bearish"
        "neutral"
    """

    result: list[dict[str, Any]] = []

    for candle in candles:

        output = dict(candle)

        open_price = candle["open"]
        close_price = candle["close"]

        if close_price > open_price:
            direction = "bullish"
        elif close_price < open_price:
            direction = "bearish"
        else:
            direction = "neutral"

        output["direction"] = direction

        result.append(output)

    return result


# ---------------------------------------------------------------------------
# Combined SHA
# ---------------------------------------------------------------------------

def add_sha(
    candles: Iterable[dict[str, Any]],
    smoothing_period: int = DEFAULT_SHA_PERIOD,
    smoothing_method: str = "ema",
) -> list[dict[str, Any]]:
    """
    Calculate SHA and add bullish/bearish direction.
    """

    sha = smoothed_heikin_ashi(
        candles,
        smoothing_period=smoothing_period,
        smoothing_method=smoothing_method,
    )

    return add_sha_direction(sha)


# ---------------------------------------------------------------------------
# Candle direction
# ---------------------------------------------------------------------------

def candle_direction(
    candle: dict[str, Any],
) -> str:
    """
    Return direction of a candle.

    Returns:
        bullish
        bearish
        neutral
    """

    open_price = _to_float(
        _get_value(candle, "open", "Open")
    )

    close_price = _to_float(
        _get_value(candle, "close", "Close")
    )

    if open_price is None or close_price is None:
        raise ValueError(
            "Candle must contain valid open and close values."
        )

    if close_price > open_price:
        return "bullish"

    if close_price < open_price:
        return "bearish"

    return "neutral"


# ---------------------------------------------------------------------------
# Dashboard SHA
# ---------------------------------------------------------------------------

def calculate_dashboard_sha(
    future_candles: Iterable[dict[str, Any]] | None = None,
    call_candles: Iterable[dict[str, Any]] | None = None,
    put_candles: Iterable[dict[str, Any]] | None = None,
    smoothing_period: int = DEFAULT_SHA_PERIOD,
    smoothing_method: str = "ema",
) -> dict[str, list[dict[str, Any]]]:
    """
    Calculate SHA independently for all three Phase 1 charts.

    Future:
        Future candles → Future SHA

    Call:
        Selected Call candles → Call SHA

    Put:
        Selected Put candles → Put SHA

    Each chart has its own independent SHA calculation.
    """

    future = (
        list(future_candles)
        if future_candles is not None
        else []
    )

    call = (
        list(call_candles)
        if call_candles is not None
        else []
    )

    put = (
        list(put_candles)
        if put_candles is not None
        else []
    )

    return {
        "future": add_sha(
            future,
            smoothing_period=smoothing_period,
            smoothing_method=smoothing_method,
        ),
        "call": add_sha(
            call,
            smoothing_period=smoothing_period,
            smoothing_method=smoothing_method,
        ),
        "put": add_sha(
            put,
            smoothing_period=smoothing_period,
            smoothing_method=smoothing_method,
        ),
    }


# ---------------------------------------------------------------------------
# Utility: latest SHA candle
# ---------------------------------------------------------------------------

def latest_sha(
    candles: Iterable[dict[str, Any]],
    smoothing_period: int = DEFAULT_SHA_PERIOD,
    smoothing_method: str = "ema",
) -> dict[str, Any] | None:
    """
    Return the latest SHA candle.

    Useful for:
        - dashboard status
        - future SHA state
        - call SHA state
        - put SHA state
        - future live-candle updates
    """

    result = add_sha(
        candles,
        smoothing_period=smoothing_period,
        smoothing_method=smoothing_method,
    )

    if not result:
        return None

    return result[-1]


# ---------------------------------------------------------------------------
# Utility: update last candle
# ---------------------------------------------------------------------------

def update_last_candle(
    candles: Iterable[dict[str, Any]],
    *,
    close: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: float | None = None,
) -> list[dict[str, Any]]:
    """
    Return a copy of the candle list with the latest candle updated.

    This is useful when a live Xstream tick changes the currently forming
    candle.

    Rules:
        close → latest close
        high  → max(current high, supplied high)
        low   → min(current low, supplied low)
        volume → supplied volume when available

    The original input list is never modified.
    """

    result = normalize_candles(candles)

    if not result:
        return result

    last = result[-1]

    if close is not None:
        close_value = float(close)
        last["close"] = close_value

        # If only LTP/close is received, the current candle's
        # high/low must still contain the new price.
        last["high"] = max(
            float(last["high"]),
            close_value,
        )

        last["low"] = min(
            float(last["low"]),
            close_value,
        )

    if high is not None:
        last["high"] = max(
            float(last["high"]),
            float(high),
        )

    if low is not None:
        last["low"] = min(
            float(last["low"]),
            float(low),
        )

    if volume is not None:
        last["volume"] = float(volume)

    return result


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "REQUIRED_OHLC",
    "DEFAULT_SHA_PERIOD",
    "normalize_candle",
    "normalize_candles",
    "sma",
    "ema",
    "heikin_ashi",
    "smoothed_heikin_ashi",
    "add_sha_direction",
    "add_sha",
    "candle_direction",
    "calculate_dashboard_sha",
    "latest_sha",
    "update_last_candle",
]
```
