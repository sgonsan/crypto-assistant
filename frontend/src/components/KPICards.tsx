import type { KPI } from '../types'

const COIN_COLORS = ['#58a6ff', '#f0883e', '#bc8cff', '#3fb950', '#ff7b72']

function directionColor(direction: string | null, confidence: number): string {
  if (!direction) return '#8b949e'
  if (direction === 'UP' && confidence > 0.65) return '#3fb950'
  if (direction === 'DOWN') return '#f85149'
  return '#d29922'
}

const formatAssetName = (id: string) =>
  id === id.toUpperCase() ? id : id.charAt(0).toUpperCase() + id.slice(1)

export function KPICards({ kpi }: { kpi: KPI[] }) {
  return (
    <div className="flex gap-3 flex-wrap">
      {kpi.map((k, i) => {
        const accent   = COIN_COLORS[i % COIN_COLORS.length]
        const dirColor = directionColor(k.predicted_direction, k.confidence)
        const up       = k.change_pct >= 0

        return (
          <div
            key={k.coin_id}
            className="flex-1 min-w-[200px] bg-card border border-border rounded-lg p-4"
            style={{ borderTop: `3px solid ${accent}` }}
          >
            <h4 className="font-semibold mb-2" style={{ color: accent }}>
              {formatAssetName(k.coin_id)}
            </h4>

            <div className="text-2xl font-bold mb-1">
              {k.current_price != null
                ? `$${k.current_price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : '—'}
            </div>

            <div className={`text-sm mb-2 ${up ? 'text-up' : 'text-down'}`}>
              {up ? '▲' : '▼'} {Math.abs(k.change_pct).toFixed(2)}% (24h)
            </div>

            <div className="text-sm flex items-center gap-2">
              <span className="font-semibold" style={{ color: dirColor }}>
                {k.predicted_direction
                  ? `${k.predicted_direction} ${k.predicted_direction === 'UP' ? '▲' : '▼'}`
                  : '—'}
              </span>
              <span className="text-muted">{(k.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
