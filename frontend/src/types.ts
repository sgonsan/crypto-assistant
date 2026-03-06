export interface Price {
  id: number
  coin_id: string
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface Indicator {
  id: number
  coin_id: string
  timestamp: number
  rsi: number | null
  macd: number | null
  macd_signal: number | null
  bb_upper: number | null
  bb_lower: number | null
  ema_20: number | null
}

export interface Prediction {
  id: number
  coin_id: string
  timestamp: number
  predicted_direction: 'UP' | 'DOWN'
  confidence: number
  actual_direction: string | null
}

export interface KPI {
  coin_id: string
  current_price: number | null
  change_pct: number
  predicted_direction: string | null
  confidence: number
}

export interface Assets {
  crypto: string[]
  stocks: string[]
}
