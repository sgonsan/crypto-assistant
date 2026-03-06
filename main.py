import logging
import os
import sys
import threading

import uvicorn

from crypto_assistant import db, predictor
from crypto_assistant.config import DB_PATH, COINS
from crypto_assistant.engine import run
from crypto_assistant.backfill import run_backfill
from crypto_assistant.api.app import app as api_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _stdin_listener():
    """Type 'r' + Enter to restart the application."""
    for line in sys.stdin:
        if line.strip().lower() in ("r", "restart"):
            logging.info("Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    logging.info("Initializing database...")
    db.init_db(DB_PATH)

    logging.info("Running historical data backfill...")
    run_backfill(DB_PATH)

    logging.info("Loading or training initial model...")
    training_data = []
    for coin_id in COINS:
        rows = db.get_training_data(DB_PATH, coin_id, n=200)
        for i in range(len(rows) - 1):
            row = dict(rows[i])
            row["next_close"] = rows[i + 1]["close"]
            training_data.append(row)
    if training_data:
        predictor.train(training_data)
    else:
        logging.info("Not enough data yet for initial training.")

    logging.info("Starting API server on http://localhost:8000")
    threading.Thread(
        target=lambda: uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="warning"),
        daemon=True,
    ).start()

    threading.Thread(target=_stdin_listener, daemon=True).start()
    logging.info("Starting main loop... (type 'r' + Enter to restart)")
    run()
