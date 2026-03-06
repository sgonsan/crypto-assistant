# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r crypto_assistant/requirements.txt

# Run
python -m crypto_assistant.main   # or: python crypto_assistant/main.py
```

The app starts the Dash dashboard at `http://localhost:8050` and begins the 60-second data collection loop automatically.

## Architecture

**Entry point:** `crypto_assistant/main.py` — initializes the DB, optionally trains the model on existing data, then calls `engine.run()`.

**Data flow (every 60 s):**
```
CoinGecko API → fetcher → db.prices → indicators → db.indicators → predictor → db.predictions → LOG_FEED (in-memory)
```

**Key modules:**
- `fetcher/coingecko.py` — fetches OHLCV from CoinGecko public API; sleeps 1.5 s between coins, auto-retries after 30 s on 429
- `db/database.py` — all SQLite operations (3 tables: `prices`, `indicators`, `predictions`)
- `indicators/technical.py` — computes RSI(14), MACD(12,26,9), Bollinger Bands(SMA20 ±2σ), EMA(20); requires ≥26 candles, returns `None` values otherwise
- `predictor/ml_model.py` — `RandomForestClassifier` with 6 features (rsi, macd, macd_signal, bb_position, ema_distance, volume_delta); persisted as `model.pkl` via joblib; retrains every 60 iterations (~1 hour)
- `engine/loop.py` — main loop; also handles model retraining every 60 iterations
- `dashboard/state.py` — shared `LOG_FEED` list (max 50 lines) used between engine and dashboard
- `dashboard/app.py` — Dash app with 3 tabs (Live Price, Candlestick+indicators, Prediction History) and auto-refresh every 10 s

**Config** (`config.py`): `COINS` (CoinGecko IDs), `INTERVAL` (60 s), `DB_PATH`, `MODEL_PATH`.

## Known Limitations

- OHLCV candles use CoinGecko's 24h high/low, not per-interval OHLCV
- `actual_direction` in predictions is never populated automatically — prediction accuracy scatter will show all grey points
- Model cold-starts return `("UP", 0.5)` until ≥10 samples with valid indicators exist
