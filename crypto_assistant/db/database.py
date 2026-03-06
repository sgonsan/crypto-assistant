import sqlite3


def init_db(db_path: str) -> None:
    """Create tables if they do not already exist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id   TEXT    NOT NULL,
                timestamp INTEGER NOT NULL,
                open      REAL    NOT NULL,
                high      REAL    NOT NULL,
                low       REAL    NOT NULL,
                close     REAL    NOT NULL,
                volume    REAL    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS indicators (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id     TEXT    NOT NULL,
                timestamp   INTEGER NOT NULL,
                rsi         REAL,
                macd        REAL,
                macd_signal REAL,
                bb_upper    REAL,
                bb_lower    REAL,
                ema_20      REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id            TEXT    NOT NULL,
                timestamp          INTEGER NOT NULL,
                predicted_direction TEXT   NOT NULL,
                confidence         REAL    NOT NULL,
                actual_direction   TEXT
            )
        """)
        # Remove duplicate rows before creating unique indices (keeps the row
        # with the lowest id for each coin_id + timestamp pair).
        conn.execute("""
            DELETE FROM prices
            WHERE id NOT IN (
                SELECT MIN(id) FROM prices GROUP BY coin_id, timestamp
            )
        """)
        conn.execute("""
            DELETE FROM indicators
            WHERE id NOT IN (
                SELECT MIN(id) FROM indicators GROUP BY coin_id, timestamp
            )
        """)
        # Unique indices prevent duplicate rows during historical backfill
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_coin_ts
            ON prices (coin_id, timestamp)
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_indicators_coin_ts
            ON indicators (coin_id, timestamp)
        """)
        conn.commit()


def has_historical_data(db_path: str, coin_id: str) -> bool:
    """Return True if prices older than 30 days already exist for coin_id."""
    thirty_days_ago = int(__import__("time").time()) - 30 * 86400
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM prices WHERE coin_id = ? AND timestamp < ?",
            (coin_id, thirty_days_ago),
        ).fetchone()
    return row[0] > 0


def insert_prices_batch(db_path: str, rows: list[dict]) -> None:
    """Insert multiple OHLCV rows, ignoring duplicates (coin_id + timestamp)."""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO prices
                (coin_id, timestamp, open, high, low, close, volume)
            VALUES (:coin_id, :timestamp, :open, :high, :low, :close, :volume)
            """,
            rows,
        )
        conn.commit()


def insert_indicators_batch(db_path: str, rows: list[dict]) -> None:
    """Insert multiple indicator rows, ignoring duplicates (coin_id + timestamp)."""
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO indicators
                (coin_id, timestamp, rsi, macd, macd_signal, bb_upper, bb_lower, ema_20)
            VALUES
                (:coin_id, :timestamp, :rsi, :macd, :macd_signal,
                 :bb_upper, :bb_lower, :ema_20)
            """,
            rows,
        )
        conn.commit()


def insert_price(
    db_path: str,
    coin_id: str,
    timestamp: int,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> None:
    """Insert a single OHLCV price row."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO prices (coin_id, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (coin_id, timestamp, open, high, low, close, volume),
        )
        conn.commit()


def insert_indicators(
    db_path: str,
    coin_id: str,
    timestamp: int,
    rsi: float,
    macd: float,
    macd_signal: float,
    bb_upper: float,
    bb_lower: float,
    ema_20: float,
) -> None:
    """Insert a row of computed technical indicators."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO indicators
                (coin_id, timestamp, rsi, macd, macd_signal, bb_upper, bb_lower, ema_20)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (coin_id, timestamp, rsi, macd, macd_signal, bb_upper, bb_lower, ema_20),
        )
        conn.commit()


def insert_prediction(
    db_path: str,
    coin_id: str,
    timestamp: int,
    predicted_direction: str,
    confidence: float,
) -> None:
    """Insert a new prediction (actual_direction starts as NULL)."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO predictions (coin_id, timestamp, predicted_direction, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (coin_id, timestamp, predicted_direction, confidence),
        )
        conn.commit()


def get_prices_since(
    db_path: str, coin_id: str, since_ts: int, limit: int = 5000
) -> list[dict]:
    """Return price rows for coin_id with timestamp >= since_ts, ascending."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT id, coin_id, timestamp, open, high, low, close, volume
            FROM prices
            WHERE coin_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (coin_id, since_ts, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_indicators_since(
    db_path: str, coin_id: str, since_ts: int, limit: int = 5000
) -> list[dict]:
    """Return indicator rows for coin_id with timestamp >= since_ts, ascending."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT id, coin_id, timestamp, rsi, macd, macd_signal, bb_upper, bb_lower, ema_20
            FROM indicators
            WHERE coin_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (coin_id, since_ts, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_recent_prices(db_path: str, coin_id: str, n: int = 100) -> list[dict]:
    """Return the *n* most-recent price rows for *coin_id*, ordered by timestamp ASC."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT id, coin_id, timestamp, open, high, low, close, volume
            FROM prices
            WHERE coin_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (coin_id, n),
        )
        rows = cursor.fetchall()

    # Reverse so the result is ascending by timestamp
    return [dict(row) for row in reversed(rows)]


def get_recent_indicators(db_path: str, coin_id: str, n: int = 100) -> list[dict]:
    """Return the *n* most-recent indicator rows for *coin_id*, ordered by timestamp ASC."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT id, coin_id, timestamp, rsi, macd, macd_signal, bb_upper, bb_lower, ema_20
            FROM indicators
            WHERE coin_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (coin_id, n),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


def get_recent_predictions(db_path: str, coin_id: str, n: int = 20) -> list[dict]:
    """Return the *n* most-recent prediction rows for *coin_id*, ordered by timestamp ASC."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT id, coin_id, timestamp, predicted_direction, confidence, actual_direction
            FROM predictions
            WHERE coin_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (coin_id, n),
        )
        rows = cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


def get_training_data(db_path: str, coin_id: str, n: int = 200) -> list[dict]:
    """Return up to *n* rows joining prices with indicators, ordered by timestamp ASC."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        """
        SELECT p.open, p.high, p.low, p.close, p.volume,
               i.rsi, i.macd, i.macd_signal, i.bb_upper, i.bb_lower, i.ema_20,
               p.timestamp
        FROM prices p
        JOIN indicators i ON p.coin_id = i.coin_id AND p.timestamp = i.timestamp
        WHERE p.coin_id = ?
        ORDER BY p.timestamp DESC
        LIMIT ?
        """,
        (coin_id, n),
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return list(reversed(rows))


def update_actual_direction(
    db_path: str, prediction_id: int, actual_direction: str
) -> None:
    """Backfill the actual_direction for a previously stored prediction."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE predictions
            SET actual_direction = ?
            WHERE id = ?
            """,
            (actual_direction, prediction_id),
        )
        conn.commit()
