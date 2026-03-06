# Market Assistant

Sistema de monitoreo y predicción de activos financieros en tiempo real. Recoge precios cada 60 segundos desde CoinGecko (criptomonedas) y Yahoo Finance (acciones), calcula indicadores técnicos, predice la dirección del precio con un modelo ML y expone todo vía una API REST + WebSocket consumida por un dashboard React.

---

## Estructura del proyecto

```text
crypto-assistant/
├── main.py                          ← Punto de entrada
├── crypto_assistant/
│   ├── config.py                    ← COINS, STOCKS, INTERVAL, DB_PATH, MODEL_PATH
│   ├── api/
│   │   ├── app.py                   ← FastAPI (REST + WebSocket)
│   │   └── state.py                 ← LOG_FEED compartido (lista en memoria)
│   ├── backfill.py                  ← Carga histórica inicial (crypto + stocks)
│   ├── db/
│   │   └── database.py              ← Todas las operaciones SQLite
│   ├── engine/
│   │   └── loop.py                  ← Bucle principal (cada 60 s)
│   ├── fetcher/
│   │   ├── coingecko.py             ← Precio actual en tiempo real (crypto)
│   │   ├── historical.py            ← Datos históricos OHLCV (CoinGecko)
│   │   ├── yfinance_fetcher.py      ← Precio actual en tiempo real (acciones, Yahoo Finance v8)
│   │   └── historical_stocks.py    ← Datos históricos OHLCV (acciones, Yahoo Finance v8)
│   ├── indicators/
│   │   └── technical.py             ← RSI, MACD, Bollinger Bands, EMA
│   └── predictor/
│       └── ml_model.py              ← RandomForest: train / predict / retrain
└── frontend/
    ├── src/
    │   ├── App.tsx                  ← Shell principal, toggle Crypto/Stocks, estado global, polling
    │   ├── api/client.ts            ← fetch wrappers para todos los endpoints
    │   ├── hooks/useWebSocket.ts    ← WebSocket para log en tiempo real
    │   ├── types.ts                 ← Interfaces TypeScript (Price, Indicator, Assets…)
    │   └── components/
    │       ├── KPICards.tsx         ← Tarjetas de precio y predicción por activo
    │       ├── PriceChart.tsx       ← Gráfico de línea (lightweight-charts)
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

No se requiere ninguna clave de API: CoinGecko pública y Yahoo Finance v8 son de acceso libre.

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

### Servicio systemd

En producción la app se despliega como servicio systemd (`crypto-assistant.service`), lo que permite el arranque automático con el sistema y la supervivencia ante desconexiones SSH.

---

## Configuración

`crypto_assistant/config.py`

| Variable     | Valor por defecto                                              | Descripción                              |
| ------------ | -------------------------------------------------------------- | ---------------------------------------- |
| `COINS`      | `["bitcoin", "ethereum", "ripple", ...]` (10 monedas)         | IDs de CoinGecko a monitorear            |
| `STOCKS`     | `["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "SPY"]` | Tickers de Yahoo Finance a monitorear    |
| `INTERVAL`   | `60`                                                           | Segundos entre ciclos de fetch           |
| `DB_PATH`    | `crypto_assistant/crypto.db`                                   | Base de datos SQLite                     |
| `MODEL_PATH` | `crypto_assistant/model.pkl`                                   | Modelo serializado                       |

Para añadir una criptomoneda: agregar su ID de CoinGecko a `COINS` (ej. `"cardano"`).

Para añadir una acción: agregar su ticker de Yahoo Finance a `STOCKS` (ej. `"MSFT"`).

---

## Flujo de datos

**Arranque (una sola vez):**

```text
init_db()  →  run_backfill() [crypto + stocks]  →  predictor.train()  →  uvicorn (hilo)  →  engine.run()
```

**Ciclo del engine (cada 60 s):**

```text
CoinGecko /api/v3/coins/{id}          Yahoo Finance v8 /chart/{symbol}
         │                                          │
         ▼                                          ▼
fetcher.fetch_prices()           fetcher.fetch_stock_prices()
         │                                          │
         └──────────────┬─────────────────────────-┘
                        ▼
              db.insert_price()              → tabla prices
                        │
                        ▼
         indicators.compute_indicators()    → RSI(14), MACD(12,26,9), BB(20), EMA(20)
                        │
                        ▼
              db.insert_indicators()        → tabla indicators
                        │
                        ▼
              predictor.predict()           → ("UP"|"DOWN", confianza 0–1)
                        │
                        ▼
              db.insert_prediction()        → tabla predictions
                        │
                        ▼
              LOG_FEED.append()             → lista en memoria → WebSocket → frontend
```

Cada 50 iteraciones acumuladas se reentrena el modelo con los últimos 200 candles por activo.

---

## API

Servidor: `http://localhost:8000`

| Método | Ruta                         | Params                       | Respuesta                                                                 |
| ------ | ---------------------------- | ---------------------------- | ------------------------------------------------------------------------- |
| GET    | `/api/assets`                | —                            | `{"crypto": string[], "stocks": string[]}`                                |
| GET    | `/api/coins`                 | —                            | `string[]` (crypto + stocks combinados)                                   |
| GET    | `/api/kpi`                   | —                            | `[{coin_id, current_price, change_pct, predicted_direction, confidence}]` |
| GET    | `/api/prices/{coin_id}`      | `since` (unix ts, default 0) | `Price[]`                                                                 |
| GET    | `/api/indicators/{coin_id}`  | `since` (unix ts, default 0) | `Indicator[]`                                                             |
| GET    | `/api/predictions/{coin_id}` | `n` (default 50)             | `Prediction[]`                                                            |
| WS     | `/api/ws/log`                | —                            | JSON array de strings (delta, push cada 1 s)                              |

En producción (con `frontend/dist/` presente), FastAPI también sirve el SPA React en todas las rutas no-API.

---

## Base de datos

SQLite en `crypto_assistant/crypto.db`. El campo `coin_id` es TEXT genérico y acepta tanto IDs de CoinGecko (`"bitcoin"`) como tickers de Yahoo Finance (`"AAPL"`). Índices únicos en `(coin_id, timestamp)` para `prices` e `indicators` — los inserts usan `INSERT OR IGNORE`, haciendo el backfill idempotente.

**`prices`**

| Columna                   | Tipo    | Descripción                        |
| ------------------------- | ------- | ---------------------------------- |
| coin_id                   | TEXT    | ID de CoinGecko o ticker de bolsa  |
| timestamp                 | INTEGER | Unix timestamp (segundos)          |
| open / high / low / close | REAL    | Precios en USD                     |
| volume                    | REAL    | Volumen en USD (crypto: 24 h)      |

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

- **Entrenamiento inicial:** al arrancar, si hay datos en DB con indicadores válidos (solo con datos de `COINS`)
- **Reentrenamiento:** automático cuando `_samples_since_last_train >= 50`
- **Mínimo:** 10 muestras válidas para entrenar; si no se cumple, se omite
- **Cold-start:** si no hay modelo en disco, devuelve `("UP", 0.5)`
- **Persistencia:** `model.pkl` vía `joblib`

---

## Fetchers y backfill

### Fetcher en tiempo real — crypto (`fetcher/coingecko.py`)

- Endpoint: `GET /api/v3/coins/{coin_id}` con `market_data=true`
- OHLCV aproximado: open = `current_price − price_change_24h`, high/low = máximos/mínimos 24 h de CoinGecko, close = precio actual
- 2.5 s entre monedas; reintentos ante HTTP 429 (30 s y 60 s)

### Fetcher en tiempo real — acciones (`fetcher/yfinance_fetcher.py`)

- Endpoint: `GET https://query1.finance.yahoo.com/v8/finance/chart/{symbol}` con `interval=5m&range=1d`
- Devuelve el último bar completo de 5 minutos disponible
- No requiere clave de API; acceso público a `query1.finance.yahoo.com`
- 1 s entre peticiones; los errores de un ticker se omiten sin detener el ciclo

### Fetcher histórico — crypto (`fetcher/historical.py`)

- Endpoint: `GET /api/v3/coins/{coin_id}/market_chart`
- CoinGecko auto-granula: `days > 90` → diario, `days ≤ 90` → horario
- OHLCV aproximado: open = close anterior, high/low = max/min(open, close)

### Fetcher histórico — acciones (`fetcher/historical_stocks.py`)

- Endpoint: `GET https://query1.finance.yahoo.com/v8/finance/chart/{symbol}`
- Soporta `interval` (`1h`, `1d`, etc.) y `range` (`730d`, `5y`, etc.)
- Reintentos ante HTTP 429 (30 s, 60 s, 90 s); 3 intentos máximo
- Las barras con datos incompletos (open/high/low/close nulos) se descartan automáticamente

### Backfill (`backfill.py`)

Se ejecuta en cada arranque; omite el activo si ya tiene datos con más de 30 días de antigüedad.

**Crypto (CoinGecko):**

| Tier | Petición   | Granularidad                           | Rango guardado               |
| ---- | ---------- | -------------------------------------- | ---------------------------- |
| 1    | `days=365` | Diario                                 | 1 año atrás → 1 mes atrás    |
| 2    | `days=30`  | Cada 6 h (1 de cada 6 puntos horarios) | 1 mes atrás → 1 semana atrás |
| 3    | `days=7`   | Horario                                | Última semana                |

Sleeps: 8 s entre llamadas, 12 s entre monedas.

**Acciones (Yahoo Finance v8):**

| Tier | Petición              | Granularidad | Rango guardado                 |
| ---- | --------------------- | ------------ | ------------------------------ |
| 1    | `interval=1d, range=5y`   | Diario   | Más de 2 años atrás (~1255 barras) |
| 2    | `interval=1h, range=730d` | Horario  | Últimos 2 años (~5000 barras)  |

Sleeps: 2 s entre llamadas, 5 s entre tickers.

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

- Los candles de crypto no son de intervalo fijo: cada registro es una foto del precio en el momento del fetch cada 60 s.
- El OHLCV en tiempo real para crypto usa high/low de 24 h de CoinGecko, no del intervalo de 60 s.
- Los datos en tiempo real de acciones se actualizan con granularidad de 5 minutos (un bar por ventana de 5 min). El engine puede ejecutarse cada 60 s pero solo obtendrá un nuevo precio cada 5 minutos.
- Fuera del horario de mercado (lunes–viernes 9:30–16:00 hora del Este) Yahoo Finance devuelve el último bar disponible; no se generan datos nuevos.
- El histórico intraday de Yahoo Finance v8 con `interval=1h` está disponible hasta aproximadamente 730 días atrás.
- `actual_direction` en predicciones siempre es NULL (no hay job automático que lo rellene).
- El modelo arranca en frío: las primeras predicciones devuelven `("UP", 0.5)` hasta tener ≥10 muestras con indicadores válidos.
- La API pública de CoinGecko tiene rate limit (~10–50 req/min). El backfill puede tardar varios minutos en el primer arranque.
