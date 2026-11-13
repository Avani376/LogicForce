/**
 * Fault Lab: inject a fault into a model, run the detection experiment, and
 * search for repairs — all through /api/faults/* and /api/repair-search.
 * The engines decide detection and repair validity; this panel reports.
 */

import { useCallback, useState } from 'react'

interface ExperimentCheck {
  property_id: string
  nominal_verdict: string
  faulty_verdict: string
}

interface ExperimentResult {
  detected: boolean
  checks: ExperimentCheck[]
  behavior: { first_divergence: Record<string, unknown> | null }
}

interface RepairCandidate {
  id: string
  valid: boolean
  description?: string
}

interface RepairResult {
  re_verified: boolean
  candidates: RepairCandidate[]
  repaired_model: Record<string, unknown> | null
}

interface FaultLabProps {
  circuitDoc: string
  outputSignals: string[]
}

const EXAMPLE_COMB_FAULT = {
  fault_schema_version: 1,
  id: 'F-sa0',
  operator: 'stuck_at',
  target: { component_id: '', pin: 'a' },
  params: { value: '0' },
}

const EXAMPLE_FSM_FAULT = {
  fault_schema_version: 1,
  id: 'F-tx',
  operator: 'transition_redirect',
  target: { transition_index: 0 },
  params: { to: 'B', set_outputs: {} },
}

