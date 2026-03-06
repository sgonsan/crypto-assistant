import pandas as pd
import numpy as np


def _safe_float(val) -> float | None:
    if pd.isna(val):
        return None
    return float(val)


def compute_indicators_series(closes: list[float]) -> list[dict]:
    """
    Compute technical indicators for ALL data points at once (vectorized).

    Parameters
    ----------
    closes : list[float]
        Close prices in chronological order (oldest first).

    Returns
    -------
    list[dict]
        One dict per input price with keys: rsi, macd, macd_signal,
        bb_upper, bb_lower, ema_20. Values are None where data is
        insufficient (first 25 rows).
    """
    empty = {"rsi": None, "macd": None, "macd_signal": None,
             "bb_upper": None, "bb_lower": None, "ema_20": None}

    if not closes:
        return []

    s = pd.Series(closes, dtype=float)

    delta = s.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi_series = 100 - (100 / (1 + gain / loss))

    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    sma20 = s.rolling(20).mean()
    std20 = s.rolling(20).std()
    bb_upper_series = sma20 + 2 * std20
    bb_lower_series = sma20 - 2 * std20

    ema20_series = s.ewm(span=20, adjust=False).mean()

    results = []
    for i in range(len(closes)):
        if i < 25:
            results.append(dict(empty))
        else:
            results.append({
                "rsi": _safe_float(rsi_series.iloc[i]),
                "macd": _safe_float(macd_line.iloc[i]),
                "macd_signal": _safe_float(signal_line.iloc[i]),
                "bb_upper": _safe_float(bb_upper_series.iloc[i]),
                "bb_lower": _safe_float(bb_lower_series.iloc[i]),
                "ema_20": _safe_float(ema20_series.iloc[i]),
            })
    return results


def compute_indicators(prices: list[float]) -> dict:
    """
    Compute technical indicators from a list of close prices.

    Parameters
    ----------
    prices : list[float]
        Close prices in chronological order (oldest first).

    Returns
    -------
    dict
        Keys: rsi, macd, macd_signal, bb_upper, bb_lower, ema_20.
        All values are floats representing the most recent indicator value.
        All values are None if there is insufficient data (len(prices) < 26).
    """
    empty: dict = {
        "rsi": None,
        "macd": None,
        "macd_signal": None,
        "bb_upper": None,
        "bb_lower": None,
        "ema_20": None,
    }

    if len(prices) < 26:
        return empty

    price_series = pd.Series(prices, dtype=float)

    # --- RSI(14) ---
    delta = price_series.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1])

    # --- MACD(12, 26, 9) ---
    ema12 = price_series.ewm(span=12, adjust=False).mean()
    ema26 = price_series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd = float(macd_line.iloc[-1])
    macd_signal = float(signal_line.iloc[-1])

    # --- Bollinger Bands(20) ---
    sma20 = price_series.rolling(20).mean()
    std20 = price_series.rolling(20).std()
    bb_upper_series = sma20 + 2 * std20
    bb_lower_series = sma20 - 2 * std20
    bb_upper = float(bb_upper_series.iloc[-1])
    bb_lower = float(bb_lower_series.iloc[-1])

    # --- EMA(20) ---
    ema20 = price_series.ewm(span=20, adjust=False).mean()
    ema_20 = float(ema20.iloc[-1])

    return {
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "ema_20": ema_20,
    }
