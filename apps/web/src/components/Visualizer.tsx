/**
 * Visualizer tab: animated views of the session's REAL engine output.
 * Charts render only data produced by engines this session — honest empty
 * states otherwise (no fabricated data, per the platform's core principle).
 */

import type { SequentialResult, SimulationResult, TruthTableResult } from '../types'

const STAGES = [
  'Specify',
  'Design',
  'Simulate',
  'Verify',
  'Fault-Test',
  'Diagnose',
  'Repair',
  'Optimize',
  'Re-Verify',
]

interface VisualizerProps {
  sim: SimulationResult | null
  seqResult: SequentialResult | null
  tt: TruthTableResult | null
}

function eventKindCounts(sim: SimulationResult | null, seqResult: SequentialResult | null): [string, number][] {
  const counts = new Map<string, number>()
  const bump = (key: string): void => {
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  for (const event of sim?.trace ?? []) bump(String(event.cause))
  for (const event of seqResult?.events ?? []) bump(String(event.cause))
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
}

export function Visualizer({ sim, seqResult, tt }: VisualizerProps): JSX.Element {
  const bars = eventKindCounts(sim, seqResult)
  const maxBar = Math.max(1, ...bars.map(([, n]) => n))
  const hasSessionData = sim !== null || seqResult !== null || tt !== null

  return (
    <div className="workspace visuals" aria-label="Visualizer workspace">
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
        <section className="panel" aria-label="Event chart">
          <h2>Event activity</h2>
          {bars.length === 0 ? (
            <p className="muted">No events yet — simulate a circuit (or run a clock) and this chart comes alive.</p>
          ) : (
            <div className="bar-chart" role="img" aria-label="Event counts by kind">
              {bars.map(([kind, count], i) => (
                <div className="bar-row" key={kind}>
                  <span className="bar-label">{kind}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${(count / maxBar) * 100}%`, animationDelay: `${i * 0.12}s` }}
                    />
                  </div>
                  <span className="bar-count">{count}</span>
                </div>
              ))}
            </div>
          )}
          {sim !== null && (
            <p className="muted chart-foot">
              {sim.event_count} events · scope {sim.scope} · hash {sim.input_hash.slice(0, 12)}…
            </p>
          )}
        </section>

        <section className="panel" aria-label="Truth table heatmap">
          <h2>Truth-table heatmap</h2>
          {tt === null ? (
            <p className="muted">Generate a truth table and every row lands here with a staggered reveal.</p>
          ) : (
            <div className="tt-heatmap" role="img" aria-label="Truth table outputs heatmap">
              {tt.rows.map((row, i) => (
                <div className="tt-cell-row" style={{ animationDelay: `${Math.min(i * 0.02, 1.6)}s` }} key={i}>
                  <span className="tt-inputs">
                    {tt.input_names.map((name) => row.inputs[name]).join('')}
                  </span>
                  {tt.output_names.map((name) => (
                    <span
                      key={name}
                      className={`tt-cell ${row.outputs[name] === '1' ? 'tt-cell-one' : 'tt-cell-zero'}`}
                    >
                      {row.outputs[name]}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          )}
          {tt !== null && <p className="muted chart-foot">{tt.rows.length} rows · {tt.scope}</p>}
        </section>

        <section className="panel" aria-label="Sequential waveform">
          <h2>Sequential draw-on</h2>
          {seqResult === null || seqResult.waveforms === undefined || Object.keys(seqResult.waveforms).length === 0 ? (
            <p className="muted">Run a clocked circuit and its waveforms will draw themselves here.</p>
          ) : (
            <div className="draw-waves">
              {Object.entries(seqResult.waveforms).map(([signal, values]) => (
                <div className="draw-wave-row" key={signal}>
                  <span className="bar-label">{signal}</span>
                  <svg
                    className="draw-wave"
                    viewBox={`0 0 ${Math.max(values.length, 2) * 24} 30`}
                    preserveAspectRatio="none"
                    aria-hidden="true"
                  >
                    <polyline
                      className="draw-path"
                      points={values
                        .map((v, i) => `${i * 24 + 12},${v === '1' ? 6 : 24}`)
                        .join(' ')}
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

      {!hasSessionData && (
        <p className="muted status-note">
          Nothing fabricated here — these charts only ever show what your engines computed this session.
        </p>
      )}
    </div>
  )
}
