import os
import time
import logging
from json import JSONDecodeError

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from functools import lru_cache
from typing import Tuple

import pandas as pd
import numpy as np
import yfinance as yf
from requests import exceptions as requests_exceptions

try:
    import requests_cache
except ImportError:  # pragma: no cover
    requests_cache = None

from .indicators import compute_indicators

logger = logging.getLogger("stock-analysis")

app = FastAPI(title="Stock Analysis API", version="0.1.0")

CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))
_history_cache: Dict[Tuple[str, str, str], Tuple[float, pd.DataFrame]] = {}
_quote_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

if requests_cache and os.environ.get("ENABLE_REQUESTS_CACHE", "1") != "0":
    try:
        requests_cache.install_cache(
            "yfinance_cache",
            backend="memory",
            expire_after=CACHE_TTL_SECONDS,
        )
        logger.info("requests-cache enabled for yfinance (TTL=%s)", CACHE_TTL_SECONDS)
    except Exception as cache_err:  # pragma: no cover
        logger.warning("Failed to enable requests-cache: %s", cache_err)


class UpstreamRateLimitError(Exception):
    """Raised when the upstream market data provider rate limits requests."""


def _is_rate_limited_error(err: Exception) -> bool:
    msg = str(err).lower()
    if "429" in msg or "too many requests" in msg:
        return True
    if isinstance(err, JSONDecodeError):
        return True
    response = getattr(err, "response", None)
    status = getattr(response, "status_code", None)
    if status == 429:
        return True
    if isinstance(err, requests_exceptions.HTTPError) and err.response is not None:
        return err.response.status_code == 429
    return False

allowed_origins = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
}

extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
if extra_origins:
    allowed_origins.update({origin.strip() for origin in extra_origins.split(",") if origin.strip()})

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Candle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float

class HistoryResponse(BaseModel):
    ticker: str
    period: str
    interval: str
    candles: List[Candle]
    indicators: Optional[Dict[str, Any]] = None

class QuoteResponse(BaseModel):
    ticker: str
    price: Optional[float] = None
    currency: Optional[str] = None
    previousClose: Optional[float] = None
    open: Optional[float] = None
    dayHigh: Optional[float] = None
    dayLow: Optional[float] = None
    marketCap: Optional[float] = None
    trailingPE: Optional[float] = None
    forwardPE: Optional[float] = None
    epsTrailing12M: Optional[float] = None
    dividendYield: Optional[float] = None
    beta: Optional[float] = None
    fiftyTwoWeekHigh: Optional[float] = None
    fiftyTwoWeekLow: Optional[float] = None

@app.get("/health")
def health():
    return {"status": "ok"}

@lru_cache(maxsize=128)
def _get_ticker_obj(ticker: str):
    return yf.Ticker(ticker)


def _safe_lookup(source, key):
    if source is None:
        return None
    try:
        getter = getattr(source, 'get', None)
        if callable(getter):
            try:
                return getter(key)
            except KeyError:
                return None
        if isinstance(source, dict):
            return source.get(key)
    except Exception:
        pass
    try:
        return source[key]  # type: ignore[index]
    except (KeyError, TypeError, AttributeError):
        pass
    try:
        return getattr(source, key)
    except AttributeError:
        return None


def _cache_get(store: Dict, key):
    if CACHE_TTL_SECONDS <= 0:
        return None
    entry = store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at > time.time():
        return value
    store.pop(key, None)
    return None


def _cache_set(store: Dict, key, value):
    if CACHE_TTL_SECONDS <= 0:
        return
    store[key] = (time.time() + CACHE_TTL_SECONDS, value)


def _safe_fast_info_value(info, key):
    return _safe_lookup(info, key)

def _safe_float(d, key):
    v = _safe_lookup(d, key)
    try:
        return float(v) if v is not None else None
    except Exception:
        return None

def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sanitize_volume(value):
    volume = _to_float(value)
    if volume is None:
        return 0.0
    try:
        if np.isnan(volume):
            return 0.0
    except TypeError:
        return 0.0
    return volume


def _download_history(ticker: str, period: str, interval: str):
    last_error: Optional[Exception] = None
    rate_limited = False

    for attempt in range(3):
        try:
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if df is not None and not df.empty:
                return df
        except Exception as err:
            last_error = err
            if _is_rate_limited_error(err):
                rate_limited = True
            logger.warning("yf.download failed for %s (attempt %s/%s): %s", ticker, attempt + 1, 3, err)
        time.sleep(1.5 * (attempt + 1))

    for attempt in range(3):
        try:
            df = _get_ticker_obj(ticker).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )
            if df is not None and not df.empty:
                return df
        except Exception as err:
            last_error = err
            if _is_rate_limited_error(err):
                rate_limited = True
            logger.warning("ticker.history failed for %s (attempt %s/%s): %s", ticker, attempt + 1, 3, err)
        time.sleep(1.5 * (attempt + 1))

    if rate_limited:
        raise UpstreamRateLimitError(str(last_error) if last_error else "Rate limited by upstream provider")

    if last_error:
        raise last_error
    return pd.DataFrame()


