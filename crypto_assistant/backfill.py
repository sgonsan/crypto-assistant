"""
Historical data backfill.

On first startup, fetches historical OHLCV and stores it with technical
indicators. Subsequent startups skip assets that already have data older
than 30 days.

── Crypto (CoinGecko) ────────────────────────────────────────────────────────
  Period                Granularity     CoinGecko fetch
  ──────────────────────────────────────────────────────
  1 year – 1 month ago  daily           days=365, all daily points
  1 month – 1 week ago  6-hour          days=30,  every 6th hourly point
  last week             hourly          days=7,   all hourly points

Note: the CoinGecko free API only supports up to 365 days on market_chart.

── Stocks (Yahoo Finance v8) ──────────────────────────────────────────────────
  Period                Granularity     Yahoo Finance v8 fetch
  ──────────────────────────────────────────────────────────────
  older than 2 years    daily           interval=1d, range=5y
  last 2 years          hourly          interval=1h, range=730d
"""

import time
import logging

import requests

from crypto_assistant.config import COINS, STOCKS, DB_PATH
from crypto_assistant import db
from crypto_assistant.fetcher.historical import fetch_market_chart
from crypto_assistant.fetcher.historical_stocks import fetch_stock_history
from crypto_assistant.indicators.technical import compute_indicators_series

logger = logging.getLogger(__name__)

_BETWEEN_FETCHES_SLEEP = 8.0   # seconds between API calls for the same coin
_BETWEEN_COINS_SLEEP = 12.0    # seconds between coins


def _build_candle_set(session: requests.Session, coin_id: str) -> list[dict]:
    """
    Fetch and merge three tiers of historical data for one coin.
    Returns a sorted, deduplicated list of candle dicts.

    Time order:  one_year_ago < one_month_ago < one_week_ago < now
    """
    now = int(time.time())
    one_year_ago  = now - 365 * 86400
    one_month_ago = now - 30  * 86400
    one_week_ago  = now - 7   * 86400

    all_candles: dict[int, dict] = {}   # timestamp → candle (dedup key)

    # ── Tier 1: 365 days → daily → keep only data older than 1 month ─────────
    logger.info("  [%s] Fetching 1-year data…", coin_id)
    candles = fetch_market_chart(session, coin_id, days=365)
    if candles:
        added = 0
        for c in candles:
            if one_year_ago <= c["timestamp"] < one_month_ago:
                all_candles[c["timestamp"]] = c
                added += 1
        logger.info("  [%s] 1y daily: %d points kept", coin_id, added)
    time.sleep(_BETWEEN_FETCHES_SLEEP)

    # ── Tier 2: 30 days → hourly → every 6th → between 1 week and 1 month ───
    logger.info("  [%s] Fetching 30-day data…", coin_id)
    candles = fetch_market_chart(session, coin_id, days=30)
    if candles:
        every_6h = candles[::6]
        added = 0
        for c in every_6h:
            if one_month_ago <= c["timestamp"] < one_week_ago:
                all_candles[c["timestamp"]] = c
                added += 1
        logger.info("  [%s] 30d 6h: %d points kept", coin_id, added)
    time.sleep(_BETWEEN_FETCHES_SLEEP)

    # ── Tier 3: 7 days → hourly → all ────────────────────────────────────────
    logger.info("  [%s] Fetching 7-day data…", coin_id)
    candles = fetch_market_chart(session, coin_id, days=7)
    if candles:
        added = 0
        for c in candles:
            if c["timestamp"] >= one_week_ago:
                all_candles[c["timestamp"]] = c
                added += 1
        logger.info("  [%s] 7d hourly: %d points kept", coin_id, added)

    return sorted(all_candles.values(), key=lambda c: c["timestamp"])


