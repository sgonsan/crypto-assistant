import type { Prediction } from '../types'

function resultStyle(pred: string, actual: string | null) {
  if (!actual) return 'text-muted'
  return pred === actual ? 'text-up' : 'text-down'
}

export function PredictionHistory({
  predictions,
  coinId,
}: {
  predictions: Prediction[]
  coinId: string
}) {
  if (!predictions.length) {
    return (
      <div className="text-muted text-center py-16 text-sm">
        No predictions yet for {coinId.toUpperCase()}
      </div>
    )
  }

  const rows = [...predictions].reverse()

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-center">
        <thead>
          <tr className="border-b border-border text-accent">
            {['Time', 'Predicted', 'Actual', 'Confidence', 'Result'].map((h) => (
              <th key={h} className="pb-2 font-semibold">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id} className="border-b border-border/30 hover:bg-white/5 transition-colors">
              <td className="py-2 text-muted text-xs">
                {new Date(p.timestamp * 1000).toLocaleString()}
              </td>
              <td className={`py-2 font-semibold ${p.predicted_direction === 'UP' ? 'text-up' : 'text-down'}`}>
                {p.predicted_direction} {p.predicted_direction === 'UP' ? '▲' : '▼'}
              </td>
              <td className="py-2 text-muted">{p.actual_direction ?? '—'}</td>
              <td className="py-2">{(p.confidence * 100).toFixed(1)}%</td>
              <td className={`py-2 font-bold ${resultStyle(p.predicted_direction, p.actual_direction)}`}>
                {p.actual_direction
                  ? p.predicted_direction === p.actual_direction ? '✓' : '✗'
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
