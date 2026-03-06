import type { KPI, Prediction, Price, Indicator, Assets } from '../types'

const BASE = '/api'

export async function fetchCoins(): Promise<string[]> {
  const res = await fetch(`${BASE}/coins`)
  return res.json()
}

export async function fetchAssets(): Promise<Assets> {
  try {
    const res = await fetch(`${BASE}/assets`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  } catch {
    return { crypto: [], stocks: [] }
  }
}

export async function fetchKPI(): Promise<KPI[]> {
  const res = await fetch(`${BASE}/kpi`)
  return res.json()
}

export async function fetchPrices(coinId: string, since = 0): Promise<Price[]> {
  const res = await fetch(`${BASE}/prices/${coinId}?since=${since}`)
  return res.json()
}

export async function fetchIndicators(coinId: string, since = 0): Promise<Indicator[]> {
  const res = await fetch(`${BASE}/indicators/${coinId}?since=${since}`)
  return res.json()
}

export async function fetchPredictions(coinId: string, n = 50): Promise<Prediction[]> {
  const res = await fetch(`${BASE}/predictions/${coinId}?n=${n}`)
  return res.json()
}
