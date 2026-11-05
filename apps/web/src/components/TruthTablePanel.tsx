/** Truth-table modal: exhaustive enumeration with its scope label front and center. */

import type { TruthTableResult } from '../types'

interface TruthTablePanelProps {
  result: TruthTableResult | null
  error: string | null
  onClose: () => void
}

export function TruthTablePanel({
  result,
  error,
  onClose,
}: TruthTablePanelProps): JSX.Element {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Truth table"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <h2>
            Truth table{' '}
            {result !== null && (
              <span className="scope-chip">{result.scope}</span>
            )}
          </h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close truth table">
            ✕
          </button>
        </div>
        {error !== null && (
          <p className="banner banner-error" role="alert">
            {error}
          </p>
        )}
        {result !== null && (
          <div className="tt-scroll">
            <table className="tt-table">
              <caption className="visually-hidden">
                Exhaustive truth table, inputs sorted by name, first name most significant
              </caption>
              <thead>
                <tr>
                  {result.input_names.map((name) => (
                    <th key={name} scope="col" className="tt-in">
                      {name}
                    </th>
                  ))}
                  {result.output_names.map((name) => (
                    <th key={name} scope="col" className="tt-out">
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, index) => (
                  <tr key={index}>
                    {result.input_names.map((name) => (
                      <td key={name} className={`value-${row.inputs[name]}`}>
                        {row.inputs[name]}
                      </td>
                    ))}
                    {result.output_names.map((name) => (
                      <td key={name} className={`value-${row.outputs[name]}`}>
                        {row.outputs[name]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted">
          {result !== null
            ? `${result.rows.length} row(s) — engine ${result.engine_version}`
            : 'Loading…'}
        </p>
      </div>
    </div>
  )
}
