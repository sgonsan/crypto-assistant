# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r crypto_assistant/requirements.txt

# Run
python main.py
```

The API server starts at `http://localhost:8000` and begins the 60-second data collection loop automatically. The frontend (React) is served from `frontend/dist` if built.

## Architecture

**Entry point:** `main.py` — initializes the DB, runs historical backfill, optionally trains the model on existing data, starts the FastAPI server (port 8000) in a daemon thread, then calls `engine.run()`.

**Data flow (every 60 s):**
```
CoinGecko API → fetcher/coingecko.py      ↘
                                            db.prices → indicators → db.indicators → predictor → db.predictions → LOG_FEED (in-memory)
Yahoo Finance → fetcher/yfinance_fetcher.py ↗
```

**Key modules:**
- `fetcher/coingecko.py` — fetches live crypto OHLCV from CoinGecko public API; sleeps 2.5 s between coins, auto-retries after 30 s on 429; open is derived as `current_price - price_change_24h`, high/low are 24h values
- `fetcher/historical.py` — fetches historical crypto data via CoinGecko `market_chart` endpoint; auto-granulates (daily >90 days, hourly ≤90 days); open/high/low are approximated from close prices
- `fetcher/yfinance_fetcher.py` — fetches live stock OHLCV via Yahoo Finance v8 API directly (`query1.finance.yahoo.com`); returns the most recent 5-min bar; bar's actual timestamp is used (not wall-clock time) so the DB unique index deduplicates within the same 5-min window; sleeps 1 s between stocks
- `fetcher/historical_stocks.py` — fetches historical stock OHLCV via Yahoo Finance v8; two tiers: `interval=1d, range=5y` for data older than 2 years, `interval=1h, range=730d` for recent data; retries on 429 with backoff
- `db/database.py` — all SQLite operations (3 tables: `prices`, `indicators`, `predictions`)
- `indicators/technical.py` — computes RSI(14), MACD(12,26,9), Bollinger Bands(SMA20 ±2σ), EMA(20); requires ≥26 candles, returns `None` values otherwise
- `predictor/ml_model.py` — `RandomForestClassifier` persisted as `model.pkl` via joblib; retrains every 60 iterations (~1 hour) using data from all COINS + STOCKS
- `engine/loop.py` — main loop; fetches and processes both crypto and stocks each cycle; retraining pulls 200 rows per asset from COINS + STOCKS
- `backfill.py` — `run_backfill()` runs crypto backfill (CoinGecko, 3-tier) then stock backfill (Yahoo Finance v8, 2-tier); skips any asset that already has data older than 30 days
- `api/state.py` — shared `LOG_FEED` list (max 50 lines) used between engine and API
- `api/app.py` — FastAPI app; serves REST endpoints and a WebSocket log feed; serves the built React SPA from `frontend/dist` if present

**Config** (`config.py`): `COINS` (10 CoinGecko IDs), `STOCKS` (8 Yahoo Finance tickers: AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, SPY), `INTERVAL` (60 s), `DB_PATH`, `MODEL_PATH`.

## API Endpoints

- `GET /api/coins` — combined list of `COINS + STOCKS`
- `GET /api/assets` — `{"crypto": [...], "stocks": [...]}` for frontend asset-type grouping
- `GET /api/kpi` — current price, 24h change %, last predicted direction and confidence for all assets
- `GET /api/prices/{coin_id}?since=<ts>` — full price history since unix timestamp (default 0)
- `GET /api/indicators/{coin_id}?since=<ts>` — indicator history since unix timestamp
- `GET /api/predictions/{coin_id}?n=50` — recent predictions (default last 50)
- `WS  /api/ws/log` — live engine log feed (pushes new lines as JSON arrays)

## Known Limitations

- Crypto OHLCV: open is derived from `current_price - price_change_24h`; high/low are 24h values, not per-interval
- `actual_direction` in predictions is never populated automatically — prediction accuracy will show no ground truth
- Model cold-starts return `("UP", 0.5)` until ≥10 samples with valid indicators exist
- Stocks only have meaningful live data during market hours (Mon–Fri 9:30–16:00 ET); outside hours the last available bar is returned, so the effective new-data rate is once per 5 minutes per stock
- Yahoo Finance v8 intraday (1h) data is only available for the last 730 days; daily data goes back up to 5 years
- Initial model training in `main.py` only uses COINS data (not STOCKS); subsequent retraining in `engine/loop.py` uses both
