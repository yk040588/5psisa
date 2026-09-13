from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
import os
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import httpx

try:
    from config.settings import settings
except Exception:
    settings = None

try:
    from .instruments import instrument_manager
except Exception:
    instrument_manager = None

try:
    from .broker import broker
except Exception:
    broker = None


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

SUPPORTED_SYMBOLS = (
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "NATURALGAS",
)

# Native intervals supported by 5paisa Historical API.
NATIVE_INTERVALS = {
    "1m": "1m",
    "5m": "5m",
    "10m": "10m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "60m": "60m",
    "1d": "1d",
}

# Locally generated intervals.
RESAMPLED_INTERVALS = {
    "3m": ("1m", 3),
    "4h": ("1h", 4),
}

SUPPORTED_INTERVALS = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "4h",
    "1d",
)

DEFAULT_INTERVAL = "5m"
DEFAULT_CANDLE_COUNT = 500
MAX_CANDLES = 2000

DEFAULT_LOOKBACK_DAYS = {
    "1m": 30,
    "3m": 30,
    "5m": 90,
    "15m": 180,
    "30m": 180,
    "1h": 365,
    "4h": 365,
    "1d": 1825,
}

CACHE_VERSION = 1


# ============================================================
# GENERAL HELPERS
# ============================================================

def _setting(name: str, default: Any = None) -> Any:
    """
    Safely read a setting regardless of whether settings.py exposes
    a pydantic object, normal class, or module-level value.
    """
    if settings is not None:
        try:
            value = getattr(settings, name, None)
            if value is not None:
                return value
        except Exception:
            pass

    return os.getenv(name, default)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default

        number = float(value)

        if not math.isfinite(number):
            return default

        return number
    except Exception:
        return default


def _clean_number(value: Any) -> Optional[float]:
    return _to_float(value, None)


def _normalize_symbol(symbol: Optional[str]) -> str:
    if not symbol:
        return str(_setting("DEFAULT_SYMBOL", "NIFTY")).upper()

    return str(symbol).strip().upper()


def _normalize_interval(interval: Optional[str]) -> str:
    value = str(interval or DEFAULT_INTERVAL).strip().lower()

    aliases = {
        "60min": "1h",
        "60m": "1h",
        "hour": "1h",
        "hourly": "1h",
        "daily": "1d",
        "day": "1d",
        "4hour": "4h",
        "4hourly": "4h",
    }

    value = aliases.get(value, value)

    if value not in SUPPORTED_INTERVALS:
        raise ValueError(
            f"Unsupported interval '{interval}'. "
            f"Supported: {', '.join(SUPPORTED_INTERVALS)}"
        )

    return value


def _safe_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    if not text:
        return None

    text = text.replace("Z", "+00:00")

    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _date_string(value: Any) -> str:
    dt = _safe_date(value)

    if dt is None:
        raise ValueError(f"Invalid date: {value}")

    return dt.strftime("%Y-%m-%d")


def _now() -> datetime:
    return datetime.now()


def _call_sync_or_async(function: Callable[..., Any], *args, **kwargs):
    """
    Call an unknown broker/instrument-manager method safely.

    If the method is async, run it only when no event loop is currently
    running. In FastAPI async routes, callers should preferably use the
    async helper below.
    """
    result = function(*args, **kwargs)

    if inspect.isawaitable(result):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                return result
        except RuntimeError:
            pass

        return asyncio.run(result)

    return result


async def _call_async(function: Callable[..., Any], *args, **kwargs):
    result = function(*args, **kwargs)

    if inspect.isawaitable(result):
        return await result

    return result


# ============================================================
# CANDLE NORMALIZATION
# ============================================================

