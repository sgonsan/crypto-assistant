"""
Live stock price fetcher using Yahoo Finance v8 API directly.

Bypasses the yfinance library (which requires fc.yahoo.com for auth) and
calls query1.finance.yahoo.com directly, which is publicly accessible.

Each fetch returns the most recent 5-minute bar so the engine loop accumulates
intraday price updates during market hours. The bar's actual timestamp is used
(not wall-clock time), so the DB unique index deduplicates within the same bar.
Outside market hours the last available bar is returned.
"""
import logging
import time

import requests

from crypto_assistant.config import STOCKS

logger = logging.getLogger(__name__)

_YF_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_BETWEEN_REQUEST_SLEEP = 1.0


def _fetch_stock(session: requests.Session, symbol: str) -> dict | None:
    """Fetch the most recent 5-min bar for a stock. Returns None on failure."""
    url = _YF_URL.format(symbol=symbol)
    params = {"interval": "5m", "range": "1d"}

    try:
        resp = session.get(url, params=params, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except Exception as exc:
        logger.error("Failed to fetch stock '%s': %s", symbol, exc)
        return None

    # Find the last bar with complete data
    for i in range(len(timestamps) - 1, -1, -1):
        try:
            o = quote["open"][i]
            h = quote["high"][i]
            l = quote["low"][i]
            c = quote["close"][i]
            v = quote.get("volume", [None])[i]
            if None in (o, h, l, c):
                continue
            return {
                "coin_id":   symbol,
                "timestamp": int(timestamps[i]),
                "open":      float(o),
                "high":      float(h),
                "low":       float(l),
                "close":     float(c),
                "volume":    float(v) if v is not None else 0.0,
            }
        except (IndexError, TypeError, ValueError):
            continue

    logger.warning("No valid bar found for stock '%s'", symbol)
    return None


def fetch_stock_prices() -> list[dict]:
    """
    Fetch the most recent 5-min OHLCV bar for all stocks defined in STOCKS.

    Returns a list of dicts with keys:
        coin_id, timestamp, open, high, low, close, volume

    Uses Yahoo Finance v8 directly (no API key required).
    The bar timestamp is used so the DB deduplicates bars within the same
    5-minute window — effective update rate is one bar per 5 minutes.
    Stocks that fail to fetch are skipped without crashing the cycle.
    """
    results: list[dict] = []

    with requests.Session() as session:
        for index, symbol in enumerate(STOCKS):
            record = _fetch_stock(session, symbol)
            if record is not None:
                results.append(record)
            else:
                print(f"[fetch_stock_prices] Skipping stock '{symbol}' due to an error.")

            if index < len(STOCKS) - 1:
                time.sleep(_BETWEEN_REQUEST_SLEEP)

    return results
