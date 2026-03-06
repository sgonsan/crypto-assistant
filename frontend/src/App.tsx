import { useState, useEffect, useCallback } from 'react'
import { fetchCoins, fetchKPI, fetchPrices, fetchIndicators, fetchPredictions } from './api/client'
import { KPICards }          from './components/KPICards'
import { PriceChart }        from './components/PriceChart'
import { CandlestickChart }  from './components/CandlestickChart'
import { PredictionHistory } from './components/PredictionHistory'
import { LogFeed }           from './components/LogFeed'
import type { KPI, Price, Indicator, Prediction } from './types'

const TABS = ['Live Price', 'Candlestick', 'Predictions'] as const
type Tab = (typeof TABS)[number]

const POLL_MS = 10_000

const RANGES: { label: string; seconds: number }[] = [
  { label: '24h', seconds: 86_400 },
  { label: '7d',  seconds: 604_800 },
  { label: '30d', seconds: 2_592_000 },
]

export default function App() {
  const [coins,        setCoins]        = useState<string[]>([])
  const [selectedCoin, setSelectedCoin] = useState<string>('')
  const [kpi,          setKpi]          = useState<KPI[]>([])
  const [prices,       setPrices]       = useState<Price[]>([])
  const [indicators,   setIndicators]   = useState<Indicator[]>([])
  const [predictions,  setPredictions]  = useState<Prediction[]>([])
  const [activeTab,    setActiveTab]    = useState<Tab>('Live Price')
  const [rangeSeconds, setRangeSeconds] = useState(604_800)
  const [lastUpdate,   setLastUpdate]   = useState('')

  // Load coin list once
  useEffect(() => {
    fetchCoins().then((c) => {
      setCoins(c)
      if (c.length > 0) setSelectedCoin(c[0])
    })
  }, [])

  const refresh = useCallback(async () => {
    if (!selectedCoin) return
    const since = Math.floor(Date.now() / 1000) - rangeSeconds
    const [kpiData, priceData, indData, predData] = await Promise.all([
      fetchKPI(),
      fetchPrices(selectedCoin, since),
      fetchIndicators(selectedCoin, since),
      fetchPredictions(selectedCoin),
    ])
    setKpi(kpiData)
    setPrices(priceData)
    setIndicators(indData)
    setPredictions(predData)
    setLastUpdate(new Date().toLocaleTimeString())
  }, [selectedCoin, rangeSeconds])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  return (
    <div className="min-h-screen bg-bg text-text">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="bg-card border-b border-border px-6 py-3 flex items-center gap-4 sticky top-0 z-10">
        <span className="text-xl font-bold text-accent">Crypto Assistant</span>

        <select
          value={selectedCoin}
          onChange={(e) => setSelectedCoin(e.target.value)}
          className="bg-bg border border-border text-text rounded px-3 py-1.5 text-sm focus:outline-none focus:border-accent"
        >
          {coins.map((c) => (
            <option key={c} value={c}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>

        <div className="ml-auto flex items-center gap-3">
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r.label}
                onClick={() => setRangeSeconds(r.seconds)}
                className={`px-2.5 py-1 text-xs rounded transition-colors ${
                  rangeSeconds === r.seconds
                    ? 'bg-accent text-white'
                    : 'text-muted hover:text-text border border-border'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
          <span className="text-muted text-xs">
            {lastUpdate ? `Updated ${lastUpdate}` : 'Loading…'}
          </span>
        </div>
      </header>

      <main className="p-4 space-y-4 max-w-screen-2xl mx-auto">

        {/* ── KPI Cards ───────────────────────────────────────────────────── */}
        <KPICards kpi={kpi} />

        {/* ── Tabbed Charts ───────────────────────────────────────────────── */}
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="flex border-b border-border">
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-3 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? 'text-accent border-b-2 border-accent -mb-px'
                    : 'text-muted hover:text-text'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="p-4">
            {activeTab === 'Live Price'   && <PriceChart prices={prices} coinId={selectedCoin} />}
            {activeTab === 'Candlestick'  && <CandlestickChart prices={prices} indicators={indicators} coinId={selectedCoin} />}
            {activeTab === 'Predictions'  && <PredictionHistory predictions={predictions} coinId={selectedCoin} />}
          </div>
        </div>

        {/* ── Log Feed ────────────────────────────────────────────────────── */}
        <LogFeed />

      </main>
    </div>
  )
}
