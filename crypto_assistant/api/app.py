"""
FastAPI backend for Crypto Assistant.

Endpoints:
  GET  /api/coins                  → list of configured coin IDs
  GET  /api/kpi                    → current price, 24h change, last prediction per coin
  GET  /api/prices/{coin_id}       → full price history (since=0 by default)
  GET  /api/indicators/{coin_id}   → full indicator history
  GET  /api/predictions/{coin_id}  → recent predictions (n=50)
  WS   /api/ws/log                 → live engine log feed
"""

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from crypto_assistant.config import COINS, DB_PATH
from crypto_assistant.db.database import (
    get_indicators_since,
    get_prices_since,
    get_recent_predictions,
)

app = FastAPI(title="Crypto Assistant API")


# ── REST routes ───────────────────────────────────────────────────────────────

@app.get("/api/coins")
def list_coins():
    return COINS


@app.get("/api/kpi")
def get_kpi():
    now = int(time.time())
    result = []
    for coin_id in COINS:
        prices = get_prices_since(DB_PATH, coin_id, since_ts=now - 86400)
        preds  = get_recent_predictions(DB_PATH, coin_id, n=1)

        if not prices:
            result.append({
                "coin_id": coin_id, "current_price": None,
                "change_pct": 0.0, "predicted_direction": None, "confidence": 0.0,
            })
            continue

        current    = prices[-1]["close"]
        old        = prices[0]["close"]
        change_pct = (current - old) / old * 100 if old else 0.0
        direction  = preds[-1]["predicted_direction"] if preds else None
        confidence = preds[-1]["confidence"] if preds else 0.0

        result.append({
            "coin_id": coin_id, "current_price": current,
            "change_pct": change_pct,
            "predicted_direction": direction, "confidence": confidence,
        })
    return result


@app.get("/api/prices/{coin_id}")
def get_prices(coin_id: str, since: int = 0):
    return get_prices_since(DB_PATH, coin_id, since_ts=since)


@app.get("/api/indicators/{coin_id}")
def get_indicators(coin_id: str, since: int = 0):
    return get_indicators_since(DB_PATH, coin_id, since_ts=since)


@app.get("/api/predictions/{coin_id}")
def get_predictions(coin_id: str, n: int = 50):
    return get_recent_predictions(DB_PATH, coin_id, n=n)


# ── WebSocket: live log ───────────────────────────────────────────────────────

@app.websocket("/api/ws/log")
async def log_ws(websocket: WebSocket):
    await websocket.accept()
    from crypto_assistant.api.state import LOG_FEED
    sent = len(LOG_FEED)
    try:
        while True:
            if len(LOG_FEED) > sent:
                await websocket.send_json(LOG_FEED[sent:])
                sent = len(LOG_FEED)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ── Serve built React app (production) ───────────────────────────────────────

_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(str(_DIST / "index.html"))
