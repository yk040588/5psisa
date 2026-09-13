```python
"""
5paisa Trading Dashboard
Phase 1 Technical Indicators

SHA IMPLEMENTATION
------------------
This module implements our own Python version of the
Smoothed Heiken Ashi calculation.

Reference calculation concept:

    Raw OHLC
        ↓
    BEFORE HA smoothing
        EMA(10)
        ↓
    Heiken Ashi
        ↓
    AFTER HA smoothing
        EMA(10)
        ↓
    Final SHA

The calculation is inspired by the mathematical pipeline of the
provided Smoothed Heiken Ashi Pine Script, but this module does NOT
use:

    - TradingView
    - TradingView API
    - TradingView libraries
    - wallneradam/TAExt
    - any paid indicator
    - any external indicator service

Everything is calculated locally in Python.

Phase 1 default:
    Before HA length      = 10
    Before HA MA          = EMA
    After HA length       = 10
    After HA MA           = EMA

The architecture supports SMA as an additional local MA option.
EMA remains the Phase 1 default.

Supported charts:
    - Future
    - Call
    - Put
"""

from __future__ import annotations

from typing import Any, Iterable


# ============================================================================
# DEFAULT SETTINGS
# ============================================================================

DEFAULT_HA_SMOOTH_LENGTH = 10
DEFAULT_HA_AFTER_SMOOTH_LENGTH = 10

DEFAULT_HA_SMOOTH_MA_TYPE = "EMA"
DEFAULT_HA_AFTER_SMOOTH_MA_TYPE = "EMA"

DEFAULT_RSI_PERIOD = 14


REQUIRED_OHLC = (
    "open",
    "high",
    "low",
    "close",
)


# ============================================================================
# BASIC HELPERS
# ============================================================================

def _to_float(value: Any) -> float | None:
    """Safely convert a value to float."""

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_value(
    candle: dict[str, Any],
    *names: str,
) -> Any:
    """
    Return the first available field.

    Supports both our internal fields and common
    5paisa/Xstream fields.
    """

    for name in names:
        if name in candle:
            return candle[name]

    return None


def _get_timestamp(
    candle: dict[str, Any],
) -> Any:
    """Extract timestamp from a candle."""

    return _get_value(
        candle,
        "timestamp",
        "Timestamp",
        "time",
        "Time",
        "datetime",
        "DateTime",
    )


def _validate_period(period: int) -> int:
    """Validate moving-average period."""

    if not isinstance(period, int):
        raise TypeError("period must be an integer")

    if period <= 0:
        raise ValueError("period must be greater than zero")

    return period


# ============================================================================
# CANDLE NORMALIZATION
# ============================================================================

def normalize_candle(
    candle: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize one candle.

    Internal format:

        {
            "timestamp": ...,
            "open": ...,
            "high": ...,
            "low": ...,
            "close": ...,
            "volume": ...
        }

    Supports Xstream-style fields:

        Timestamp
        Open
        High
        Low
        Close
        Volume
    """

    if not isinstance(candle, dict):
        raise TypeError("candle must be a dictionary")

    open_price = _to_float(
        _get_value(
            candle,
            "open",
            "Open",
            "OPEN",
        )
    )

    high_price = _to_float(
        _get_value(
            candle,
            "high",
            "High",
            "HIGH",
        )
    )

    low_price = _to_float(
        _get_value(
            candle,
            "low",
            "Low",
            "LOW",
        )
    )

    close_price = _to_float(
        _get_value(
            candle,
            "close",
            "Close",
            "CLOSE",
        )
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

    result: dict[str, Any] = {
        "timestamp": _get_timestamp(candle),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
    }

    if volume is not None:
        result["volume"] = volume

    return result


def normalize_candles(
    candles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize a complete candle series."""

    if candles is None:
        return []

    return [
        normalize_candle(candle)
        for candle in candles
    ]


# ============================================================================
# SIMPLE MOVING AVERAGE
# ============================================================================

def sma(
    values: Iterable[float | None],
    period: int,
) -> list[float | None]:
    """
    Simple Moving Average.

    Example:

        values = [10, 20, 30]
        period = 2

        result = [None, 15, 25]
    """

    period = _validate_period(period)

    source = list(values)

    result: list[float | None] = [
        None
        for _ in source
    ]

    window: list[float] = []

    for index, value in enumerate(source):

        if value is None:
            window.clear()
            continue

        window.append(float(value))

        if len(window) > period:
            window.pop(0)

        if len(window) == period:
            result[index] = (
                sum(window) / period
            )

    return result


# ============================================================================
# EXPONENTIAL MOVING AVERAGE
# ============================================================================

def ema(
    values: Iterable[float | None],
    period: int,
) -> list[float | None]:
    """
    Exponential Moving Average.

    EMA multiplier:

        2 / (period + 1)

    The first EMA value is seeded using the SMA
    of the first complete period.

    This gives deterministic historical calculations.
    """

    period = _validate_period(period)

    source = list(values)

    result: list[float | None] = [
        None
        for _ in source
    ]

    if not source:
        return result

    multiplier = 2.0 / (
        period + 1.0
    )

    valid_values: list[float] = []

    previous_ema: float | None = None

    for index, value in enumerate(source):

        if value is None:
            continue

        current = float(value)

        valid_values.append(current)

        # Initial EMA seed.
        if previous_ema is None:

            if len(valid_values) < period:
                continue

            previous_ema = (
                sum(
                    valid_values[-period:]
                ) / period
            )

            result[index] = previous_ema

            continue

        previous_ema = (
            (
                current - previous_ema
            ) * multiplier
            + previous_ema
        )

        result[index] = previous_ema

    return result


# ============================================================================
# GENERIC MOVING AVERAGE
# ============================================================================

def moving_average(
    values: Iterable[float | None],
    period: int,
    ma_type: str = "EMA",
) -> list[float | None]:
    """
    Moving-average dispatcher.

    Phase 1 supported:
        EMA
        SMA

    EMA is the default because the provided SHA configuration
    uses EMA.
    """

    ma_type = str(
        ma_type
    ).upper().strip()

    if ma_type == "EMA":
        return ema(values, period)

    if ma_type == "SMA":
        return sma(values, period)

    raise ValueError(
        f"Unsupported MA type: {ma_type}. "
        "Phase 1 supports EMA and SMA."
    )


# ============================================================================
# STANDARD HEIKEN ASHI
# ============================================================================

def heikin_ashi(
    candles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Calculate standard Heiken Ashi candles.

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
    """

    normalized = normalize_candles(
        candles
    )

    if not normalized:
        return []

    result: list[dict[str, Any]] = []

    previous_open: float | None = None
    previous_close: float | None = None

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

        if previous_open is None:

            ha_open = (
                open_price
                + close_price
            ) / 2.0

        else:

            ha_open = (
                previous_open
                + previous_close
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

        result_candle: dict[str, Any] = {
            "timestamp": candle.get(
                "timestamp"
            ),
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
        }

        if "volume" in candle:
            result_candle["volume"] = (
                candle["volume"]
            )

        result.append(result_candle)

        previous_open = ha_open
        previous_close = ha_close

    return result


# ============================================================================
# STAGE 1 - BEFORE HA SMOOTHING
# ============================================================================

def smooth_ohlc_before_ha(
    candles: Iterable[dict[str, Any]],
    smooth_length: int = DEFAULT_HA_SMOOTH_LENGTH,
    smooth_ma_type: str = DEFAULT_HA_SMOOTH_MA_TYPE,
) -> list[dict[str, Any]]:
    """
    Stage 1 of our SHA.

    Raw OHLC
        ↓
    Moving average
        ↓
    Smoothed OHLC

    Default:

        length = 10
        MA = EMA
    """

    smooth_length = _validate_period(
        smooth_length
    )

    normalized = normalize_candles(
        candles
    )

    if not normalized:
        return []

    opens = [
        candle["open"]
        for candle in normalized
    ]

    highs = [
        candle["high"]
        for candle in normalized
    ]

    lows = [
        candle["low"]
        for candle in normalized
    ]

    closes = [
        candle["close"]
        for candle in normalized
    ]

    smooth_open = moving_average(
        opens,
        smooth_length,
        smooth_ma_type,
    )

    smooth_high = moving_average(
        highs,
        smooth_length,
        smooth_ma_type,
    )

    smooth_low = moving_average(
        lows,
        smooth_length,
        smooth_ma_type,
    )

    smooth_close = moving_average(
        closes,
        smooth_length,
        smooth_ma_type,
    )

    result: list[dict[str, Any]] = []

    for index, candle in enumerate(
        normalized
    ):

        o = smooth_open[index]
        h = smooth_high[index]
        l = smooth_low[index]
        c = smooth_close[index]

        if (
            o is None
            or h is None
            or l is None
            or c is None
        ):
            continue

        output: dict[str, Any] = {
            "timestamp": candle.get(
                "timestamp"
            ),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
        }

        if "volume" in candle:
            output["volume"] = (
                candle["volume"]
            )

        result.append(output)

    return result


# ============================================================================
# STAGE 2 - AFTER HA SMOOTHING
# ============================================================================

def smooth_ha_after(
    ha_candles: Iterable[dict[str, Any]],
    after_smooth_length: int = (
        DEFAULT_HA_AFTER_SMOOTH_LENGTH
    ),
    after_smooth_ma_type: str = (
        DEFAULT_HA_AFTER_SMOOTH_MA_TYPE
    ),
) -> list[dict[str, Any]]:
    """
    Stage 2 of our SHA.

    Heiken Ashi
        ↓
    Moving average
        ↓
    Final Smoothed Heiken Ashi
    """

    after_smooth_length = _validate_period(
        after_smooth_length
    )

    normalized = normalize_candles(
        ha_candles
    )

    if not normalized:
        return []

    opens = [
        candle["open"]
        for candle in normalized
    ]

    highs = [
        candle["high"]
        for candle in normalized
    ]

    lows = [
        candle["low"]
        for candle in normalized
    ]

    closes = [
        candle["close"]
        for candle in normalized
    ]

    smooth_open = moving_average(
        opens,
        after_smooth_length,
        after_smooth_ma_type,
    )

    smooth_high = moving_average(
        highs,
        after_smooth_length,
        after_smooth_ma_type,
    )

    smooth_low = moving_average(
        lows,
        after_smooth_length,
        after_smooth_ma_type,
    )

    smooth_close = moving_average(
        closes,
        after_smooth_length,
        after_smooth_ma_type,
    )

    result: list[dict[str, Any]] = []

    for index, candle in enumerate(
        normalized
    ):

        o = smooth_open[index]
        h = smooth_high[index]
        l = smooth_low[index]
        c = smooth_close[index]

        if (
            o is None
            or h is None
            or l is None
            or c is None
        ):
            continue

        output: dict[str, Any] = {
            "timestamp": candle.get(
                "timestamp"
            ),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
        }

        if "volume" in candle:
            output["volume"] = (
                candle["volume"]
            )

        result.append(output)

    return result


# ============================================================================
# FINAL SHA
# ============================================================================

def smoothed_heikin_ashi(
    candles: Iterable[dict[str, Any]],
    smooth_length: int = DEFAULT_HA_SMOOTH_LENGTH,
    smooth_ma_type: str = DEFAULT_HA_SMOOTH_MA_TYPE,
    after_smooth_length: int = (
        DEFAULT_HA_AFTER_SMOOTH_LENGTH
    ),
    after_smooth_ma_type: str = (
        DEFAULT_HA_AFTER_SMOOTH_MA_TYPE
    ),
) -> list[dict[str, Any]]:
    """
    Calculate Phase 1 Smoothed Heiken Ashi.

    FINAL PIPELINE:

        Raw OHLC
             ↓
        BEFORE HA
        EMA(10)
             ↓
        Heiken Ashi
             ↓
        AFTER HA
        EMA(10)
             ↓
        FINAL SHA
    """

    # ------------------------------------------------------------
    # Stage 1
    # ------------------------------------------------------------

    before_ha = smooth_ohlc_before_ha(
        candles,
        smooth_length=smooth_length,
        smooth_ma_type=smooth_ma_type,
    )

    if not before_ha:
        return []

    # ------------------------------------------------------------
    # Heiken Ashi
    # ------------------------------------------------------------

    ha = heikin_ashi(
        before_ha
    )

    if not ha:
        return []

    # ------------------------------------------------------------
    # Stage 2
    # ------------------------------------------------------------

    final_sha = smooth_ha_after(
        ha,
        after_smooth_length=after_smooth_length,
        after_smooth_ma_type=after_smooth_ma_type,
    )

    return final_sha


# ============================================================================
# SHA DIRECTION
# ============================================================================

def add_sha_direction(
    candles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Add bullish/bearish/neutral direction.

    Bullish:
        close > open

    Bearish:
        close < open

    Neutral:
        close == open
    """

    result: list[dict[str, Any]] = []

    for candle in candles:

        output = dict(candle)

        open_price = float(
            candle["open"]
        )

        close_price = float(
            candle["close"]
        )

        if close_price > open_price:
            direction = "bullish"

        elif close_price < open_price:
            direction = "bearish"

        else:
            direction = "neutral"

        output["direction"] = direction

        result.append(output)

    return result


def add_sha(
    candles: Iterable[dict[str, Any]],
    smooth_length: int = DEFAULT_HA_SMOOTH_LENGTH,
    smooth_ma_type: str = DEFAULT_HA_SMOOTH_MA_TYPE,
    after_smooth_length: int = (
        DEFAULT_HA_AFTER_SMOOTH_LENGTH
    ),
    after_smooth_ma_type: str = (
        DEFAULT_HA_AFTER_SMOOTH_MA_TYPE
    ),
) -> list[dict[str, Any]]:
    """
    Calculate final SHA and add direction.
    """

    sha = smoothed_heikin_ashi(
        candles,
        smooth_length=smooth_length,
        smooth_ma_type=smooth_ma_type,
        after_smooth_length=after_smooth_length,
        after_smooth_ma_type=after_smooth_ma_type,
    )

    return add_sha_direction(
        sha
    )


# ============================================================================
# CANDLE DIRECTION
# ============================================================================

def candle_direction(
    candle: dict[str, Any],
) -> str:
    """Return bullish, bearish or neutral."""

    open_price = _to_float(
        _get_value(
            candle,
            "open",
            "Open",
        )
    )

    close_price = _to_float(
        _get_value(
            candle,
            "close",
            "Close",
        )
    )

    if (
        open_price is None
        or close_price is None
    ):
        raise ValueError(
            "Candle must contain valid open and close values."
        )

    if close_price > open_price:
        return "bullish"

    if close_price < open_price:
        return "bearish"

    return "neutral"


# ============================================================================
# DASHBOARD SHA
# ============================================================================

def calculate_dashboard_sha(
    future_candles: Iterable[dict[str, Any]] | None = None,
    call_candles: Iterable[dict[str, Any]] | None = None,
    put_candles: Iterable[dict[str, Any]] | None = None,
    smooth_length: int = DEFAULT_HA_SMOOTH_LENGTH,
    smooth_ma_type: str = DEFAULT_HA_SMOOTH_MA_TYPE,
    after_smooth_length: int = (
        DEFAULT_HA_AFTER_SMOOTH_LENGTH
    ),
    after_smooth_ma_type: str = (
        DEFAULT_HA_AFTER_SMOOTH_MA_TYPE
    ),
) -> dict[str, list[dict[str, Any]]]:
    """
    Calculate independent SHA for:

        Future
        Call
        Put

    Each chart receives its own complete SHA pipeline.
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
            smooth_length=smooth_length,
            smooth_ma_type=smooth_ma_type,
            after_smooth_length=after_smooth_length,
            after_smooth_ma_type=after_smooth_ma_type,
        ),

        "call": add_sha(
            call,
            smooth_length=smooth_length,
            smooth_ma_type=smooth_ma_type,
            after_smooth_length=after_smooth_length,
            after_smooth_ma_type=after_smooth_ma_type,
        ),

        "put": add_sha(
            put,
            smooth_length=smooth_length,
            smooth_ma_type=smooth_ma_type,
            after_smooth_length=after_smooth_length,
            after_smooth_ma_type=after_smooth_ma_type,
        ),
    }


# ============================================================================
# LATEST SHA
# ============================================================================

def latest_sha(
    candles: Iterable[dict[str, Any]],
    smooth_length: int = DEFAULT_HA_SMOOTH_LENGTH,
    smooth_ma_type: str = DEFAULT_HA_SMOOTH_MA_TYPE,
    after_smooth_length: int = (
        DEFAULT_HA_AFTER_SMOOTH_LENGTH
    ),
    after_smooth_ma_type: str = (
        DEFAULT_HA_AFTER_SMOOTH_MA_TYPE
    ),
) -> dict[str, Any] | None:
    """Return the latest SHA candle."""

    result = add_sha(
        candles,
        smooth_length=smooth_length,
        smooth_ma_type=smooth_ma_type,
        after_smooth_length=after_smooth_length,
        after_smooth_ma_type=after_smooth_ma_type,
    )

    if not result:
        return None

    return result[-1]


# ============================================================================
# LIVE CANDLE UPDATE
# ============================================================================

def update_last_candle(
    candles: Iterable[dict[str, Any]],
    *,
    close: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: float | None = None,
) -> list[dict[str, Any]]:
    """
    Update the currently forming candle.

    This is useful for Xstream live ticks.

    The input list is copied; the original list is not modified.
    """

    result = normalize_candles(
        candles
    )

    if not result:
        return result

    last = result[-1]

    if close is not None:

        close_value = float(close)

        last["close"] = close_value

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
        last["volume"] = float(
            volume
        )

    return result


# ============================================================================
# RSI
# ============================================================================

def rsi(
    values: Iterable[float],
    period: int = DEFAULT_RSI_PERIOD,
) -> list[float | None]:
    """
    Calculate RSI using Wilder-style smoothing.

    RSI is included as a reusable Phase 1 utility.
    SHA remains the primary chart indicator.
    """

    period = _validate_period(
        period
    )

    source = [
        float(value)
        for value in values
    ]

    if len(source) <= period:
        return []

    result: list[float | None] = [
        None
        for _ in source
    ]

    gain = 0.0
    loss = 0.0

    for index in range(
        1,
        period + 1,
    ):

        change = (
            source[index]
            - source[index - 1]
        )

        if change >= 0:
            gain += change
        else:
            loss -= change

    average_gain = (
        gain / period
    )

    average_loss = (
        loss / period
    )

    if average_loss == 0:
        result[period] = 100.0
    else:
        relative_strength = (
            average_gain
            / average_loss
        )

        result[period] = (
            100.0
            - (
                100.0
                / (
                    1.0
                    + relative_strength
                )
            )
        )

    for index in range(
        period + 1,
        len(source),
    ):

        change = (
            source[index]
            - source[index - 1]
        )

        current_gain = (
            change
            if change > 0
            else 0.0
        )

        current_loss = (
            -change
            if change < 0
            else 0.0
        )

        average_gain = (
            (
                average_gain
                * (period - 1)
            )
            + current_gain
        ) / period

        average_loss = (
            (
                average_loss
                * (period - 1)
            )
            + current_loss
        ) / period

        if average_loss == 0:
            result[index] = 100.0
        else:

            relative_strength = (
                average_gain
                / average_loss
            )

            result[index] = (
                100.0
                - (
                    100.0
                    / (
                        1.0
                        + relative_strength
                    )
                )
            )

    return result


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================

__all__ = [
    "DEFAULT_HA_SMOOTH_LENGTH",
    "DEFAULT_HA_AFTER_SMOOTH_LENGTH",
    "DEFAULT_HA_SMOOTH_MA_TYPE",
    "DEFAULT_HA_AFTER_SMOOTH_MA_TYPE",
    "DEFAULT_RSI_PERIOD",
    "REQUIRED_OHLC",
    "normalize_candle",
    "normalize_candles",
    "sma",
    "ema",
    "moving_average",
    "heikin_ashi",
    "smooth_ohlc_before_ha",
    "smooth_ha_after",
    "smoothed_heikin_ashi",
    "add_sha_direction",
    "add_sha",
    "candle_direction",
    "calculate_dashboard_sha",
    "latest_sha",
    "update_last_candle",
    "rsi",
]
```