def _store_candles(db_path: str, candles: list[dict]) -> None:
    """Insert prices and compute+insert indicators for a list of candles."""
    if not candles:
        return

    db.insert_prices_batch(db_path, candles)

    closes = [c["close"] for c in candles]
    indicators_list = compute_indicators_series(closes)

    ind_rows = []
    for candle, ind in zip(candles, indicators_list):
        if ind["rsi"] is None:
            continue
        ind_rows.append({
            "coin_id":      candle["coin_id"],
            "timestamp":    candle["timestamp"],
            "rsi":          ind["rsi"],
            "macd":         ind["macd"],
            "macd_signal":  ind["macd_signal"],
            "bb_upper":     ind["bb_upper"],
            "bb_lower":     ind["bb_lower"],
            "ema_20":       ind["ema_20"],
        })

    db.insert_indicators_batch(db_path, ind_rows)
    logger.info(
        "  Stored %d price rows and %d indicator rows.",
        len(candles), len(ind_rows),
    )


def _build_stock_candle_set(symbol: str) -> list[dict]:
    """
    Fetch 2 years of hourly + 5 years of daily historical data for one stock.
    Hourly data covers the recent period; daily fills in older history.
    Returns a sorted, deduplicated list of candle dicts.
    """
    all_candles: dict[int, dict] = {}
    now = int(time.time())
    two_years_ago = now - 730 * 86400

    # ── Tier 1: 5y daily → keep data older than 730 days ─────────────────────
    logger.info("  [%s] Fetching 5-year daily data (Yahoo Finance)…", symbol)
    daily = fetch_stock_history(symbol, interval="1d", range_="5y")
    if daily:
        added = 0
        for c in daily:
            if c["timestamp"] < two_years_ago:
                all_candles[c["timestamp"]] = c
                added += 1
        logger.info("  [%s] 5y daily: %d points kept (older than 2y)", symbol, added)
    time.sleep(2.0)

    # ── Tier 2: 730d hourly → all recent data ────────────────────────────────
    logger.info("  [%s] Fetching 730-day hourly data (Yahoo Finance)…", symbol)
    hourly = fetch_stock_history(symbol, interval="1h", range_="730d")
    if hourly:
        for c in hourly:
            all_candles[c["timestamp"]] = c
        logger.info("  [%s] 730d hourly: %d points", symbol, len(hourly))

    return sorted(all_candles.values(), key=lambda c: c["timestamp"])


def run_stock_backfill(db_path: str = DB_PATH) -> None:
    """
    Run the historical backfill for all configured stocks via Yahoo Finance v8.
    Skips any stock that already has data older than 30 days.
    """
    logger.info("=== Stock historical backfill starting ===")

    for idx, symbol in enumerate(STOCKS):
        if db.has_historical_data(db_path, symbol):
            logger.info("Historical data already present for '%s' – skipping.", symbol)
            if idx < len(STOCKS) - 1:
                time.sleep(5.0)
            continue

        logger.info("Backfilling stock '%s'…", symbol)
        candles = _build_stock_candle_set(symbol)
        logger.info("  [%s] Total candles to store: %d", symbol, len(candles))
        _store_candles(db_path, candles)
        logger.info("Backfill complete for '%s'.", symbol)

        if idx < len(STOCKS) - 1:
            time.sleep(5.0)

    logger.info("=== Stock historical backfill done ===")


def run_backfill(db_path: str = DB_PATH) -> None:
    """
    Run the historical backfill for all configured coins and stocks.
    Skips any asset that already has data older than 30 days.
    """
    logger.info("=== Historical backfill starting ===")

    with requests.Session() as session:
        for idx, coin_id in enumerate(COINS):
            if db.has_historical_data(db_path, coin_id):
                logger.info(
                    "Historical data already present for '%s' – skipping.", coin_id
                )
                if idx < len(COINS) - 1:
                    time.sleep(_BETWEEN_COINS_SLEEP)
                continue

            logger.info("Backfilling '%s'…", coin_id)
            candles = _build_candle_set(session, coin_id)
            logger.info(
                "  [%s] Total candles to store: %d", coin_id, len(candles)
            )
            _store_candles(db_path, candles)
            logger.info("Backfill complete for '%s'.", coin_id)

            if idx < len(COINS) - 1:
                time.sleep(_BETWEEN_COINS_SLEEP)

    logger.info("=== Historical backfill done ===")

    run_stock_backfill(db_path)
