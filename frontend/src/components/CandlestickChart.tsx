import { useEffect, useRef } from 'react'
import { createChart, ColorType, CrosshairMode, LineStyle } from 'lightweight-charts'
import type { Price, Indicator } from '../types'

const CHART_BG   = '#161b22'
const GRID_COLOR = '#21262d'
const BORDER     = '#30363d'

function makeChart(el: HTMLElement, height: number) {
  return createChart(el, {
    layout: {
      background: { type: ColorType.Solid, color: CHART_BG },
      textColor: '#e6edf3',
    },
    grid: {
      vertLines: { color: GRID_COLOR },
      horzLines: { color: GRID_COLOR },
    },
    crosshair: { mode: CrosshairMode.Normal },
    rightPriceScale: { borderColor: BORDER },
    timeScale: { borderColor: BORDER, timeVisible: true },
    width: el.clientWidth,
    height,
  })
}

export function CandlestickChart({
  prices,
  indicators,
  coinId,
}: {
  prices: Price[]
  indicators: Indicator[]
  coinId: string
}) {
  const mainRef = useRef<HTMLDivElement>(null)
  const rsiRef  = useRef<HTMLDivElement>(null)
  const macdRef = useRef<HTMLDivElement>(null)

  const chartsRef = useRef<{
    main: ReturnType<typeof createChart>
    rsi:  ReturnType<typeof createChart>
    macd: ReturnType<typeof createChart>
  } | null>(null)

  const seriesRef = useRef<{
    candle:     any
    ema:        any
    bbUpper:    any
    bbLower:    any
    rsi:        any
    macdHist:   any
    macdSignal: any
  } | null>(null)

  // Initialise charts once
  useEffect(() => {
    if (!mainRef.current || !rsiRef.current || !macdRef.current) return

    const main = makeChart(mainRef.current, 420)
    const rsi  = makeChart(rsiRef.current,  140)
    const macd = makeChart(macdRef.current, 140)

    // ── Main chart series ────────────────────────────────────────────────────
    const candle = main.addCandlestickSeries({
      upColor:        '#3fb950', downColor:   '#f85149',
      borderUpColor:  '#3fb950', borderDownColor: '#f85149',
      wickUpColor:    '#3fb950', wickDownColor:   '#f85149',
    })
    const ema = main.addLineSeries({
      color: '#58a6ff', lineWidth: 1, title: 'EMA20',
    })
    const bbUpper = main.addLineSeries({
      color: '#d29922', lineWidth: 1, lineStyle: LineStyle.Dashed, title: 'BB Upper',
    })
    const bbLower = main.addLineSeries({
      color: '#d29922', lineWidth: 1, lineStyle: LineStyle.Dashed, title: 'BB Lower',
    })

    // ── RSI chart ────────────────────────────────────────────────────────────
    const rsiSeries = rsi.addLineSeries({ color: '#ff7b72', lineWidth: 1, title: 'RSI' })
    rsi.addLineSeries({ color: '#f85149', lineWidth: 1, lineStyle: LineStyle.Dashed }).setData(
      Array.from({ length: 2 }, (_, i) => ({ time: i + 1 as any, value: 70 }))
    )
    rsi.addLineSeries({ color: '#3fb950', lineWidth: 1, lineStyle: LineStyle.Dashed }).setData(
      Array.from({ length: 2 }, (_, i) => ({ time: i + 1 as any, value: 30 }))
    )

    // ── MACD chart ───────────────────────────────────────────────────────────
    const macdHist   = macd.addHistogramSeries({ title: 'MACD Hist' })
    const macdSignal = macd.addLineSeries({ color: '#d29922', lineWidth: 1, title: 'Signal' })

    chartsRef.current = { main, rsi, macd }
    seriesRef.current = { candle, ema, bbUpper, bbLower, rsi: rsiSeries, macdHist, macdSignal }

    // Sync visible range across all three charts
    const sync = (source: any, targets: any[]) =>
      source.timeScale().subscribeVisibleLogicalRangeChange((range: any) => {
        if (range) targets.forEach((t) => t.timeScale().setVisibleLogicalRange(range))
      })
    sync(main, [rsi, macd])
    sync(rsi,  [main, macd])
    sync(macd, [main, rsi])

    const onResize = () => {
      const w = mainRef.current?.clientWidth ?? 0
      main.applyOptions({ width: w })
      rsi.applyOptions({ width: w })
      macd.applyOptions({ width: w })
    }
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      main.remove()
      rsi.remove()
      macd.remove()
    }
  }, [])

  // Update data when props change
  useEffect(() => {
    const s = seriesRef.current
    if (!s || !prices.length) return

    s.candle.setData(
      prices.map((p) => ({ time: p.timestamp, open: p.open, high: p.high, low: p.low, close: p.close }))
    )

    const withEma = indicators.filter((i) => i.ema_20 !== null)
    if (withEma.length) {
      s.ema.setData(withEma.map((i) => ({ time: i.timestamp, value: i.ema_20! })))
      s.bbUpper.setData(withEma.filter((i) => i.bb_upper !== null).map((i) => ({ time: i.timestamp, value: i.bb_upper! })))
      s.bbLower.setData(withEma.filter((i) => i.bb_lower !== null).map((i) => ({ time: i.timestamp, value: i.bb_lower! })))
    }

    const withRsi = indicators.filter((i) => i.rsi !== null)
    if (withRsi.length)
      s.rsi.setData(withRsi.map((i) => ({ time: i.timestamp, value: i.rsi! })))

    const withMacd = indicators.filter((i) => i.macd !== null && i.macd_signal !== null)
    if (withMacd.length) {
      s.macdHist.setData(
        withMacd.map((i) => ({
          time:  i.timestamp,
          value: i.macd! - i.macd_signal!,
          color: i.macd! - i.macd_signal! >= 0 ? '#3fb950' : '#f85149',
        }))
      )
      s.macdSignal.setData(withMacd.map((i) => ({ time: i.timestamp, value: i.macd_signal! })))
    }

    chartsRef.current?.main.timeScale().fitContent()
  }, [prices, indicators, coinId])

  return (
    <div className="space-y-0">
      <div className="text-muted text-xs px-1 pb-0.5">{coinId.toUpperCase()} · OHLCV · EMA20 · Bollinger Bands</div>
      <div ref={mainRef} />
      <div className="text-muted text-xs px-1 pt-1 pb-0.5">RSI (14)</div>
      <div ref={rsiRef} />
      <div className="text-muted text-xs px-1 pt-1 pb-0.5">MACD (12, 26, 9)</div>
      <div ref={macdRef} />
    </div>
  )
}
