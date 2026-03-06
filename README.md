# Crypto Assistant

Sistema de monitoreo y predicción de criptomonedas en tiempo real. Recoge precios cada 60 segundos desde CoinGecko, calcula indicadores técnicos, predice la dirección del precio con un modelo ML y expone todo vía una API REST + WebSocket consumida por un dashboard React.

---

## Estructura del proyecto

```text
stock-algorithm/
├── main.py                          ← Punto de entrada
├── crypto_assistant/
│   ├── config.py                    ← COINS, INTERVAL, DB_PATH, MODEL_PATH
│   ├── api/
│   │   ├── app.py                   ← FastAPI (REST + WebSocket)
│   │   └── state.py                 ← LOG_FEED compartido (lista en memoria)
│   ├── backfill.py                  ← Carga histórica inicial (1 año)
│   ├── db/
│   │   └── database.py              ← Todas las operaciones SQLite
│   ├── engine/
│   │   └── loop.py                  ← Bucle principal (cada 60 s)
│   ├── fetcher/
│   │   ├── coingecko.py             ← Precio actual en tiempo real
│   │   └── historical.py            ← Datos históricos OHLCV
│   ├── indicators/
│   │   └── technical.py             ← RSI, MACD, Bollinger Bands, EMA
│   └── predictor/
│       └── ml_model.py              ← RandomForest: train / predict / retrain
└── frontend/
    ├── src/
    │   ├── App.tsx                  ← Shell principal, estado global, polling
    │   ├── api/client.ts            ← fetch wrappers para todos los endpoints
    │   ├── hooks/useWebSocket.ts    ← WebSocket para log en tiempo real
    │   ├── types.ts                 ← Interfaces TypeScript (Price, Indicator…)
    │   └── components/
    │       ├── KPICards.tsx         ← Tarjetas de precio y predicción por moneda
    │       ├── PriceChart.tsx       ← Gráfico de línea (TradingView)
    │       ├── CandlestickChart.tsx ← Velas + RSI + MACD (3 paneles sincronizados)
    │       ├── PredictionHistory.tsx← Tabla de predicciones con resultado
    │       └── LogFeed.tsx          ← Terminal de log en tiempo real
    ├── package.json
    └── vite.config.ts               ← Dev proxy /api → :8000
```

---

## Instalación

```bash
# 1. Entorno virtual Python
python -m venv .venv
source .venv/bin/activate

# 2. Dependencias Python
pip install -r crypto_assistant/requirements.txt

# 3. Dependencias frontend
cd frontend && npm install && cd ..
```

**Dependencias Python:** `requests`, `pandas`, `numpy`, `scikit-learn`, `joblib`, `fastapi`, `uvicorn[standard]`

**Dependencias frontend:** `react 18`, `lightweight-charts 4`, `tailwindcss 3`, `typescript`, `vite`

---

## Ejecución

### Desarrollo (hot reload en frontend)

```bash
# Terminal 1 — backend + engine
python main.py

# Terminal 2 — frontend (Vite dev server)
cd frontend && npm run dev
```

- API: `http://localhost:8000`
- Dashboard: `http://localhost:5173` (proxied a :8000)

### Producción (un solo proceso)

```bash
cd frontend && npm run build   # genera frontend/dist/
python main.py                 # FastAPI sirve el dist estático en :8000
```

### Reiniciar sin Ctrl+C

Mientras la app está corriendo, escribe `r` + Enter en la terminal.

---

## Configuración

`crypto_assistant/config.py`

| Variable     | Valor por defecto                   | Descripción                    |
| ------------ | ----------------------------------- | ------------------------------ |
| `COINS`      | `["bitcoin", "ethereum", "solana"]` | IDs de CoinGecko a monitorear  |
| `INTERVAL`   | `60`                                | Segundos entre ciclos de fetch |
| `DB_PATH`    | `crypto_assistant/crypto.db`        | Base de datos SQLite           |
| `MODEL_PATH` | `crypto_assistant/model.pkl`        | Modelo serializado             |

Para añadir una moneda: agregar su ID de CoinGecko a `COINS` (ej. `"cardano"`).

---

## Flujo de datos

**Arranque (una sola vez):**

```text
init_db()  →  run_backfill()  →  predictor.train()  →  uvicorn (hilo)  →  engine.run()
```

**Ciclo del engine (cada 60 s):**

```text
CoinGecko /coins/{id}
    │
    ▼
fetcher.fetch_prices()          → OHLCV aproximado por moneda
    │
    ▼
db.insert_price()               → tabla prices
    │
    ▼
indicators.compute_indicators() → RSI(14), MACD(12,26,9), BB(20), EMA(20)
    │
    ▼
db.insert_indicators()          → tabla indicators
    │
    ▼
predictor.predict()             → ("UP"|"DOWN", confianza 0–1)
    │
    ▼
db.insert_prediction()          → tabla predictions
    │
    ▼
LOG_FEED.append()               → lista en memoria → WebSocket → frontend
```

Cada 50 iteraciones acumuladas se reentrenan el modelo con los últimos 200 candles por moneda.

---

## API

Servidor: `http://localhost:8000`

| Método | Ruta                         | Params                       | Respuesta                                                                 |
| ------ | ---------------------------- | ---------------------------- | ------------------------------------------------------------------------- |
| GET    | `/api/coins`                 | —                            | `string[]`                                                                |
| GET    | `/api/kpi`                   | —                            | `[{coin_id, current_price, change_pct, predicted_direction, confidence}]` |
| GET    | `/api/prices/{coin_id}`      | `since` (unix ts, default 0) | `Price[]`                                                                 |
| GET    | `/api/indicators/{coin_id}`  | `since` (unix ts, default 0) | `Indicator[]`                                                             |
| GET    | `/api/predictions/{coin_id}` | `n` (default 50)             | `Prediction[]`                                                            |
| WS     | `/api/ws/log`                | —                            | JSON array de strings (delta, push cada 1 s)                              |

