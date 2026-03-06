"""
Historical stock data fetcher using Yahoo Finance v8 API directly.

Bypasses the yfinance library (which requires fc.yahoo.com for auth) and
calls query1.finance.yahoo.com directly, which is publicly accessible.

Available granularities tested:
  interval=1h, range=730d  → ~5000 hourly bars (2 years, market hours only)
  interval=1d, range=5y    → ~1255 daily bars (5 years)
"""
import logging
import time

import requests

logger = logging.getLogger(__name__)

_YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_RATE_LIMIT_SLEEP = 30


def fetch_stock_history(
    symbol: str,
    interval: str = "1h",
    range_: str = "730d",
) -> list[dict] | None:
    """
    Fetch historical OHLCV for a stock symbol via Yahoo Finance v8.

    Args:
        symbol:   Ticker (e.g. "AAPL")
        interval: Bar size — "1m","5m","15m","1h","1d" etc.
        range_:   Lookback — "1d","5d","60d","730d","1y","5y","max" etc.

    Returns a list of candle dicts sorted ascending by timestamp, with keys:
        coin_id, timestamp (unix seconds), open, high, low, close, volume
    Returns None on unrecoverable error.
    """
    url = _YF_URL.format(symbol=symbol)
    params = {"interval": interval, "range": range_}

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=_HEADERS, timeout=30)
            if resp.status_code == 429:
                wait = _RATE_LIMIT_SLEEP * (attempt + 1)
                logger.warning(
                    "Rate limited fetching '%s' (%s/%s). Waiting %ds.",
                    symbol, interval, range_, wait,
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            logger.error(
                "Request error fetching '%s' (%s/%s): %s", symbol, interval, range_, exc
            )
            return None
    else:
        logger.error("Giving up on '%s' after rate-limit retries.", symbol)
        return None

    try:
        data = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        opens   = quote.get("open",   [])
        highs   = quote.get("high",   [])
        lows    = quote.get("low",    [])
        closes  = quote.get("close",  [])
        volumes = quote.get("volume", [])
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Failed to parse response for '%s': %s", symbol, exc)
        return None

    candles: list[dict] = []
    for i, ts in enumerate(timestamps):
        try:
            o = opens[i]
            h = highs[i]
            l = lows[i]
            c = closes[i]
            v = volumes[i]
            # Skip bars with missing data (common at market open/close boundaries)
            if None in (o, h, l, c):
                continue
            candles.append({
                "coin_id":   symbol,
                "timestamp": int(ts),
                "open":      float(o),
                "high":      float(h),
                "low":       float(l),
                "close":     float(c),
                "volume":    float(v) if v is not None else 0.0,
            })
        except (IndexError, TypeError, ValueError):
            continue

    return sorted(candles, key=lambda c: c["timestamp"])
