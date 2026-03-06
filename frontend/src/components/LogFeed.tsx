import { useEffect, useRef } from 'react'
import { useLogFeed } from '../hooks/useWebSocket'

export function LogFeed() {
  const lines     = useLogFeed()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-accent text-sm font-semibold mb-3">Engine Log</h3>
      <div className="bg-[#010409] rounded p-3 h-48 overflow-y-auto font-mono text-xs text-up">
        {lines.length === 0
          ? <span className="text-muted">Waiting for engine data...</span>
          : lines.map((line, i) => <div key={i}>{line}</div>)
        }
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
