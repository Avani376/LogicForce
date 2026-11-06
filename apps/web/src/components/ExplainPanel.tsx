/** Explain panel: evidence-grounded explanations, auto-populated from engine output. */

import { useCallback, useState } from 'react'

interface ExplanationResult {
  kind: string
  summary: string
  findings: { kind: string; text: string; evidence: { source: string; [k: string]: unknown }[] }[]
  suggestions: { text: string; kind: string }[]
  disclaimer: string
}

const KINDS = ['cpu_trace', 'verification', 'fault_experiment', 'cosim', 'circuit_truth_table'] as const

interface ExplainPanelProps {
  autoEvidence?: Record<string, unknown> | null
}

export function ExplainPanel({ autoEvidence }: ExplainPanelProps): JSX.Element {
  const [kind, setKind] = useState<string>('cpu_trace')
  const [evidenceText, setEvidenceText] = useState(
    autoEvidence ? JSON.stringify(autoEvidence, null, 2) : '{ "trace": [], "stop_reason": "hlt" }'
  )
  const [result, setResult] = useState<ExplanationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (): Promise<void> => {
    setError(null); setResult(null)
    try {
      const evidence = JSON.parse(evidenceText) as Record<string, unknown>
      const response = await fetch('/api/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ explanation_schema_version: 1, kind, evidence }),
      })
      const body = await response.json()
      if (!response.ok) { setError(body.detail?.message ?? `HTTP ${response.status}`); return }
      setResult(body as ExplanationResult)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }, [kind, evidenceText])

  const loadCurrentEvidence = useCallback((): void => {
    if (autoEvidence !== null) setEvidenceText(JSON.stringify(autoEvidence, null, 2))
  }, [autoEvidence])

  return (
    <div className="explain-panel">
      <h2>Evidence-Grounded Explanation</h2>
      <p className="muted">Rule-based analysis of engine output. Not an AI model. Deterministic.</p>
      <div className="explain-form">
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Explanation kind">
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        {autoEvidence !== null && (
          <button type="button" onClick={loadCurrentEvidence}
            aria-label="Load evidence from the current simulation">
            Load current simulation evidence
          </button>
        )}
        <button type="button" onClick={() => void run()}>Explain</button>
      </div>
      <textarea className="asm-editor" value={evidenceText} rows={8} spellCheck={false}
        onChange={(e) => setEvidenceText(e.target.value)}
        aria-label="Evidence JSON (paste engine output here)" />
      {error && <p className="banner-error">{error}</p>}
      {result && (
        <div className="explain-result">
          <p className="ok-text">{result.summary}</p>
          <ul className="issue-list">
            {result.findings.map((f, i) => (
              <li key={i} className="issue">
                <span className="issue-code">{f.kind}</span>
                <span>{f.text}</span>
                <span className="muted">{f.evidence.map((e) => `[${e.source}${e.step !== undefined ? ` step ${e.step}` : ''}]`).join(' ')}</span>
              </li>
            ))}
          </ul>
          {result.suggestions.length > 0 && (
            <div>
              <h3>Suggestions (unverified)</h3>
              <ul className="issue-list">{result.suggestions.map((s, i) => (
                <li key={i} className="issue issue-warning"><span>{s.text}</span></li>
              ))}</ul>
            </div>
          )}
          <p className="muted">{result.disclaimer}</p>
        </div>
      )}
    </div>
  )
}
