import time
import logging

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"
_RATE_LIMIT_SLEEP = 30


def fetch_market_chart(
    session: requests.Session, coin_id: str, days: int
) -> list[dict] | None:
    """
    Fetch historical OHLCV data from CoinGecko's market_chart endpoint.

    CoinGecko auto-granulates:
      - days >  90 → one data point per day
      - days <= 90 → one data point per hour

    OHLCV is approximated because the free market_chart endpoint only returns
    close prices and volumes:
      open  = previous candle's close (first candle: open = close)
      high  = max(open, close)
      low   = min(open, close)
      close = price from API
      volume = from total_volumes

    Returns a list of dicts with keys:
        coin_id, timestamp (unix seconds), open, high, low, close, volume
    Returns None on unrecoverable error.
    """
    url = f"{BASE_URL}/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days}

    _MAX_ATTEMPTS = 4
    response = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            break
        except requests.exceptions.HTTPError as exc:
            if response is not None and response.status_code == 429:
                wait = _RATE_LIMIT_SLEEP * (2 ** attempt)  # 30, 60, 120, 240s
                logger.warning(
                    "Rate limited fetching history for '%s' (%d days). "
                    "Waiting %ds (attempt %d/%d).",
                    coin_id, days, wait, attempt + 1, _MAX_ATTEMPTS,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "HTTP error fetching history for '%s' (%d days): %s",
                    coin_id, days, exc,
                )
                return None
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Request error fetching history for '%s' (%d days): %s",
                coin_id, days, exc,
            )
            return None
    else:
        logger.error(
            "Skipping '%s' historical (%d days) after %d rate-limit retries.",
            coin_id, days, _MAX_ATTEMPTS,
        )
        return None

    try:
        data = response.json()
        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
    except Exception as exc:
        logger.error("Failed to parse history response for '%s': %s", coin_id, exc)
        return None

    # Build a fast lookup: unix_second → volume
    vol_map: dict[int, float] = {
        int(ts_ms // 1000): vol for ts_ms, vol in volumes
    }

    candles: list[dict] = []
    prev_close: float | None = None

    for ts_ms, close in prices:
        ts = int(ts_ms // 1000)
        open_ = prev_close if prev_close is not None else close
        high = max(open_, close)
        low = min(open_, close)
        vol = vol_map.get(ts, 0.0)

        candles.append({
            "coin_id": coin_id,
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        })
        prev_close = close

    return candles
