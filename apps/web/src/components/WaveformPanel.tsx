/**
 * Waveform viewer: one digital signal row per traced signal, one column per clock
 * cycle. Values render as text-bearing levels — 0 low, 1 high, X mid-band (never
 * color alone), Z flat gray. Deterministic engine output in, picture out.
 */

import { useState } from 'react'

import type { SequentialResult } from '../types'

interface WaveformPanelProps {
  result: SequentialResult | null
}

interface SignalStats {
  transitions: number
  rising: number
  falling: number
  ones: number
}

function analyze(values: string[]): SignalStats {
  let transitions = 0
  let rising = 0
  let falling = 0
  let ones = 0
  for (let i = 0; i < values.length; i += 1) {
    if (values[i] === '1') ones += 1
    if (i > 0 && values[i] !== values[i - 1]) {
      transitions += 1
      if (values[i - 1] === '0' && values[i] === '1') rising += 1
      if (values[i - 1] === '1' && values[i] === '0') falling += 1
    }
  }
  return { transitions, rising, falling, ones }
}

const ROW_H = 30
const COL_W = 36
const LABEL_W = 130
const TOP_PAD = 24

function levelY(value: string, rowTop: number): number {
  if (value === '1') return rowTop + 5
  if (value === '0') return rowTop + ROW_H - 6
  return rowTop + ROW_H / 2 // X / Z mid-band
}

function signalPath(values: string[], rowTop: number): { path: string; xs: number[] } {
  let path = ''
  const xs: number[] = []
  for (let i = 0; i < values.length; i += 1) {
    const x1 = i * COL_W
    const x2 = (i + 1) * COL_W
    const y = levelY(values[i], rowTop)
    if (i === 0) {
      path += `M ${x1} ${y} `
    } else if (values[i] !== values[i - 1]) {
      path += `V ${y} `
    }
    path += `H ${x2} `
    xs.push(x1)
  }
  return { path, xs }
}

function rowOrder(keys: string[]): string[] {
  const inputs = keys.filter((k) => k.startsWith('in:')).sort()
  const outputs = keys.filter((k) => k.startsWith('out:')).sort()
  const states = keys.filter((k) => !k.startsWith('in:') && !k.startsWith('out:')).sort()
  return [...inputs, ...states, ...outputs]
}

export function WaveformPanel({ result }: WaveformPanelProps): JSX.Element | null {
  const [hoverCycle, setHoverCycle] = useState<number | null>(null)
  if (result === null) return null
  const keys = rowOrder(Object.keys(result.waveforms))
  const cycleCount = result.cycles.length
  const width = LABEL_W + cycleCount * COL_W + 12
  const height = TOP_PAD + keys.length * ROW_H + 10

  return (
    <section className="waveform-panel" aria-label="Sequential waveform viewer">
      <h2>
        Waveform{' '}
        <span className="scope-chip" title="Exactly what this run claims to cover">
          {result.scope}
        </span>
        <span className="hash-chip" title="SHA-256 of circuit + input sequence">
          hash {result.input_hash.slice(0, 12)}…
        </span>
        <span className="muted final-state">
          final: {Object.entries(result.final_state).map(([k, v]) => `${k}=${v}`).join(' ')}
        </span>
      </h2>
      <div
        className="waveform-scroll"
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const x = e.clientX - rect.left - LABEL_W
          const idx = Math.floor(x / COL_W)
          setHoverCycle(idx >= 0 && idx < cycleCount ? idx : null)
        }}
        onMouseLeave={() => setHoverCycle(null)}
      >
        <svg width={width} height={height} className="waveform-svg" role="img">
          <title>
            {keys.length} signals over {cycleCount} clock cycles
          </title>
          {/* cycle ruler */}
          {Array.from({ length: cycleCount }, (_, i) => (
            <text
              key={`c${i}`}
              x={LABEL_W + i * COL_W + COL_W / 2}
              y={14}
              textAnchor="middle"
              className="wf-cycle-num"
            >
              {i}
            </text>
          ))}
          {keys.map((key, rowIndex) => {
            const values = result.waveforms[key]
            const rowTop = TOP_PAD + rowIndex * ROW_H
            const { path, xs } = signalPath(values, rowTop)
            return (
              <g key={key} className={`wf-row wf-${values[0] === undefined ? 'x' : 'ok'}`}>
                <text x={8} y={rowTop + ROW_H / 2 + 4} className="wf-label">
                  {key}
                </text>
                <rect
                  x={LABEL_W}
                  y={rowTop}
                  width={cycleCount * COL_W}
                  height={ROW_H}
                  className="wf-row-bg"
                />
                <path d={path} className="wf-signal" />
                {xs.map((x, i) =>
                  values[i] === 'X' || values[i] === 'Z' ? (
                    <text
                      key={`${key}_x${i}`}
                      x={x + COL_W / 2}
                      y={rowTop + ROW_H / 2 + 4}
                      textAnchor="middle"
                      className={`value-text value-${values[i]}`}
                    >
                      {values[i]}
                    </text>
                  ) : null,
                )}
              </g>
            )
          })}
        {hoverCycle !== null && (
          <line
            x1={LABEL_W + hoverCycle * COL_W + COL_W / 2}
            x2={LABEL_W + hoverCycle * COL_W + COL_W / 2}
            y1={TOP_PAD - 8}
            y2={height - 6}
            stroke="#ffd166"
            strokeWidth={1.5}
          />
        )}
        </svg>
      </div>
      <table className="trace-table wf-stats" aria-label="Per-signal analysis">
        <thead>
          <tr>
            <th>signal</th><th>transitions</th><th>rising</th><th>falling</th><th>1-density</th>
            <th>{hoverCycle !== null ? `value @ cycle ${hoverCycle}` : 'value (hover the graph)'}</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const values = result.waveforms[k] ?? []
            const st = analyze(values)
            const atHover = hoverCycle !== null ? (values[hoverCycle] ?? '—') : '—'
            return (
              <tr key={k}>
                <td>{k}</td>
                <td>{st.transitions}</td>
                <td>{st.rising}</td>
                <td>{st.falling}</td>
                <td>{Math.round((st.ones / Math.max(1, values.length)) * 100)}%</td>
                <td>{atHover}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="muted">
        {keys.length} signal(s) × {cycleCount} cycles · async events:{' '}
        {result.events.filter((e) => e.cause === 'async').length} · clock edges:{' '}
        {result.events.filter((e) => e.cause === 'clock_edge').length}
      </p>
    </section>
  )
}
