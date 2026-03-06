import time
import logging

import requests

from crypto_assistant.config import COINS

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"

PARAMS = {
    "localization": "false",
    "tickers": "false",
    "market_data": "true",
    "community_data": "false",
    "developer_data": "false",
}

_BETWEEN_REQUEST_SLEEP = 2.5
_RATE_LIMIT_SLEEP = 30


def _fetch_coin(session: requests.Session, coin_id: str) -> dict | None:
    """Fetch market data for a single coin. Returns a structured dict or None on failure."""
    url = f"{BASE_URL}/coins/{coin_id}"

    response = None
    for attempt in range(2):
        try:
            response = session.get(url, params=PARAMS, timeout=15)
            response.raise_for_status()
            break
        except requests.exceptions.HTTPError as exc:
            if response is not None and response.status_code == 429:
                wait = _RATE_LIMIT_SLEEP * (attempt + 1)
                logger.warning(
                    "Rate limited (429) for '%s'. Waiting %ds (attempt %d/2).",
                    coin_id, wait, attempt + 1,
                )
                time.sleep(wait)
            else:
                logger.error("HTTP error fetching coin '%s': %s", coin_id, exc)
                return None
        except requests.exceptions.RequestException as exc:
            logger.error("Request error fetching coin '%s': %s", coin_id, exc)
            return None
    else:
        logger.error("Skipping '%s' after 2 rate limit retries.", coin_id)
        return None

    try:
        data = response.json()
        market_data = data["market_data"]

        current_price: float = market_data["current_price"]["usd"]
        high: float = market_data["high_24h"]["usd"]
        low: float = market_data["low_24h"]["usd"]
        volume: float = market_data["total_volume"]["usd"]
        price_change_24h: float = market_data["price_change_24h"]

        open_price: float = current_price - price_change_24h
        close_price: float = current_price
        timestamp: int = int(time.time())

        return {
            "coin_id": coin_id,
            "timestamp": timestamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close_price,
            "volume": volume,
        }

    except (KeyError, TypeError, ValueError) as exc:
        logger.error("Failed to parse market data for coin '%s': %s", coin_id, exc)
        return None


def fetch_prices() -> list[dict]:
    """
    Fetch current price data for all coins defined in COINS.

    Returns a list of dicts with keys:
        coin_id, timestamp, open, high, low, close, volume

    Coins that fail to fetch or parse are skipped without crashing the cycle.
    """
    results: list[dict] = []

    with requests.Session() as session:
        for index, coin_id in enumerate(COINS):
            record = _fetch_coin(session, coin_id)

            if record is not None:
                results.append(record)
            else:
                print(f"[fetch_prices] Skipping coin '{coin_id}' due to an error.")

            # Sleep between requests, but skip the delay after the last coin.
            if index < len(COINS) - 1:
                time.sleep(_BETWEEN_REQUEST_SLEEP)

    return results
