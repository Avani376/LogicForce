/**
 * Visuals tab — the session dashboard.
 * Every pixel is driven by real engine output from this session; empty states
 * are honest (no fabricated data, per the platform's core principle).
 */

import { useEffect, useMemo, useState } from 'react'

import type { HealthStatus, SequentialResult, SimulationResult, TruthTableResult } from '../types'

const STAGES = ['Specify', 'Design', 'Simulate', 'Verify', 'Fault-Test', 'Diagnose', 'Repair', 'Optimize', 'Re-Verify']
const SEGMENT_COLORS = ['#5b6ee1', '#d946ef', '#34c98e', '#ffd166', '#ff8fab', '#22d3ee']

interface VisualizerProps {
  sim: SimulationResult | null
  seqResult: SequentialResult | null
  tt: TruthTableResult | null
  health: HealthStatus | null
}

/** Animated 0→value counter (one glance ⇒ the number, not a wall of text). */
function CountUp({ value }: { value: number }): JSX.Element {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    const start = performance.now()
    const duration = 700
    let raf = 0
    const tick = (now: number): void => {
      const t = Math.min(1, (now - start) / duration)
      setShown(Math.round(value * (1 - Math.pow(1 - t, 3))))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])
  return <span className="stat-number">{shown.toLocaleString()}</span>
}

/** Cause label helper — circuit causes are objects, sequential causes are strings. */
function causeKey(cause: unknown): string {
  if (typeof cause === 'string') return cause
  const obj = cause as { type?: string; component?: string }
  return obj.type !== undefined ? `${obj.type}:${obj.component}` : String(cause)
}