export function FaultLab({ circuitDoc, outputSignals }: FaultLabProps): JSX.Element {
  const [modelKind, setModelKind] = useState<'combinational' | 'fsm'>('combinational')
  const computeCircuitFault = useCallback((): string => {
    let doc: { components?: { id: string; type: string }[] } = {}
    try { doc = JSON.parse(circuitDoc) as typeof doc } catch { doc = {} }
    const gate = doc.components?.find((c) => !['INPUT', 'OUTPUT', 'CONST0', 'CONST1'].includes(c.type))
    const fault = { ...EXAMPLE_COMB_FAULT, target: { component_id: gate?.id ?? '', pin: 'a' } }
    return JSON.stringify(fault, null, 2)
  }, [circuitDoc])

  const [faultText, setFaultText] = useState(() => {
    let doc: { components?: { id: string; type: string }[] } = {}
    try { doc = JSON.parse(circuitDoc) as typeof doc } catch { doc = {} }
    const gate = doc.components?.find((c) => !['INPUT', 'OUTPUT', 'CONST0', 'CONST1'].includes(c.type))
    const fault = { ...EXAMPLE_COMB_FAULT, target: { component_id: gate?.id ?? '', pin: 'a' } }
    return JSON.stringify(fault, null, 2)
  })
  const [invariant, setInvariant] = useState('')
  const [experiment, setExperiment] = useState<ExperimentResult | null>(null)
  const [repair, setRepair] = useState<RepairResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const setKind = useCallback((kind: 'combinational' | 'fsm'): void => {
    setModelKind(kind)
    setExperiment(null)
    setRepair(null)
    if (kind === 'fsm') { setFaultText(JSON.stringify(EXAMPLE_FSM_FAULT, null, 2)); return }
    setFaultText(computeCircuitFault())
  }, [circuitDoc, computeCircuitFault])

  const runExperiment = useCallback(async (): Promise<void> => {
    setError(null)
    setExperiment(null)
    setRepair(null)
    setBusy(true)
    try {
      const fault = JSON.parse(faultText) as Record<string, unknown>
      const model = modelKind === 'combinational' ? (JSON.parse(circuitDoc) as Record<string, unknown>) : null
      const properties: Record<string, unknown>[] =
        modelKind === 'combinational' && invariant.trim() !== ''
          ? [{
              property_schema_version: 1,
              id: 'P-ui',
              kind: 'combinational_invariant',
              expression: invariant.trim(),
            }]
          : []
      const response = await fetch('/api/fault-experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_kind: modelKind, model, fault, properties }),
      })
      const body = await response.json()
      if (!response.ok) {
        setError(body.detail?.message ?? body.detail?.code ?? `HTTP ${response.status}`)
        return
      }
      setExperiment(body as ExperimentResult)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(false)
    }
  }, [faultText, modelKind, circuitDoc, invariant])

  const runRepair = useCallback(async (): Promise<void> => {
    setError(null)
    setRepair(null)
    setBusy(true)
    try {
      const fault = JSON.parse(faultText) as Record<string, unknown>
      const model = modelKind === 'combinational' ? (JSON.parse(circuitDoc) as Record<string, unknown>) : null
      const applyResponse = await fetch('/api/faults/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_kind: modelKind, model, fault }),
      })
      const applyBody = await applyResponse.json()
      if (!applyResponse.ok) {
        setError(applyBody.detail?.message ?? applyBody.detail?.code ?? `HTTP ${applyResponse.status}`)
        return
      }
      const properties: Record<string, unknown>[] =
        modelKind === 'combinational' && invariant.trim() !== ''
          ? [{
              property_schema_version: 1,
              id: 'P-ui',
              kind: 'combinational_invariant',
              expression: invariant.trim(),
            }]
          : []
      const response = await fetch('/api/repair-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_kind: modelKind,
          nominal: model,
          faulty: applyBody.faulty_model,
          properties,
          max_candidates: 8,
        }),
      })
      const body = await response.json()
      if (!response.ok) {
        setError(body.detail?.message ?? body.detail?.code ?? `HTTP ${response.status}`)
        return
      }
      setRepair(body as RepairResult)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(false)
    }
  }, [faultText, modelKind, circuitDoc, invariant])

  return (
    <div className="workspace" aria-label="Fault diagnosis lab">
      <section className="panel" aria-label="Fault setup">
        <h2>Fault injection</h2>
        <p className="muted">
          Pick a model, describe the fault, and run the detection experiment. For the
          current circuit, <code>stuck_at</code> faults rewire an input pin to a constant.
          Detection needs a property to check — give a boolean invariant for circuits.
          {modelKind === 'combinational' && outputSignals.length > 0 && (
            <> Available outputs: {outputSignals.join(', ')}</>
          )}
        </p>
        <div className="verify-form">
          <button
            type="button"
            className={`tab-btn ${modelKind === 'combinational' ? 'tab-active' : ''}`}
            onClick={() => setKind('combinational')}
          >
            Current circuit
          </button>
          <button
            type="button"
            className={`tab-btn ${modelKind === 'fsm' ? 'tab-active' : ''}`}
            onClick={() => setKind('fsm')}
          >
            FSM (paste JSON below)
          </button>
        </div>
        {modelKind === 'fsm' && (
          <p className="muted">
            In FSM mode, paste the FSM document as "model" inside the fault JSON payload —
            the experiment endpoint receives it via the apply call below.
          </p>
        )}
        <textarea
          className="asm-editor"
          rows={10}
          value={faultText}
          onChange={(e) => setFaultText(e.target.value)}
          spellCheck={false}
          aria-label="Fault JSON"
        />
        {modelKind === 'combinational' && (
          <div className="verify-form">
            <input
              className="verify-input"
              value={invariant}
              onChange={(e) => setInvariant(e.target.value)}
              aria-label="Detection invariant"
              placeholder={`detection invariant over outputs, e.g. !(${outputSignals[0] ?? 'carry'} & ${outputSignals[1] ?? 'sum'})`}
            />
          </div>
        )}
        <div className="verify-form">
          <button type="button" onClick={() => void runExperiment()} disabled={busy}>
            {busy ? 'Running…' : 'Run detection experiment'}
          </button>
          <button type="button" onClick={() => void runRepair()} disabled={busy}>
            Search repairs
          </button>
        </div>
        {error !== null && <p className="banner-error">{error}</p>}
      </section>

      {experiment !== null && (
        <section className="panel" aria-label="Diagnosis report">
          <h2>Diagnosis report</h2>
          <p>
            <span className={`verdict-chip ${experiment.detected ? 'verdict-PASS' : 'verdict-FAIL'}`}>
              {experiment.detected ? 'DETECTED' : 'NOT DETECTED'}
            </span>
            <span className="muted"> the property suite observed faulty behavior</span>
          </p>
          <table className="trace-table">
            <thead>
              <tr><th>property</th><th>nominal</th><th>faulty</th></tr>
            </thead>
            <tbody>
              {experiment.checks.map((c) => (
                <tr key={c.property_id}>
                  <td>{c.property_id}</td>
                  <td>{c.nominal_verdict}</td>
                  <td>{c.faulty_verdict}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {experiment.behavior.first_divergence !== null && (
            <div>
              <h3>First divergence</h3>
              <pre className="counterexample">{JSON.stringify(experiment.behavior.first_divergence, null, 2)}</pre>
            </div>
          )}
        </section>
      )}

      {repair !== null && (
        <section className="panel" aria-label="Repair results">
          <h2>Repair search</h2>
          <p>
            <span className={`verdict-chip ${repair.re_verified ? 'verdict-PASS' : 'verdict-FAIL'}`}>
              {repair.re_verified ? 'RE-VERIFIED' : 'UNVERIFIED'}
            </span>
            <span className="muted"> every candidate below was checked against the property suite</span>
          </p>
          <ul className="issue-list">
            {repair.candidates.map((c) => (
              <li key={c.id} className="issue">
                {c.id}: {c.valid ? 'valid repair' : 'rejected'} {c.description ? `— ${c.description}` : ''}
              </li>
            ))}
          </ul>
          {repair.repaired_model !== null && (
            <details>
              <summary>Repaired model JSON</summary>
              <pre className="counterexample">{JSON.stringify(repair.repaired_model, null, 2)}</pre>
            </details>
          )}
        </section>
      )}
    </div>
  )
}
