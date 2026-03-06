import time
import logging
from datetime import datetime
from crypto_assistant import db, fetcher, indicators, predictor
from crypto_assistant.config import DB_PATH, INTERVAL, COINS

logger = logging.getLogger(__name__)

from crypto_assistant.api.state import LOG_FEED


def run():
    iteration = 0

    while True:
        start_time = time.time()
        try:
            prices = fetcher.fetch_prices()

            for price in prices:
                coin_id = price['coin_id']
                timestamp = price['timestamp']
                open_ = price['open']
                high = price['high']
                low = price['low']
                close = price['close']
                volume = price['volume']

                db.insert_price(DB_PATH, coin_id, timestamp, open_, high, low, close, volume)

                recent_prices = db.get_recent_prices(DB_PATH, coin_id, n=100)
                close_prices = [r['close'] for r in recent_prices]

                ind = indicators.compute_indicators(close_prices)

                if all(v is None for v in ind.values()):
                    logger.info("[%s] Not enough candles yet for indicators, skipping predict", coin_id)
                    continue

                db.insert_indicators(
                    DB_PATH,
                    coin_id,
                    timestamp,
                    ind['rsi'],
                    ind['macd'],
                    ind['macd_signal'],
                    ind['bb_upper'],
                    ind['bb_lower'],
                    ind['ema_20'],
                )

                features = {
                    'open': open_,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume,
                    'rsi': ind.get('rsi'),
                    'macd': ind.get('macd'),
                    'macd_signal': ind.get('macd_signal'),
                    'bb_upper': ind.get('bb_upper'),
                    'bb_lower': ind.get('bb_lower'),
                    'ema_20': ind.get('ema_20'),
                }

                direction, confidence = predictor.predict(features)
                db.insert_prediction(DB_PATH, coin_id, timestamp, direction, confidence)

                log_line = f"[{datetime.now().strftime('%H:%M:%S')}] {coin_id}: {direction} {confidence:.1%}"
                logging.info(log_line)
                LOG_FEED.append(log_line)
                if len(LOG_FEED) > 50:
                    LOG_FEED.pop(0)

            iteration += 1

            if iteration % 60 == 0:
                training_data = []
                for coin_id in COINS:
                    rows = db.get_training_data(DB_PATH, coin_id, n=200)
                    for i in range(len(rows) - 1):
                        row = dict(rows[i])
                        row['next_close'] = rows[i + 1]['close']
                        training_data.append(row)
                predictor.retrain_if_ready(training_data)

        except Exception as e:
            logging.exception(f"Error in main loop iteration: {e}")

        elapsed = time.time() - start_time
        sleep_time = max(0, INTERVAL - elapsed)
        time.sleep(sleep_time)
