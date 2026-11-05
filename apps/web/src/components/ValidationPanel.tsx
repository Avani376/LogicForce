/** Validation report panel: errors first, then warnings. Honest and complete. */

import type { SimulationResult, ValidationReport } from '../types'

interface ValidationPanelProps {
  report: ValidationReport | null
  sim: SimulationResult | null
}

export function ValidationPanel({ report, sim }: ValidationPanelProps): JSX.Element {
  if (report !== null && !report.ok) {
    return (
      <section className="panel panel-error" aria-label="Validation report">
        <h2>Validation — {report.errors.length} error{report.errors.length === 1 ? '' : 's'}</h2>
        <ul className="issue-list">
          {report.errors.map((issue, index) => (
            <li key={`${issue.code}_${index}`} className="issue issue-error">
              <span className="issue-code">{issue.code}</span>
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
        <p className="muted">
          The engine refuses to simulate circuits with validation errors.
        </p>
      </section>
    )
  }
  if (report !== null && report.ok) {
    return (
      <section className="panel panel-warning" aria-label="Validation report">
        <h2>Validation — warnings</h2>
        <ul className="issue-list">
          {report.warnings.map((issue, index) => (
            <li key={`${issue.code}_${index}`} className="issue issue-warning">
              <span className="issue-code">{issue.code}</span>
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
      </section>
    )
  }
  if (sim !== null) {
    return (
      <section className="panel panel-ok" aria-label="Validation report">
        <h2>Validation</h2>
        <p className="ok-text">✓ No validation errors — simulated by engine {sim.engine_version}</p>
      </section>
    )
  }
  return (
    <section className="panel" aria-label="Validation report">
      <h2>Validation</h2>
      <p className="muted">Waiting for engine…</p>
    </section>
  )
}
