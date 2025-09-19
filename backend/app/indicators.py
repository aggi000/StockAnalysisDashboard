import pandas as pd
import numpy as np
from typing import Dict, List, Any

def _sma(series: pd.Series, window: int = 20) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()

def _ema(series: pd.Series, span: int = 20) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=window).mean()
    rs = gain / loss.replace({0: np.nan})
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, span=fast)
    ema_slow = _ema(series, span=slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, span=signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def _bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0):
    ma = _sma(series, window=window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    return ma, upper, lower

def compute_indicators(df: pd.DataFrame, wants: List[str]) -> Dict[str, Any]:
    """
    df: expects columns ["Close", "Volume"]
    wants: subset of ["sma","ema","rsi","macd","boll"]
    """
    out: Dict[str, Any] = {}
    close = df["Close"].astype(float)

    if "sma" in wants:
        out["sma20"] = _sma(close, 20).dropna().to_dict()
        out["sma50"] = _sma(close, 50).dropna().to_dict()

    if "ema" in wants:
        out["ema12"] = _ema(close, 12).dropna().to_dict()
        out["ema26"] = _ema(close, 26).dropna().to_dict()

    if "rsi" in wants:
        out["rsi14"] = _rsi(close, 14).dropna().to_dict()

    if "macd" in wants:
        macd_line, signal_line, hist = _macd(close, 12, 26, 9)
        out["macd"] = {
            "line": macd_line.dropna().to_dict(),
            "signal": signal_line.dropna().to_dict(),
            "hist": hist.dropna().to_dict(),
        }

    if "boll" in wants:
        ma, upper, lower = _bollinger(close, 20, 2.0)
        out["bollinger"] = {
            "ma": ma.dropna().to_dict(),
            "upper": upper.dropna().to_dict(),
            "lower": lower.dropna().to_dict(),
        }

    return out
