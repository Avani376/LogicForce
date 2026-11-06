/** Verify panel: property checking + counterexample display. */

import { useCallback, useState } from 'react'

interface VerifyResult {
  verdict: string
  scope: string
  explored_cases: number
  counterexample: Record<string, unknown> | null
  reason: string | null
  property: { id: string; expression: string }
}

export function VerifyPanel({ circuitDoc }: { circuitDoc: string }): JSX.Element {
  const [expression, setExpression] = useState('!(a & b)')
  const [result, setResult] = useState<VerifyResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const verify = useCallback(async (): Promise<void> => {
    setError(null); setResult(null)
    try {
      const circuit = JSON.parse(circuitDoc) as Record<string, unknown>
      const response = await fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind: 'combinational_invariant', model: circuit,
          property: { property_schema_version: 1, id: 'P-ui', kind: 'combinational_invariant', expression },
        }),
      })
      const body = await response.json()
      if (!response.ok) { setError(body.detail?.message ?? body.detail?.code ?? `HTTP ${response.status}`); return }
      setResult(body as VerifyResult)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [circuitDoc, expression])

  return (
    <div className="verify-panel">
      <h2>Verification</h2>
      <div className="verify-form">
        <label>Expression: <input className="verify-input" value={expression}
          onChange={(e) => setExpression(e.target.value)}
          placeholder="!(a & b)" aria-label="Property expression" /></label>
        <button type="button" onClick={() => void verify()}>Verify</button>
      </div>
      {error && <p className="banner-error">{error}</p>}
      {result && (
        <div className={`verify-result ${result.verdict === 'PASS' ? 'panel-ok' : 'panel-error'}`}>
          <span className={`scope-chip`}>{result.scope}</span>
          <span className={`verdict-chip verdict-${result.verdict}`}>{result.verdict}</span>
          <span className="muted">{result.explored_cases} case(s) explored</span>
          {result.counterexample !== null && (
            <pre className="counterexample">{JSON.stringify(result.counterexample, null, 2)}</pre>
          )}
          {result.reason && <p className="muted">{result.reason}</p>}
        </div>
      )}
    </div>
  )
}
