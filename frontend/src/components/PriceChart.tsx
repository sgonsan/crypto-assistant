import { useEffect, useRef } from 'react'
import { createChart, ColorType } from 'lightweight-charts'
import type { Price } from '../types'

const CHART_BG   = '#161b22'
const GRID_COLOR = '#21262d'

export function PriceChart({ prices, coinId }: { prices: Price[]; coinId: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef     = useRef<ReturnType<typeof createChart> | null>(null)
  const seriesRef    = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART_BG },
        textColor: '#e6edf3',
      },
      grid: {
        vertLines: { color: GRID_COLOR },
        horzLines: { color: GRID_COLOR },
      },
      rightPriceScale: { borderColor: '#30363d' },
      timeScale: { borderColor: '#30363d', timeVisible: true },
      width: containerRef.current.clientWidth,
      height: 400,
    })

    const series = chart.addLineSeries({ color: '#58a6ff', lineWidth: 2 })
    chartRef.current = chart
    seriesRef.current = series

    const onResize = () => {
      if (containerRef.current)
        chart.applyOptions({ width: containerRef.current.clientWidth })
    }
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !prices.length) return
    seriesRef.current.setData(prices.map((p) => ({ time: p.timestamp, value: p.close })))
    chartRef.current?.timeScale().fitContent()
  }, [prices, coinId])

  return <div ref={containerRef} style={{ height: 400 }} />
}
