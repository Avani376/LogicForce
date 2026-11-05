/**
 * Waveform viewer: one digital signal row per traced signal, one column per clock
 * cycle. Values render as text-bearing levels — 0 low, 1 high, X mid-band (never
 * color alone), Z flat gray. Deterministic engine output in, picture out.
 */

import type { SequentialResult } from '../types'

interface WaveformPanelProps {
  result: SequentialResult | null
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
      <div className="waveform-scroll">
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
        </svg>
      </div>
      <p className="muted">
        {keys.length} signal(s) × {cycleCount} cycles · async events:{' '}
        {result.events.filter((e) => e.cause === 'async').length} · clock edges:{' '}
        {result.events.filter((e) => e.cause === 'clock_edge').length}
      </p>
    </section>
  )
}
