import type { KPI, Prediction, Price, Indicator } from '../types'

const BASE = '/api'

export async function fetchCoins(): Promise<string[]> {
  const res = await fetch(`${BASE}/coins`)
  return res.json()
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
