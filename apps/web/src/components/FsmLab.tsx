/**
 * FSM Lab: state-graph visualizer + simulation + reachability.
 * Talks to /api/fsm/simulate and /api/fsm/reachable — the engines compute,
 * this panel renders. The graph is laid out from the FSM document itself.
 */

import { useCallback, useMemo, useState } from 'react'

interface FsmDoc {
  fsm_schema_version: number
  inputs: string[]
  outputs: string[]
  states: string[]
  initial: string
  transitions: { from: string; when: Record<string, string>; to: string; outputs: Record<string, string> }[]
}

interface FsmCycle {
  cycle: number
  state: string
  outputs: Record<string, string>
}

const EXAMPLE_FSM: FsmDoc = {
  fsm_schema_version: 1,
  inputs: ['x'],
  outputs: ['z'],
  states: ['A', 'B', 'C'],
  initial: 'A',
  transitions: [
    { from: 'A', when: { x: '1' }, to: 'B', outputs: { z: '0' } },
    { from: 'A', when: { x: '0' }, to: 'A', outputs: { z: '0' } },
    { from: 'B', when: { x: '1' }, to: 'C', outputs: { z: '0' } },
    { from: 'B', when: { x: '0' }, to: 'B', outputs: { z: '0' } },
    { from: 'C', when: { x: '1' }, to: 'A', outputs: { z: '1' } },
    { from: 'C', when: { x: '0' }, to: 'C', outputs: { z: '1' } },
  ],
}

const EXAMPLE_SEQUENCE = [{ x: '1' }, { x: '1' }, { x: '1' }]

function whenLabel(when: Record<string, string>): string {
  return Object.entries(when).map(([k, v]) => `${k}=${v}`).join(' ')
}

function outputsLabel(outputs: Record<string, string>): string {
  return Object.entries(outputs).map(([k, v]) => `${k}=${v}`).join(' ')
}

