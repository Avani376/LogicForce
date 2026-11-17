/** Trace panel: the ordered event list emitted by the engine for the last run. */

import type { TraceEvent } from '../types'

interface TracePanelProps {
  trace: TraceEvent[]
  eventCount: number
  scope: string
  hash: string
}

export function TracePanel({
  trace,
  eventCount,
  scope,
  hash,
}: TracePanelProps): JSX.Element {
  return (
    <section className="trace-panel" aria-label="Simulation trace">
      <h2>
        Trace{' '}
        <span className="scope-chip" title="Exactly what this run claims to cover">
          {scope || 'no run'}
        </span>
        {hash !== '' && (
          <span className="hash-chip" title="SHA-256 of circuit + inputs (reproducibility)">
            hash {hash.slice(0, 12)}…
          </span>
        )}
      </h2>
      {trace.length === 0 ? (
        <p className="muted">No value changes in the last run.</p>
      ) : (
        <table className="trace-table">
          <caption className="visually-hidden">
            Simulation trace events in emission order
          </caption>
          <thead>
            <tr>
              <th scope="col">seq</th>
              <th scope="col">delta</th>
              <th scope="col">net</th>
              <th scope="col">old → new</th>
              <th scope="col">cause</th>
            </tr>
          </thead>
          <tbody>
            {trace.map((event) => (
              <tr key={event.seq}>
                <td>{event.seq}</td>
                <td>{event.delta}</td>
                <td>{event.net}</td>
                <td>
                  {event.old} → {event.new}
                </td>
                <td>
                  {event.cause.type}:{event.cause.component}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="muted">{eventCount} event(s) · same design + inputs ⇒ byte-identical result</p>
    </section>
  )
}