def normalize_candle(candle: Any) -> Optional[Dict[str, Any]]:
    """
    Convert all expected 5paisa candle formats into:

    {
        "timestamp": "...",
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "volume": int
    }

    5paisa can return candle rows as arrays:
        [Timestamp, Open, High, Low, Close, Volume]

    or dictionaries with fields:
        Timestamp, Open, High, Low, Close, Volume
    """

    if isinstance(candle, (list, tuple)):
        if len(candle) < 5:
            return None

        timestamp = candle[0]
        open_price = _clean_number(candle[1])
        high_price = _clean_number(candle[2])
        low_price = _clean_number(candle[3])
        close_price = _clean_number(candle[4])
        volume = _to_int(candle[5], 0) if len(candle) > 5 else 0

    elif isinstance(candle, dict):
        timestamp = (
            candle.get("timestamp")
            or candle.get("Timestamp")
            or candle.get("time")
            or candle.get("Time")
            or candle.get("datetime")
            or candle.get("DateTime")
        )

        open_price = _clean_number(
            candle.get("open", candle.get("Open", candle.get("OpenRate")))
        )

        high_price = _clean_number(
            candle.get("high", candle.get("High"))
        )

        low_price = _clean_number(
            candle.get("low", candle.get("Low"))
        )

        close_price = _clean_number(
            candle.get(
                "close",
                candle.get(
                    "Close",
                    candle.get("LastRate", candle.get("LTP")),
                ),
            )
        )

        volume = _to_int(
            candle.get(
                "volume",
                candle.get(
                    "Volume",
                    candle.get("TotalQty", candle.get("LastQty", 0)),
                ),
            ),
            0,
        )

    else:
        return None

    if timestamp is None:
        return None

    dt = _safe_date(timestamp)

    if dt is None:
        # Some broker feeds use epoch milliseconds.
        try:
            numeric = float(timestamp)

            if numeric > 10_000_000_000:
                numeric /= 1000

            dt = datetime.fromtimestamp(numeric)
        except Exception:
            return None

    if (
        open_price is None
        or high_price is None
        or low_price is None
        or close_price is None
    ):
        return None

    return {
        "timestamp": dt.isoformat(),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }


def normalize_candles(data: Any) -> List[Dict[str, Any]]:
    """
    Normalize a complete historical response.

    Handles:
    - {"data": {"candles": [...]}}
    - {"candles": [...]}
    - {"body": {"data": {"candles": [...]}}}
    - direct [...]
    """

    if data is None:
        return []

    candles = data

    if isinstance(data, dict):
        if "data" in data:
            nested = data["data"]

            if isinstance(nested, dict):
                candles = nested.get("candles", nested.get("Candles", []))
            else:
                candles = nested

        elif "body" in data:
            body = data["body"]

            if isinstance(body, dict):
                nested = body.get("data", body)

                if isinstance(nested, dict):
                    candles = nested.get(
                        "candles",
                        nested.get("Candles", []),
                    )
                else:
                    candles = nested

        elif "candles" in data:
            candles = data["candles"]

        elif "Candles" in data:
            candles = data["Candles"]

    if not isinstance(candles, list):
        return []

    result: List[Dict[str, Any]] = []

    for item in candles:
        normalized = normalize_candle(item)

        if normalized:
            result.append(normalized)

    result.sort(key=lambda item: item["timestamp"])

    return deduplicate_candles(result)


def deduplicate_candles(
    candles: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}

    for candle in candles:
        timestamp = candle.get("timestamp")

        if timestamp:
            seen[str(timestamp)] = candle

    return sorted(
        seen.values(),
        key=lambda item: item["timestamp"],
    )


# ============================================================
# RESAMPLING
# ============================================================

def resample_candles(
    candles: Sequence[Dict[str, Any]],
    minutes: int,
) -> List[Dict[str, Any]]:
    """
    Local OHLCV resampling.

    Example:
        1m -> 3m
        60m -> 4h
    """

    if not candles:
        return []

    if minutes <= 1:
        return list(candles)

    normalized = normalize_candles(list(candles))

    if not normalized:
        return []

    buckets: Dict[datetime, Dict[str, Any]] = {}

    for candle in normalized:
        dt = _safe_date(candle["timestamp"])

        if dt is None:
            continue

        minute_of_day = dt.hour * 60 + dt.minute

        bucket_minute = (
            minute_of_day // minutes
        ) * minutes

        bucket = dt.replace(
            hour=bucket_minute // 60,
            minute=bucket_minute % 60,
            second=0,
            microsecond=0,
        )

        key = bucket

        if key not in buckets:
            buckets[key] = {
                "timestamp": bucket.isoformat(),
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle.get("volume", 0),
            }
        else:
            current = buckets[key]

            current["high"] = max(
                current["high"],
                candle["high"],
            )

            current["low"] = min(
                current["low"],
                candle["low"],
            )

            current["close"] = candle["close"]

            current["volume"] += _to_int(
                candle.get("volume", 0),
                0,
            )

    return sorted(
        buckets.values(),
        key=lambda item: item["timestamp"],
    )


