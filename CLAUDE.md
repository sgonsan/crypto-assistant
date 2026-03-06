# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r crypto_assistant/requirements.txt  # includes yfinance (required for stock support)

# Run
python -m crypto_assistant.main   # or: python crypto_assistant/main.py
```

The app starts the Dash dashboard at `http://localhost:8050` and begins the 60-second data collection loop automatically.

## Architecture

**Entry point:** `crypto_assistant/main.py` — initializes the DB, optionally trains the model on existing data, then calls `engine.run()`.

**Data flow (every 60 s):**
```
CoinGecko API → fetcher/coingecko.py     ↘
                                           db.prices → indicators → db.indicators → predictor → db.predictions → LOG_FEED (in-memory)
Yahoo Finance → fetcher/yfinance_fetcher.py ↗
```

**Key modules:**
- `fetcher/coingecko.py` — fetches OHLCV from CoinGecko public API; sleeps 1.5 s between coins, auto-retries after 30 s on 429
- `fetcher/yfinance_fetcher.py` — fetches live stock OHLCV via `yfinance`; `fetch_stock_prices()` uses `yf.Ticker(symbol).history(period="2d", interval="1d")` to get the latest daily bar
- `fetcher/historical_stocks.py` — fetches historical stock OHLCV via yfinance in three tiers: 1 year daily, 60 days hourly, 5 days hourly
- `db/database.py` — all SQLite operations (3 tables: `prices`, `indicators`, `predictions`)
- `indicators/technical.py` — computes RSI(14), MACD(12,26,9), Bollinger Bands(SMA20 ±2σ), EMA(20); requires ≥26 candles, returns `None` values otherwise
- `predictor/ml_model.py` — `RandomForestClassifier` with 6 features (rsi, macd, macd_signal, bb_position, ema_distance, volume_delta); persisted as `model.pkl` via joblib; retrains every 60 iterations (~1 hour)
- `engine/loop.py` — main loop; fetches and processes both crypto and stocks each cycle; handles model retraining every 60 iterations
- `backfill.py` — backfills historical data for both crypto (CoinGecko) and stocks (yfinance); uses `has_historical_data` check to skip already-backfilled assets
- `dashboard/state.py` — shared `LOG_FEED` list (max 50 lines) used between engine and dashboard
- `dashboard/app.py` — Dash app with 3 tabs (Live Price, Candlestick+indicators, Prediction History), asset type toggle (Crypto / Stocks) in header, and auto-refresh every 10 s

**Config** (`config.py`): `COINS` (CoinGecko IDs), `STOCKS` (Yahoo Finance tickers: AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, SPY), `INTERVAL` (60 s), `DB_PATH`, `MODEL_PATH`.

## API Endpoints

- `/api/coins` — returns combined list of `COINS + STOCKS`
- `/api/assets` — returns `{"crypto": [...], "stocks": [...]}` for frontend asset-type grouping

## Known Limitations

- OHLCV candles use CoinGecko's 24h high/low, not per-interval OHLCV
- `actual_direction` in predictions is never populated automatically — prediction accuracy scatter will show all grey points
- Model cold-starts return `("UP", 0.5)` until ≥10 samples with valid indicators exist
- Stocks only have meaningful live data during market hours (Mon–Fri 9:30–16:00 ET). Outside hours, the fetcher returns the last trading day's bar, so predictions will be stale.
- yfinance intraday data (1h intervals) is only available for the last 730 days; daily data goes back further.