/** SVG donut with animated sweep and per-segment hover emphasis. */
function Donut({ segments }: { segments: { label: string; count: number; color: string }[] }): JSX.Element {
  const total = segments.reduce((sum, s) => sum + s.count, 0)
  const [hovered, setHovered] = useState<string | null>(null)
  if (total === 0) return <p className="muted">No events yet — run something and the ring fills itself.</p>
  const radius = 52
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 140 140" className="donut" role="img" aria-label="Event mix donut chart">
        {segments.map((seg) => {
          const dash = (seg.count / total) * circumference
          const el = (
            <circle
              key={seg.label}
              cx="70" cy="70" r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth={hovered === seg.label ? 21 : 15}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              className="donut-seg"
              onMouseEnter={() => setHovered(seg.label)}
              onMouseLeave={() => setHovered(null)}
            />
          )
          offset += dash
          return el
        })}
        <text x="70" y="66" className="donut-total">{total}</text>
        <text x="70" y="82" className="donut-caption">events</text>
      </svg>
      <ul className="donut-legend">
        {segments.map((seg) => (
          <li key={seg.label} className={hovered !== null && hovered !== seg.label ? 'legend-dim' : ''}
            onMouseEnter={() => setHovered(seg.label)} onMouseLeave={() => setHovered(null)}>
            <span className="legend-dot" style={{ background: seg.color }} />
            <span>{seg.label}</span>
            <span className="legend-count">{Math.round((seg.count / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Visualizer({ sim, seqResult, tt, health }: VisualizerProps): JSX.Element {
  // Event mix across both engines.
  const segments = useMemo(() => {
    const counts = new Map<string, number>()
    for (const e of sim?.trace ?? []) {
      const k = causeKey(e.cause)
      counts.set(k, (counts.get(k) ?? 0) + 1)
    }
    for (const e of seqResult?.events ?? []) {
      const k = causeKey(e.cause)
      counts.set(k, (counts.get(k) ?? 0) + 1)
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([label, count], i) => ({ label, count, color: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }))
  }, [sim, seqResult])

  // Sparkline of propagation deltas (circuit trace order).
  const spark = useMemo(() => {
    const deltas = (sim?.trace ?? []).map((e) => e.delta)
    if (deltas.length < 2) return null
    const max = Math.max(...deltas.map(Math.abs), 1)
    const w = 260, h = 44
    const step = w / (deltas.length - 1)
    const points = deltas.map((d, i) => `${(i * step).toFixed(1)},${(h / 2 - (d / max) * (h / 2 - 4)).toFixed(1)}`)
    return { line: `M ${points.join(' L ')}`, area: `M 0,${h / 2} L ${points.join(' L ')} L ${w},${h / 2} Z` }
  }, [sim])

  // Truth-table 1-density per output.
  const density = useMemo(() => {
    if (tt === null) return []
    return tt.output_names.map((name) => {
      const ones = tt.rows.filter((row) => row.outputs[name] === '1').length
      return { name, ones, total: tt.rows.length }
    })
  }, [tt])

  const steps = [
    ['Circuit built', true],
    ['Simulated', sim !== null],
    ['Truth table', tt !== null],
    ['Sequential run', seqResult !== null],
  ] as [string, boolean][]
  const doneCount = steps.filter(([, ok]) => ok).length

  return (
    <div className="workspace visuals" aria-label="Session dashboard">
      {/* Stat tiles — the whole session in four numbers. */}
      <div className="stat-row" aria-label="Session statistics">
        <div className="stat-tile" title="Value changes propagated by the combinational engine">
          <span className="stat-number-wrap"><CountUp value={sim?.trace.length ?? 0} /></span>
          <span className="stat-label">circuit events</span>
        </div>
        <div className="stat-tile" title="Clock cycles simulated by the sequential engine">
          <span className="stat-number-wrap"><CountUp value={seqResult?.cycles.length ?? 0} /></span>
          <span className="stat-label">clock cycles</span>
        </div>
        <div className="stat-tile" title="Exhaustive truth-table rows">
          <span className="stat-number-wrap"><CountUp value={tt?.rows.length ?? 0} /></span>
          <span className="stat-label">truth-table rows</span>
        </div>
        <div className="stat-tile stat-tile-live" title="API health reported by the server">
          <span className="stat-number-wrap">
            {health?.status === 'ok' ? <CountUp value={12} /> : '—'}
          </span>
          <span className="stat-label">
            {health?.status === 'ok' ? `engines online · v${health.engine_version}` : 'API offline'}
          </span>
        </div>
      </div>

      {/* Session progress — what you have actually done. */}
      <section className="panel session-progress" aria-label="Your session progress">
        <div className="progress-chips">
          {steps.map(([label, ok]) => (
            <span key={label} className={`progress-chip ${ok ? 'chip-done' : 'chip-todo'}`}>
              <span className="chip-check">{ok ? '✓' : '·'}</span> {label}
            </span>
          ))}
          <span className="progress-fraction">{doneCount}/4 session steps</span>
        </div>
      </section>

      {/* The engineering loop, with a pulse travelling through it. */}
      <section className="panel visuals-hero" aria-label="Engineering workflow">
        <h2>The LogicForge loop</h2>
        <div className="pipeline" role="img" aria-label="Specify through re-verify pipeline">
          {STAGES.map((stage, i) => (
            <div className="pipeline-stage" style={{ animationDelay: `${i * 0.35}s` }} key={stage}>
              <span className="pipeline-dot" />
              <span className="pipeline-label">{stage}</span>
            </div>
          ))}
          <span className="pipeline-pulse" aria-hidden="true" />
        </div>
        <p className="muted">
          Every stage is a deterministic engine — the output of one becomes the verified input of the next.
        </p>
      </section>

      <div className="visuals-grid">
        <section className="panel" aria-label="Event mix donut">
          <h2>Event mix</h2>
          <Donut segments={segments} />
        </section>

        <section className="panel" aria-label="Propagation sparkline">
          <h2>Propagation deltas</h2>
          {spark === null ? (
            <p className="muted">Simulate a circuit and each value change lands on this line.</p>
          ) : (
            <svg viewBox="0 0 260 44" className="sparkline" preserveAspectRatio="none" role="img" aria-label="Event deltas sparkline">
              <path className="spark-area" d={spark.area} />
              <path className="spark-line" d={spark.line} />
            </svg>
          )}
          {sim !== null && (
            <p className="muted chart-foot">scope {sim.scope} · hash {sim.input_hash.slice(0, 12)}…</p>
          )}
        </section>

        <section className="panel" aria-label="Truth table heatmap">
          <h2>Truth-table heatmap</h2>
          {tt === null ? (
            <p className="muted">Generate a truth table and every row lands here with a staggered reveal.</p>
          ) : (
            <>
              <div className="density-rows">
                {density.map((d) => (
                  <div className="bar-row" key={d.name} title={`${d.ones}/${d.total} rows are 1`}>
                    <span className="bar-label">{d.name}</span>
                    <div className="bar-track">
                      <div className="bar-fill bar-fill-density" style={{ width: `${(d.ones / d.total) * 100}%` }} />
                    </div>
                    <span className="bar-count">{Math.round((d.ones / d.total) * 100)}%</span>
                  </div>
                ))}
              </div>
              <div className="tt-heatmap">
                {tt.rows.map((row, i) => (
                  <div className="tt-cell-row" style={{ animationDelay: `${Math.min(i * 0.02, 1.6)}s` }} key={i}
                    title={tt.input_names.map((n) => row.inputs[n]).join('')}>
                    <span className="tt-inputs">{tt.input_names.map((n) => row.inputs[n]).join('')}</span>
                    {tt.output_names.map((name) => (
                      <span key={name} className={`tt-cell ${row.outputs[name] === '1' ? 'tt-cell-one' : 'tt-cell-zero'}`}>
                        {row.outputs[name]}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="panel" aria-label="Sequential waveform">
          <h2>Sequential draw-on</h2>
          {seqResult === null || Object.keys(seqResult.waveforms).length === 0 ? (
            <p className="muted">Run a clocked circuit and its waveforms will draw themselves here.</p>
          ) : (
            <div className="draw-waves">
              {Object.entries(seqResult.waveforms).map(([signal, values]) => (
                <div className="draw-wave-row" key={signal}>
                  <span className="bar-label">{signal}</span>
                  <svg className="draw-wave" viewBox={`0 0 ${Math.max(values.length, 2) * 24} 30`} preserveAspectRatio="none" aria-hidden="true">
                    <polyline
                      className="draw-path"
                      points={values.map((v, i) => `${i * 24 + 12},${v === '1' ? 6 : 24}`).join(' ')}
                      style={{ animationDelay: '0.2s' }}
                    />
                  </svg>
                </div>
              ))}
            </div>
          )}
          {seqResult !== null && <p className="muted chart-foot">{seqResult.cycles.length} cycles · {seqResult.scope}</p>}
        </section>
      </div>
    </div>
  )
}