# ============================================================
# CACHE
# ============================================================

class CandleCache:
    """
    Small JSON based local candle cache.

    Purpose:
    - reduce repeated API calls
    - allow historical charts to continue working offline
      when data has already been cached
    """

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            configured = _setting("DATA_DIR", None)

            if configured:
                self.base_dir = Path(configured)
            else:
                self.base_dir = (
                    Path(__file__).resolve().parent.parent / "data"
                )

        self.base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _file_path(
        self,
        symbol: str,
        instrument_type: str,
        scrip_code: Any,
        interval: str,
    ) -> Path:
        safe_symbol = str(symbol).upper().replace("/", "_")
        safe_type = str(instrument_type).upper()
        safe_code = str(scrip_code)
        safe_interval = str(interval).lower()

        directory = (
            self.base_dir
            / "market_cache"
            / safe_symbol
            / safe_type
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return directory / f"{safe_code}_{safe_interval}.json"

    def load(
        self,
        symbol: str,
        instrument_type: str,
        scrip_code: Any,
        interval: str,
    ) -> List[Dict[str, Any]]:
        path = self._file_path(
            symbol,
            instrument_type,
            scrip_code,
            interval,
        )

        if not path.exists():
            return []

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as file:
                payload = json.load(file)

            if isinstance(payload, dict):
                candles = payload.get("candles", [])
            else:
                candles = payload

            return normalize_candles(candles)

        except Exception as exc:
            logger.warning(
                "Unable to read candle cache %s: %s",
                path,
                exc,
            )
            return []

    def save(
        self,
        symbol: str,
        instrument_type: str,
        scrip_code: Any,
        interval: str,
        candles: Sequence[Dict[str, Any]],
    ) -> None:
        path = self._file_path(
            symbol,
            instrument_type,
            scrip_code,
            interval,
        )

        normalized = normalize_candles(list(candles))

        payload = {
            "version": CACHE_VERSION,
            "symbol": symbol,
            "instrument_type": instrument_type,
            "scrip_code": scrip_code,
            "interval": interval,
            "updated_at": datetime.now().isoformat(),
            "candles": normalized,
        }

        temp_path = path.with_suffix(".tmp")

        try:
            with temp_path.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

            temp_path.replace(path)

        except Exception as exc:
            logger.warning(
                "Unable to save candle cache %s: %s",
                path,
                exc,
            )

            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    def merge(
        self,
        symbol: str,
        instrument_type: str,
        scrip_code: Any,
        interval: str,
        candles: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        existing = self.load(
            symbol,
            instrument_type,
            scrip_code,
            interval,
        )

        merged = deduplicate_candles(
            list(existing) + list(candles)
        )

        max_candles = _to_int(
            _setting("MAX_CANDLES", MAX_CANDLES),
            MAX_CANDLES,
        )

        if len(merged) > max_candles:
            merged = merged[-max_candles:]

        self.save(
            symbol,
            instrument_type,
            scrip_code,
            interval,
            merged,
        )

        return merged


# ============================================================
# MARKET DATA MANAGER
# ============================================================

class MarketDataManager:
    """
    Phase 1 market-data layer.

    Responsibilities:
        Historical Xstream API
        Local candle cache
        Offline fallback
        Candle normalization
        3m / 4h resampling
        Future / Call / Put history
        Live tick normalization
        Latest LTP state

    Actual Xstream MarketFeedV3 WebSocket connection is intentionally
    kept in websocket_manager.py.
    """

    def __init__(self):
        self.cache = CandleCache()

        self.latest_quotes: Dict[str, Dict[str, Any]] = {}

        self._tick_callbacks: List[
            Callable[[Dict[str, Any]], Any]
        ] = []

        self._historical_lock = asyncio.Lock()

    # --------------------------------------------------------
    # CALLBACKS
    # --------------------------------------------------------

    def add_tick_callback(
        self,
        callback: Callable[[Dict[str, Any]], Any],
    ) -> None:
        if callback not in self._tick_callbacks:
            self._tick_callbacks.append(callback)

    def remove_tick_callback(
        self,
        callback: Callable[[Dict[str, Any]], Any],
    ) -> None:
        if callback in self._tick_callbacks:
            self._tick_callbacks.remove(callback)

    async def _notify_tick(
        self,
        tick: Dict[str, Any],
    ) -> None:
        for callback in list(self._tick_callbacks):
            try:
                result = callback(tick)

                if inspect.isawaitable(result):
                    await result

            except Exception:
                logger.exception(
                    "Market-data tick callback failed"
                )

    # --------------------------------------------------------
    # BROKER ACCESS TOKEN
    # --------------------------------------------------------

    def _get_access_token(self) -> Optional[str]:
        if broker is None:
            return None

        possible_names = (
            "access_token",
            "_access_token",
            "token",
            "_token",
        )

        for name in possible_names:
            try:
                value = getattr(broker, name, None)

                if value:
                    return str(value)
            except Exception:
                pass

        # Try common getter methods.
        for method_name in (
            "get_access_token",
            "get_token",
        ):
            try:
                method = getattr(
                    broker,
                    method_name,
                    None,
                )

                if method:
                    value = method()

                    if inspect.isawaitable(value):
                        continue

                    if value:
                        return str(value)

            except Exception:
                pass

        return None

    # --------------------------------------------------------
    # HISTORICAL URL
    # --------------------------------------------------------

    def _historical_base_url(self) -> str:
        return str(
            _setting(
                "FIVEPAISA_HISTORICAL_URL",
                "https://openapi.5paisa.com/V2/historical",
            )
        ).rstrip("/")

    # --------------------------------------------------------
    # INSTRUMENT RESOLUTION
    # --------------------------------------------------------

    def resolve_instrument(
        self,
        symbol: str,
        instrument_type: str = "FUTURE",
        expiry: Optional[str] = None,
        strike: Optional[Union[int, float, str]] = None,
        option_type: Optional[str] = None,
        scrip_code: Optional[Union[int, str]] = None,
        instrument: Any = None,
    ) -> Any:
        """
        Resolve an instrument from final instruments.py.

        If a complete instrument object is supplied, it is used directly.
        """

        if instrument is not None:
            return instrument

        if instrument_manager is None:
            raise RuntimeError(
                "instrument_manager is not available."
            )

        symbol = _normalize_symbol(symbol)

        if scrip_code is not None:
            finder = getattr(
                instrument_manager,
                "find_by_token",
                None,
            )

            if finder:
                result = _call_sync_or_async(
                    finder,
                    scrip_code,
                )

                if result is not None:
                    return result

        instrument_type = str(
            instrument_type or "FUTURE"
        ).upper()

        # Future
        if instrument_type == "FUTURE":
            if expiry:
                finder = getattr(
                    instrument_manager,
                    "find_future",
                    None,
                )

                if finder:
                    result = _call_sync_or_async(
                        finder,
                        symbol,
                        expiry,
                    )

                    if result:
                        return result

            finder = getattr(
                instrument_manager,
                "get_nearest_future",
                None,
            )

            if finder:
                result = _call_sync_or_async(
                    finder,
                    symbol,
                )

                if result:
                    return result

            futures_method = getattr(
                instrument_manager,
                "get_futures",
                None,
            )

            if futures_method:
                futures = _call_sync_or_async(
                    futures_method,
                    symbol,
                    expiry,
                )

                if futures:
                    return futures[0]

        # Option
        if instrument_type in (
            "CALL",
            "PUT",
            "OPTION",
        ):
            if option_type is None:
                option_type = (
                    "CALL"
                    if instrument_type == "CALL"
                    else "PUT"
                )

            finder = getattr(
                instrument_manager,
                "find_option",
                None,
            )

            if finder:
                result = _call_sync_or_async(
                    finder,
                    symbol=symbol,
                    expiry=expiry,
                    strike=strike,
                    option_type=option_type,
                )

                if result:
                    return result

            options_method = getattr(
                instrument_manager,
                "get_options",
                None,
            )

            if options_method:
                options = _call_sync_or_async(
                    options_method,
                    symbol,
                    expiry,
                    option_type,
                )

                if options:
                    if strike is not None:
                        target = _to_float(strike)

                        for option in options:
                            option_strike = _to_float(
                                getattr(
                                    option,
                                    "strike",
                                    None,
                                )
                            )

                            if (
                                option_strike is not None
                                and target is not None
                                and option_strike == target
                            ):
                                return option

                    return options[0]

        raise LookupError(
            f"Instrument not found: "
            f"{symbol} {instrument_type} "
            f"expiry={expiry} strike={strike} "
            f"option_type={option_type} "
            f"scrip_code={scrip_code}"
        )

    # --------------------------------------------------------
    # INSTRUMENT FIELD EXTRACTION
    # --------------------------------------------------------

    @staticmethod
    def instrument_value(
        instrument: Any,
        *names: str,
        default: Any = None,
    ) -> Any:
        if instrument is None:
            return default

        if isinstance(instrument, dict):
            for name in names:
                if name in instrument:
                    value = instrument[name]

                    if value is not None:
                        return value

            return default

        for name in names:
            try:
                value = getattr(
                    instrument,
                    name,
                    None,
                )

                if value is not None:
                    return value

            except Exception:
                pass

        return default

    def instrument_exchange(
        self,
        instrument: Any,
    ) -> str:
        return str(
            self.instrument_value(
                instrument,
                "exchange",
                "Exchange",
                "Exch",
                default="",
            )
        ).upper()

    def instrument_exchange_type(
        self,
        instrument: Any,
    ) -> str:
        return str(
            self.instrument_value(
                instrument,
                "exchange_type",
                "ExchangeType",
                "ExchType",
                default="",
            )
        ).upper()

    def instrument_scrip_code(
        self,
        instrument: Any,
    ) -> Optional[int]:
        value = self.instrument_value(
            instrument,
            "scrip_code",
            "ScripCode",
            "broker_token",
            "BrokerToken",
            "token",
            "Token",
            default=None,
        )

        if value is None:
            return None

        return _to_int(value, 0)

    # --------------------------------------------------------
    # HISTORICAL REQUEST
    # --------------------------------------------------------

    async def _request_historical(
        self,
        instrument: Any,
        interval: str,
        from_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        access_token = self._get_access_token()

        if not access_token:
            raise RuntimeError(
                "5paisa access token is not available."
            )

        exchange = self.instrument_exchange(
            instrument
        )

        exchange_type = self.instrument_exchange_type(
            instrument
        )

        scrip_code = self.instrument_scrip_code(
            instrument
        )

        if not exchange:
            raise ValueError(
                "Instrument exchange is missing."
            )

        if not exchange_type:
            raise ValueError(
                "Instrument exchange type is missing."
            )

        if not scrip_code:
            raise ValueError(
                "Instrument ScripCode is missing."
            )

        native_interval = NATIVE_INTERVALS.get(
            interval,
            interval,
        )

        url = (
            f"{self._historical_base_url()}/"
            f"{exchange}/"
            f"{exchange_type}/"
            f"{scrip_code}/"
            f"{native_interval}"
        )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        params = {
            "from": from_date,
            "end": end_date,
        }

        timeout = float(
            _setting(
                "HTTP_TIMEOUT_SECONDS",
                30,
            )
        )

        async with httpx.AsyncClient(
            timeout=timeout,
        ) as client:

            response = await client.get(
                url,
                headers=headers,
                params=params,
            )

            response.raise_for_status()

            payload = response.json()

        candles = normalize_candles(payload)

        if not candles:
            logger.info(
                "No historical candles returned for "
                "%s/%s/%s",
                exchange,
                exchange_type,
                scrip_code,
            )

        return candles

    # --------------------------------------------------------
    # HISTORICAL DATA
    # --------------------------------------------------------

    async def get_historical(
        self,
        symbol: str,
        interval: str = DEFAULT_INTERVAL,
        from_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None,
        instrument_type: str = "FUTURE",
        expiry: Optional[str] = None,
        strike: Optional[Union[int, float, str]] = None,
        option_type: Optional[str] = None,
        scrip_code: Optional[Union[int, str]] = None,
        instrument: Any = None,
        refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Main historical-data method.

        Offline behavior:
            If API is unavailable and cache exists,
            cached candles are returned.

        3m:
            fetch 1m -> local 3m resampling

        4h:
            fetch 60m -> local 4h resampling
        """

        symbol = _normalize_symbol(symbol)
        interval = _normalize_interval(interval)

        requested_count = _to_int(
            count,
            _to_int(
                _setting(
                    "DEFAULT_CANDLE_COUNT",
                    DEFAULT_CANDLE_COUNT,
                ),
                DEFAULT_CANDLE_COUNT,
            ),
        )

        requested_count = max(
            1,
            min(
                requested_count,
                _to_int(
                    _setting(
                        "MAX_CANDLES",
                        MAX_CANDLES,
                    ),
                    MAX_CANDLES,
                ),
            ),
        )

        instrument = self.resolve_instrument(
            symbol=symbol,
            instrument_type=instrument_type,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            scrip_code=scrip_code,
            instrument=instrument,
        )

        actual_scrip_code = self.instrument_scrip_code(
            instrument
        )

        if not actual_scrip_code:
            raise ValueError(
                f"Instrument has no ScripCode: {instrument}"
            )

        # ----------------------------------------------------
        # Local resampled interval
        # ----------------------------------------------------

        if interval in RESAMPLED_INTERVALS:
            base_interval, multiplier = RESAMPLED_INTERVALS[
                interval
            ]

            base_candles = await self.get_historical(
                symbol=symbol,
                interval=base_interval,
                from_date=from_date,
                end_date=end_date,
                count=max(
                    requested_count * multiplier,
                    requested_count,
                ),
                instrument_type=instrument_type,
                expiry=expiry,
                strike=strike,
                option_type=option_type,
                scrip_code=actual_scrip_code,
                instrument=instrument,
                refresh=refresh,
            )

            return resample_candles(
                base_candles,
                multiplier
                * (
                    60
                    if base_interval == "1h"
                    else 1
                ),
            )[-requested_count:]

        # ----------------------------------------------------
        # Native interval
        # ----------------------------------------------------

        native_interval = NATIVE_INTERVALS[interval]

        cache_symbol = symbol

        cached = self.cache.load(
            cache_symbol,
            instrument_type,
            actual_scrip_code,
            native_interval,
        )

        # ----------------------------------------------------
        # Determine dates
        # ----------------------------------------------------

        if end_date:
            end_dt = _safe_date(end_date)

            if end_dt is None:
                end_dt = _now()
        else:
            end_dt = _now()

        if from_date:
            start_dt = _safe_date(from_date)

            if start_dt is None:
                raise ValueError(
                    f"Invalid from_date: {from_date}"
                )
        else:
            lookback = DEFAULT_LOOKBACK_DAYS.get(
                interval,
                90,
            )

            # For intraday intervals, request enough history.
            start_dt = end_dt - timedelta(
                days=lookback
            )

        start_string = start_dt.strftime(
            "%Y-%m-%d"
        )

        end_string = end_dt.strftime(
            "%Y-%m-%d"
        )

        # ----------------------------------------------------
        # Cache-only mode
        # ----------------------------------------------------

        if not refresh and cached:
            # If caller explicitly supplied a date range,
            # filter cached candles accordingly.
            filtered = self._filter_date_range(
                cached,
                start_dt,
                end_dt,
            )

            if len(filtered) >= requested_count:
                return filtered[-requested_count:]

        # ----------------------------------------------------
        # Fetch fresh data
        # ----------------------------------------------------

        fresh: List[Dict[str, Any]] = []

        try:
            async with self._historical_lock:
                fresh = await self._request_historical(
                    instrument=instrument,
                    interval=native_interval,
                    from_date=start_string,
                    end_date=end_string,
                )

        except Exception as exc:
            logger.warning(
                "Historical API unavailable for %s "
                "%s %s: %s",
                symbol,
                instrument_type,
                native_interval,
                exc,
            )

            # Offline fallback.
            if cached:
                filtered = self._filter_date_range(
                    cached,
                    start_dt,
                    end_dt,
                )

                return filtered[-requested_count:]

            raise

        # ----------------------------------------------------
        # Merge into cache
        # ----------------------------------------------------

        merged = self.cache.merge(
            cache_symbol,
            instrument_type,
            actual_scrip_code,
            native_interval,
            fresh,
        )

        filtered = self._filter_date_range(
            merged,
            start_dt,
            end_dt,
        )

        return filtered[-requested_count:]

    # --------------------------------------------------------
    # DATE FILTER
    # --------------------------------------------------------

    @staticmethod
    def _filter_date_range(
        candles: Sequence[Dict[str, Any]],
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict[str, Any]]:
        result = []

        for candle in candles:
            dt = _safe_date(
                candle.get("timestamp")
            )

            if dt is None:
                continue

            if start_dt <= dt <= end_dt + timedelta(days=1):
                result.append(candle)

        return result

    # --------------------------------------------------------
    # FUTURE / CALL / PUT SHORTCUTS
    # --------------------------------------------------------

    async def get_future_history(
        self,
        symbol: str,
        interval: str = DEFAULT_INTERVAL,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        return await self.get_historical(
            symbol=symbol,
            interval=interval,
            instrument_type="FUTURE",
            **kwargs,
        )

    async def get_call_history(
        self,
        symbol: str,
        expiry: Optional[str],
        strike: Union[int, float, str],
        interval: str = DEFAULT_INTERVAL,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        return await self.get_historical(
            symbol=symbol,
            interval=interval,
            instrument_type="CALL",
            expiry=expiry,
            strike=strike,
            option_type="CALL",
            **kwargs,
        )

    async def get_put_history(
        self,
        symbol: str,
        expiry: Optional[str],
        strike: Union[int, float, str],
        interval: str = DEFAULT_INTERVAL,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        return await self.get_historical(
            symbol=symbol,
            interval=interval,
            instrument_type="PUT",
            expiry=expiry,
            strike=strike,
            option_type="PUT",
            **kwargs,
        )

    # --------------------------------------------------------
    # QUOTE / LIVE TICK NORMALIZATION
    # --------------------------------------------------------

    @staticmethod
    def normalize_tick(
        tick: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Normalize 5paisa MarketFeedV3 tick.

        Important fields documented by 5paisa:
            Exch
            ExchType
            Token
            LastRate
            LastQty
            TotalQty
            High
            Low
            OpenRate
            PClose
            AvgRate
            BidQty
            BidRate
            OffQty
            OffRate
            TickDt
        """

        if isinstance(tick, str):
            try:
                tick = json.loads(tick)
            except Exception:
                return None

        if not isinstance(tick, dict):
            return None

        # Sometimes WebSocket returns:
        # {"MarketFeedV3": [...]}
        if len(tick) == 1:
            for value in tick.values():
                if isinstance(value, list) and value:
                    if isinstance(value[0], dict):
                        tick = value[0]
                        break

                if isinstance(value, dict):
                    possible = value.get(
                        "MarketFeedData"
                    )

                    if isinstance(possible, list) and possible:
                        if isinstance(possible[0], dict):
                            tick = possible[0]
                            break

        token = (
            tick.get("Token")
            or tick.get("ScripCode")
            or tick.get("token")
            or tick.get("scrip_code")
        )

        last_rate = (
            tick.get("LastRate")
            if tick.get("LastRate") is not None
            else tick.get("LTP")
        )

        if last_rate is None:
            last_rate = tick.get("last_rate")

        last_rate = _clean_number(last_rate)

        if token is None or last_rate is None:
            return None

        normalized = {
            "token": _to_int(token, 0),
            "scrip_code": _to_int(token, 0),
            "exchange": str(
                tick.get(
                    "Exch",
                    tick.get("exchange", ""),
                )
            ).upper(),
            "exchange_type": str(
                tick.get(
                    "ExchType",
                    tick.get("exchange_type", ""),
                )
            ).upper(),
            "ltp": last_rate,
            "last_rate": last_rate,
            "last_qty": _to_int(
                tick.get(
                    "LastQty",
                    tick.get("last_qty", 0),
                ),
                0,
            ),
            "total_qty": _to_int(
                tick.get(
                    "TotalQty",
                    tick.get("total_qty", 0),
                ),
                0,
            ),
            "open": _clean_number(
                tick.get(
                    "OpenRate",
                    tick.get("Open"),
                )
            ),
            "high": _clean_number(
                tick.get("High")
            ),
            "low": _clean_number(
                tick.get("Low")
            ),
            "previous_close": _clean_number(
                tick.get(
                    "PClose",
                    tick.get("PreviousClose"),
                )
            ),
            "avg_rate": _clean_number(
                tick.get("AvgRate")
            ),
            "bid_qty": _to_int(
                tick.get("BidQty", 0),
                0,
            ),
            "bid_rate": _clean_number(
                tick.get("BidRate")
            ),
            "ask_qty": _to_int(
                tick.get(
                    "OffQty",
                    tick.get("AskQty", 0),
                ),
                0,
            ),
            "ask_rate": _clean_number(
                tick.get(
                    "OffRate",
                    tick.get("AskRate"),
                )
            ),
            "tick_time": (
                tick.get("TickDt")
                or tick.get("Time")
                or tick.get("timestamp")
            ),
            "raw": deepcopy(tick),
        }

        return normalized

    async def process_tick(
        self,
        tick: Any,
    ) -> Optional[Dict[str, Any]]:
        normalized = self.normalize_tick(tick)

        if normalized is None:
            return None

        token = str(
            normalized["token"]
        )

        self.latest_quotes[token] = normalized

        await self._notify_tick(
            normalized
        )

        return normalized

    # --------------------------------------------------------
    # LATEST QUOTE
    # --------------------------------------------------------

    def get_latest_quote(
        self,
        token: Union[int, str],
    ) -> Optional[Dict[str, Any]]:
        return self.latest_quotes.get(
            str(token)
        )

    def get_ltp(
        self,
        token: Union[int, str],
    ) -> Optional[float]:
        quote = self.get_latest_quote(token)

        if not quote:
            return None

        return _clean_number(
            quote.get("ltp")
        )

    def set_latest_quote(
        self,
        token: Union[int, str],
        quote: Dict[str, Any],
    ) -> None:
        normalized = self.normalize_tick(
            quote
        )

        if normalized:
            self.latest_quotes[str(token)] = normalized

    # --------------------------------------------------------
    # CACHE / STATUS
    # --------------------------------------------------------

    def clear_quote_cache(self) -> None:
        self.latest_quotes.clear()

    def cache_status(self) -> Dict[str, Any]:
        return {
            "cache_directory": str(
                self.cache.base_dir
            ),
            "quotes_in_memory": len(
                self.latest_quotes
            ),
            "supported_intervals": list(
                SUPPORTED_INTERVALS
            ),
            "native_intervals": list(
                NATIVE_INTERVALS.keys()
            ),
            "resampled_intervals": list(
                RESAMPLED_INTERVALS.keys()
            ),
        }

    def status(self) -> Dict[str, Any]:
        return {
            "service": "market_data",
            "supported_symbols": list(
                SUPPORTED_SYMBOLS
            ),
            "supported_intervals": list(
                SUPPORTED_INTERVALS
            ),
            "native_intervals": [
                "1m",
                "5m",
                "10m",
                "15m",
                "30m",
                "1h",
                "1d",
            ],
            "resampled_intervals": {
                "3m": "1m -> 3m",
                "4h": "1h -> 4h",
            },
            "cache": self.cache_status(),
        }


# ============================================================
# SHARED INSTANCE
# ============================================================

market_data = MarketDataManager()

# Compatibility aliases for existing imports.
market_data_manager = market_data
manager = market_data


# ============================================================
# MODULE-LEVEL HELPERS
# ============================================================

async def get_historical(
    symbol: str,
    interval: str = DEFAULT_INTERVAL,
    **kwargs,
) -> List[Dict[str, Any]]:
    return await market_data.get_historical(
        symbol=symbol,
        interval=interval,
        **kwargs,
    )


async def get_future_history(
    symbol: str,
    interval: str = DEFAULT_INTERVAL,
    **kwargs,
) -> List[Dict[str, Any]]:
    return await market_data.get_future_history(
        symbol=symbol,
        interval=interval,
        **kwargs,
    )


async def get_call_history(
    symbol: str,
    expiry: Optional[str],
    strike: Union[int, float, str],
    interval: str = DEFAULT_INTERVAL,
    **kwargs,
) -> List[Dict[str, Any]]:
    return await market_data.get_call_history(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        interval=interval,
        **kwargs,
    )


async def get_put_history(
    symbol: str,
    expiry: Optional[str],
    strike: Union[int, float, str],
    interval: str = DEFAULT_INTERVAL,
    **kwargs,
) -> List[Dict[str, Any]]:
    return await market_data.get_put_history(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        interval=interval,
        **kwargs,
    )


def normalize_tick(
    tick: Any,
) -> Optional[Dict[str, Any]]:
    return market_data.normalize_tick(tick)