export function FsmLab(): JSX.Element {
  const [fsmText, setFsmText] = useState(JSON.stringify(EXAMPLE_FSM, null, 2))
  const [sequenceText, setSequenceText] = useState(JSON.stringify(EXAMPLE_SEQUENCE))
  const [cycles, setCycles] = useState<FsmCycle[] | null>(null)
  const [finalState, setFinalState] = useState<string | null>(null)
  const [reachable, setReachable] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const parsed = useMemo((): { fsm: FsmDoc | null; problem: string | null } => {
    try {
      const fsm = JSON.parse(fsmText) as FsmDoc
      if (!Array.isArray(fsm.states) || !Array.isArray(fsm.transitions)) {
        return { fsm: null, problem: 'FSM needs "states" and "transitions" arrays' }
      }
      return { fsm, problem: null }
    } catch (cause) {
      return { fsm: null, problem: cause instanceof Error ? cause.message : String(cause) }
    }
  }, [fsmText])

  const simulate = useCallback(async (): Promise<void> => {
    setError(null)
    try {
      const sequence = JSON.parse(sequenceText) as Record<string, string>[]
      const response = await fetch('/api/fsm/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fsm: parsed.fsm, input_sequence: sequence }),
      })
      const body = await response.json()
      if (!response.ok) {
        setError(body.detail?.message ?? body.detail?.code ?? `HTTP ${response.status}`)
        return
      }
      setCycles(body.cycles as FsmCycle[])
      setFinalState(body.final_state as string)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [parsed.fsm, sequenceText])

  const computeReachable = useCallback(async (): Promise<void> => {
    setError(null)
    try {
      const response = await fetch('/api/fsm/reachable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fsm: parsed.fsm }),
      })
      const body = await response.json()
      if (!response.ok) {
        setError(body.detail?.message ?? body.detail?.code ?? `HTTP ${response.status}`)
        return
      }
      setReachable(body.reachable_states as string[])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [parsed.fsm])

  const graph = useMemo(() => {
    if (parsed.fsm === null) return null
    const { states, initial, transitions } = parsed.fsm
    const W = 620
    const H = 380
    const cx = W / 2
    const cy = H / 2 + 6
    const R = Math.min(150, 60 + states.length * 14)
    const nodeR = 26
    const angleOf = (state: string): number => {
      const idx = Math.max(0, states.indexOf(state))
      return -Math.PI / 2 + (2 * Math.PI * idx) / Math.max(1, states.length)
    }
    const pos = new Map(states.map((st) => {
      const a = angleOf(st)
      return [st, { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) }] as const
    }))
    const edges = transitions.map((t, i) => {
      const from = pos.get(t.from) ?? { x: cx, y: cy }
      const to = pos.get(t.to) ?? { x: cx, y: cy }
      if (t.from === t.to) {
        const a = angleOf(t.from)
        const ox = cx + (R + nodeR + 16) * Math.cos(a)
        const oy = cy + (R + nodeR + 16) * Math.sin(a)
        return {
          key: `loop${i}`,
          path: `M ${ox - 12} ${oy - 12} A 17 17 0 1 1 ${ox + 12} ${oy - 12}`,
          labelX: ox,
          labelY: oy,
          label: whenLabel(t.when),
        }
      }
      const mx = (from.x + to.x) / 2
      const my = (from.y + to.y) / 2
      const dx = to.x - from.x
      const dy = to.y - from.y
      const len = Math.hypot(dx, dy) || 1
      const ux = dx / len
      const uy = dy / len
      const x1 = from.x + ux * nodeR
      const y1 = from.y + uy * nodeR
      const x2 = to.x - ux * nodeR
      const y2 = to.y - uy * nodeR
      const bend = 34
      const cxp = mx - uy * bend
      const cyp = my + ux * bend
      return {
        key: `e${i}`,
        path: `M ${x1} ${y1} Q ${cxp} ${cyp} ${x2} ${y2}`,
        labelX: (cxp + mx) / 2,
        labelY: (cyp + my) / 2,
        label: whenLabel(t.when),
      }
    })
    return { W, H, nodeR, pos, edges, initial, states }
  }, [parsed.fsm])

  return (
    <div className="workspace" aria-label="FSM lab">
      <section className="panel" aria-label="FSM editor">
        <h2>FSM definition</h2>
        <p className="muted">
          Edit the JSON or use the example, then simulate an input sequence or compute
          the reachable states. The engines validate everything — this panel only draws.
        </p>
        <textarea
          className="asm-editor"
          rows={12}
          value={fsmText}
          onChange={(e) => setFsmText(e.target.value)}
          spellCheck={false}
          aria-label="FSM JSON"
        />
        <div className="verify-form">
          <input
            className="verify-input"
            value={sequenceText}
            onChange={(e) => setSequenceText(e.target.value)}
            aria-label="Input sequence JSON"
            placeholder='input sequence, e.g. [{"x":"1"},{"x":"1"}]'
          />
          <button type="button" onClick={() => void simulate()} disabled={parsed.fsm === null}>
            Simulate
          </button>
          <button type="button" onClick={() => void computeReachable()} disabled={parsed.fsm === null}>
            Reachable states
          </button>
        </div>
        {parsed.problem !== null && <p className="banner-error">JSON problem: {parsed.problem}</p>}
        {error !== null && <p className="banner-error">{error}</p>}
        {cycles !== null && (
          <div className="counterexample">
            <p>
              <strong>{cycles.length} cycles</strong> · final state <strong>{finalState}</strong>
            </p>
            <table className="trace-table">
              <thead>
                <tr><th>cycle</th><th>state</th><th>outputs</th></tr>
              </thead>
              <tbody>
                {cycles.map((c) => (
                  <tr key={c.cycle}>
                    <td>{c.cycle}</td>
                    <td>{c.state}</td>
                    <td>{outputsLabel(c.outputs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {reachable !== null && (
          <p className="muted">
            Reachable from <strong>{parsed.fsm?.initial}</strong>: {reachable.join(', ')} —
            unreachable states are dimmed in the graph.
          </p>
        )}
      </section>

      <section className="panel" aria-label="State graph">
        <h2>State graph</h2>
        {graph === null ? (
          <p className="muted">Fix the JSON above to see the state graph.</p>
        ) : (
          <div className="waveform-scroll">
            <svg width={graph.W} height={graph.H} className="fsm-svg" role="img" aria-label="FSM state graph">
              <defs>
                <marker id="fsm-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#8a97ff" />
                </marker>
              </defs>
              {graph.edges.map((edge) => (
                <g key={edge.key}>
                  <path d={edge.path} fill="none" stroke="#8a97ff" strokeWidth={1.8} markerEnd="url(#fsm-arrow)" />
                  <text x={edge.labelX} y={edge.labelY - 4} className="fsm-edge-label">{edge.label}</text>
                </g>
              ))}
              {graph.states.map((st) => {
                const p = graph.pos.get(st) ?? { x: 0, y: 0 }
                const dimmed = reachable !== null && !reachable.includes(st)
                return (
                  <g key={st} opacity={dimmed ? 0.35 : 1}>
                    {st === graph.initial && (
                      <path
                        d={`M ${p.x - 52} ${p.y - 34} L ${p.x - 10} ${p.y - 8}`}
                        stroke="#ffd166" strokeWidth={2} markerEnd="url(#fsm-arrow)"
                      />
                    )}
                    <circle
                      cx={p.x} cy={p.y} r={graph.nodeR}
                      fill={st === graph.initial ? '#2a3a6e' : '#1c2150'}
                      stroke={st === graph.initial ? '#ffd166' : '#5b6ee1'}
                      strokeWidth={st === graph.initial ? 2.5 : 1.6}
                    />
                    {st === graph.initial && (
                      <circle cx={p.x} cy={p.y} r={graph.nodeR - 5} fill="none" stroke="#ffd166" strokeWidth={1} />
                    )}
                    <text x={p.x} y={p.y + 5} textAnchor="middle" className="fsm-state-label">{st}</text>
                  </g>
                )
              })}
            </svg>
          </div>
        )}
        <p className="muted">
          Yellow ring marks the initial state; arrows carry their input conditions; the
          reachable check dims states no input sequence can reach.
        </p>
      </section>
    </div>
  )
}
