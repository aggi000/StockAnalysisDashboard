import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from functools import lru_cache
import pandas as pd
import numpy as np
import yfinance as yf

from .indicators import compute_indicators

app = FastAPI(title="Stock Analysis API", version="0.1.0")

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


def _safe_fast_info_value(info, key):
    try:
        return info.get(key)
    except KeyError:
        return None
    except Exception:
        return None

def _safe_float(d, key):
    v = d.get(key)
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
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as primary_error:
        df = None
    else:
        primary_error = None

    if df is None or df.empty:
        try:
            df = _get_ticker_obj(ticker).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                actions=False,
            )
        except Exception as fallback_error:
            raise fallback_error if primary_error is None else primary_error

    return df


@app.get("/api/quote/{ticker}", response_model=QuoteResponse)
def get_quote(ticker: str):
    t = _get_ticker_obj(ticker.upper())
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
    currency = fast.get("currency") or info.get("currency")

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

    return QuoteResponse(
        ticker=ticker.upper(),
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

@app.get("/api/history/{ticker}", response_model=HistoryResponse)
def get_history(
    ticker: str,
    period: Literal["1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max"] = "1y",
    interval: Literal["1m","2m","5m","15m","30m","60m","90m","1h","1d","5d","1wk","1mo","3mo"] = "1d",
    indicators: Optional[str] = Query(None, description="Comma-separated list: sma,ema,rsi,macd,boll")
):
    try:
        df = _download_history(ticker.upper(), period, interval)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to download history: {e}")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No historical data found")

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

    return HistoryResponse(ticker=ticker.upper(), period=period, interval=interval, candles=candles, indicators=ind_out)