En producción (con `frontend/dist/` presente), FastAPI también sirve el SPA React en todas las rutas no-API.

---

## Base de datos

SQLite en `crypto_assistant/crypto.db`. Índices únicos en `(coin_id, timestamp)` para `prices` e `indicators` — los inserts usan `INSERT OR IGNORE`, haciendo el backfill idempotente.

**`prices`**

| Columna                   | Tipo    | Descripción               |
| ------------------------- | ------- | ------------------------- |
| coin_id                   | TEXT    | ID de CoinGecko           |
| timestamp                 | INTEGER | Unix timestamp (segundos) |
| open / high / low / close | REAL    | Precios en USD            |
| volume                    | REAL    | Volumen 24 h en USD       |

**`indicators`**

| Columna             | Tipo | Descripción                   |
| ------------------- | ---- | ----------------------------- |
| rsi                 | REAL | RSI(14) — NULL si <26 candles |
| macd                | REAL | EMA(12) − EMA(26)             |
| macd_signal         | REAL | EMA(9) del MACD               |
| bb_upper / bb_lower | REAL | SMA(20) ± 2σ                  |
| ema_20              | REAL | EMA(20)                       |

**`predictions`**

| Columna             | Tipo | Descripción                |
| ------------------- | ---- | -------------------------- |
| predicted_direction | TEXT | `"UP"` o `"DOWN"`          |
| confidence          | REAL | Probabilidad [0, 1]        |
| actual_direction    | TEXT | NULL hasta backfill manual |

---

## Modelo ML

- **Algoritmo:** `RandomForestClassifier` (scikit-learn, parámetros por defecto)
- **Label:** `1` (UP) si `next_close > close`, `0` (DOWN) en caso contrario
- **Features (6):**

| Feature        | Fórmula                                      |
| -------------- | -------------------------------------------- |
| `rsi`          | RSI(14)                                      |
| `macd`         | Línea MACD                                   |
| `macd_signal`  | Señal MACD                                   |
| `bb_position`  | `(close − bb_lower) / (bb_upper − bb_lower)` |
| `ema_distance` | `(close − ema_20) / ema_20`                  |
| `volume_delta` | `volume / prev_volume − 1`                   |

- **Entrenamiento inicial:** al arrancar, si hay datos en DB con indicadores válidos
- **Reentrenamiento:** automático cuando `_samples_since_last_train >= 50`
- **Mínimo:** 10 muestras válidas para entrenar; si no se cumple, se omite
- **Cold-start:** si no hay modelo en disco, devuelve `("UP", 0.5)`
- **Persistencia:** `model.pkl` vía `joblib`

---

## Fetcher y backfill

### Fetcher en tiempo real (`fetcher/coingecko.py`)

- Endpoint: `GET /api/v3/coins/{coin_id}` con `market_data=true`
- OHLCV aproximado: open = `current_price − price_change_24h`, high/low = 24 h de CoinGecko, close = precio actual
- 2.5 s entre monedas; reintentos ante HTTP 429 (30 s y 60 s)

### Fetcher histórico (`fetcher/historical.py`)

- Endpoint: `GET /api/v3/coins/{coin_id}/market_chart`
- CoinGecko auto-granula: `days > 90` → diario, `days ≤ 90` → horario
- OHLCV aproximado: open = close anterior, high/low = max/min(open, close)

### Backfill (`backfill.py`)

Se ejecuta en cada arranque; omite la moneda si ya tiene datos con más de 30 días de antigüedad.

| Tier | Petición   | Granularidad                           | Rango guardado               |
| ---- | ---------- | -------------------------------------- | ---------------------------- |
| 1    | `days=365` | Diario                                 | 1 año atrás → 1 mes atrás    |
| 2    | `days=30`  | Cada 6 h (1 de cada 6 puntos horarios) | 1 mes atrás → 1 semana atrás |
| 3    | `days=7`   | Horario                                | Última semana                |

Sleeps: 8 s entre llamadas, 12 s entre monedas.

---

## Indicadores técnicos

Dos funciones en `indicators/technical.py`:

| Función                             | Uso                       | Comportamiento                                                                    |
| ----------------------------------- | ------------------------- | --------------------------------------------------------------------------------- |
| `compute_indicators(prices)`        | Engine loop (tiempo real) | Calcula solo el último valor; requiere ≥26 precios; devuelve `None` en todo si no |
| `compute_indicators_series(closes)` | Backfill (batch)          | Vectorizado sobre toda la serie; primeros 25 valores son `None`                   |

Indicadores calculados: **RSI(14)**, **MACD(12, 26, 9)**, **Bollinger Bands SMA(20) ±2σ**, **EMA(20)**.

---

## Limitaciones conocidas

- Los candles no son de intervalo fijo: cada registro es una foto del precio en el momento del fetch cada 60 s.
- El OHLCV en tiempo real usa high/low de 24 h de CoinGecko, no del intervalo de 60 s.
- `actual_direction` en predicciones siempre es NULL (no hay job automático que lo rellene).
- El modelo arranca en frío: primeras predicciones devuelven `("UP", 0.5)` hasta tener ≥10 muestras con indicadores válidos.
- La API pública de CoinGecko tiene rate limit (~10–50 req/min). El backfill puede tardar varios minutos en el primer arranque.