@app.get("/api/quote/{ticker}", response_model=QuoteResponse)
def get_quote(ticker: str):
    symbol = ticker.upper()
    cached = _cache_get(_quote_cache, symbol)
    if cached is not None:
        return QuoteResponse(**cached)

    t = _get_ticker_obj(symbol)
    fast = {}
    info = {}
    try:
        fast = t.fast_info or {}
    except Exception:
        fast = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}

    # 1) Price: fast_info → info → history close
    price = _safe_float(fast, "last_price") or _safe_float(info, "regularMarketPrice")
    currency = _safe_fast_info_value(fast, "currency") or _safe_fast_info_value(info, "currency")

    # 2) Previous close / open / day high / day low
    previous_close = _safe_float(fast, "previous_close") or _safe_float(info, "regularMarketPreviousClose")
    open_price     = _safe_float(fast, "open")           or _safe_float(info, "regularMarketOpen")
    day_high       = _safe_float(fast, "day_high")       or _safe_float(info, "regularMarketDayHigh")
    day_low        = _safe_float(fast, "day_low")        or _safe_float(info, "regularMarketDayLow")

    # 3) If any of those are still missing, fill from today's OHLC (or last session)
    if any(v is None for v in [price, previous_close, open_price, day_high, day_low]):
        try:
            # most recent day; interval 1m gives last trade if available
            hist = t.history(period="5d", interval="1d", auto_adjust=False)
            if not hist.empty:
                last = hist.iloc[-1]
                # Only set missing values; don't override existing
                price = price or float(last.get("Close"))
                previous_close = previous_close or float(hist["Close"].iloc[-2]) if len(hist) >= 2 else previous_close
                open_price = open_price or float(last.get("Open"))
                day_high = day_high or float(last.get("High"))
                day_low = day_low or float(last.get("Low"))
        except Exception:
            pass

    response = QuoteResponse(
        ticker=symbol,
        price=price,
        currency=currency,
        previousClose=previous_close,
        open=open_price,
        dayHigh=day_high,
        dayLow=day_low,
        marketCap=_safe_float(info, "marketCap"),
        trailingPE=_safe_float(info, "trailingPE"),
        forwardPE=_safe_float(info, "forwardPE"),
        epsTrailing12M=_safe_float(info, "trailingEps"),
        dividendYield=_safe_float(info, "dividendYield"),
        beta=_safe_float(info, "beta"),
        fiftyTwoWeekHigh=_safe_float(info, "fiftyTwoWeekHigh"),
        fiftyTwoWeekLow=_safe_float(info, "fiftyTwoWeekLow"),
    )
    _cache_set(_quote_cache, symbol, response.dict())
    return response

@app.get("/api/history/{ticker}", response_model=HistoryResponse)
def get_history(
    ticker: str,
    period: Literal["1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max"] = "1y",
    interval: Literal["1m","2m","5m","15m","30m","60m","90m","1h","1d","5d","1wk","1mo","3mo"] = "1d",
    indicators: Optional[str] = Query(None, description="Comma-separated list: sma,ema,rsi,macd,boll")
):
    symbol = ticker.upper()
    cache_key = (symbol, period, interval)
    cached_df = _cache_get(_history_cache, cache_key)
    if cached_df is not None:
        df = cached_df.copy()
    else:
        try:
            df = _download_history(symbol, period, interval)
        except UpstreamRateLimitError as e:
            raise HTTPException(status_code=429, detail="Rate limited by data provider. Please try again shortly.") from e
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to download history: {e}")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No historical data found")
        _cache_set(_history_cache, cache_key, df.copy())

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns=str.lower)  # open, high, low, close, volume
    df.index = pd.to_datetime(df.index)

    candles = [
        Candle(
            date=idx.isoformat(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=_sanitize_volume(row.get("volume")),
        )
        for idx, row in df.iterrows()
    ]

    ind_out = None
    if indicators:
        wants = [x.strip().lower() for x in indicators.split(",") if x.strip()]
        ind_out = compute_indicators(df[["close","volume"]].rename(columns={"close": "Close", "volume": "Volume"}), wants)

    return HistoryResponse(ticker=symbol, period=period, interval=interval, candles=candles, indicators=ind_out)
