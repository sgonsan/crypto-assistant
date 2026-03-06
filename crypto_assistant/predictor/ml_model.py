import logging

import joblib
from sklearn.ensemble import RandomForestClassifier

from crypto_assistant.config import MODEL_PATH

logger = logging.getLogger(__name__)

_model = None
_samples_since_last_train = 0
RETRAIN_THRESHOLD = 50


def train(data: list[dict]) -> None:
    """
    Train RandomForestClassifier on historical data.
    data: list of dicts, each with keys:
      rsi, macd, macd_signal, bb_upper, bb_lower, ema_20,
      close, volume, next_close (float or None)
    Only use rows where next_close is not None.
    Label: 1 if next_close > close, 0 otherwise.
    Features: [rsi, macd, macd_signal, bb_position, ema_distance, volume_delta]
      - bb_position = (close - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) != 0 else 0.5
      - ema_distance = (close - ema_20) / ema_20 if ema_20 != 0 else 0.0
      - volume_delta = volume / prev_volume - 1 (use 0.0 for first row)
    Skips rows with None in any feature field.
    If < 10 valid training samples, logs warning and returns without training.
    Saves model to MODEL_PATH with joblib.dump().
    Sets global _model.
    Resets _samples_since_last_train = 0.
    """
    global _model, _samples_since_last_train

    X: list[list[float]] = []
    y: list[int] = []
    prev_volume: float | None = None

    for row in data:
        if row.get("next_close") is None:
            prev_volume = row.get("volume")
            continue

        rsi = row.get("rsi")
        macd = row.get("macd")
        macd_signal = row.get("macd_signal")
        bb_upper = row.get("bb_upper")
        bb_lower = row.get("bb_lower")
        ema_20 = row.get("ema_20")
        close = row.get("close")
        volume = row.get("volume")
        next_close = row.get("next_close")

        if any(v is None for v in [rsi, macd, macd_signal, bb_upper, bb_lower, ema_20, close, volume]):
            prev_volume = volume
            continue

        bb_range = bb_upper - bb_lower
        bb_position = (close - bb_lower) / bb_range if bb_range != 0 else 0.5

        ema_distance = (close - ema_20) / ema_20 if ema_20 != 0 else 0.0

        volume_delta = (volume / prev_volume - 1) if prev_volume is not None and prev_volume != 0 else 0.0

        label = 1 if next_close > close else 0

        X.append([rsi, macd, macd_signal, bb_position, ema_distance, volume_delta])
        y.append(label)

        prev_volume = volume

    if len(X) < 10:
        logger.warning(
            "Not enough valid training samples (%d). Need at least 10. Skipping training.", len(X)
        )
        return

    model = RandomForestClassifier()
    model.fit(X, y)

    joblib.dump(model, MODEL_PATH)
    logger.info("Model trained on %d samples and saved to %s.", len(X), MODEL_PATH)

    _model = model
    _samples_since_last_train = 0


def predict(features: dict) -> tuple[str, float]:
    """
    features: dict with keys rsi, macd, macd_signal, bb_upper, bb_lower, ema_20, close, volume
    Returns (direction: "UP" or "DOWN", confidence: float 0-1).
    If model not loaded, tries to load from MODEL_PATH.
    If model still not available, returns ("UP", 0.5) as default.
    """
    global _model

    if _model is None:
        try:
            _model = joblib.load(MODEL_PATH)
            logger.info("Model loaded from %s.", MODEL_PATH)
        except Exception as e:
            logger.warning("Could not load model from %s: %s. Returning default prediction.", MODEL_PATH, e)
            return ("UP", 0.5)

    rsi = features.get("rsi", 0.0)
    macd = features.get("macd", 0.0)
    macd_signal = features.get("macd_signal", 0.0)
    bb_upper = features.get("bb_upper", 0.0)
    bb_lower = features.get("bb_lower", 0.0)
    ema_20 = features.get("ema_20", 0.0)
    close = features.get("close", 0.0)
    volume = features.get("volume", 0.0)

    required = [rsi, macd, macd_signal, bb_upper, bb_lower, ema_20]
    if any(v is None for v in required):
        return ("UP", 0.5)

    bb_range = bb_upper - bb_lower
    bb_position = (close - bb_lower) / bb_range if bb_range != 0 else 0.5
    ema_distance = (close - ema_20) / ema_20 if ema_20 != 0 else 0.0

    feature_vector = [[rsi, macd, macd_signal, bb_position, ema_distance, volume]]

    proba = _model.predict_proba(feature_vector)[0]
    classes = list(_model.classes_)

    up_index = classes.index(1) if 1 in classes else None
    down_index = classes.index(0) if 0 in classes else None

    if up_index is not None and down_index is not None:
        if proba[up_index] >= proba[down_index]:
            return ("UP", float(proba[up_index]))
        else:
            return ("DOWN", float(proba[down_index]))
    elif up_index is not None:
        return ("UP", float(proba[up_index]))
    elif down_index is not None:
        return ("DOWN", float(proba[down_index]))
    else:
        return ("UP", 0.5)


def retrain_if_ready(data: list[dict]) -> None:
    """
    Increments _samples_since_last_train by len(data).
    If _samples_since_last_train >= RETRAIN_THRESHOLD, calls train(data).
    """
    global _samples_since_last_train

    _samples_since_last_train += len(data)

    if _samples_since_last_train >= RETRAIN_THRESHOLD:
        logger.info(
            "_samples_since_last_train=%d >= RETRAIN_THRESHOLD=%d. Retraining.",
            _samples_since_last_train,
            RETRAIN_THRESHOLD,
        )
        train(data)
